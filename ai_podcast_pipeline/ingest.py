from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable
from xml.etree import ElementTree as ET

import requests

from .constants import MAX_CANDIDATES, MAX_CANDIDATES_PER_FEED, RSS_FEEDS
from .models import CandidateStory
from .utils import canonical_domain, canonical_url, parse_datetime, read_json

logger = logging.getLogger(__name__)

# Maximum parallel workers for RSS fetching.
_FETCH_WORKERS = 12


def _local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1].lower()
    return tag.lower()


def _iter_children_by_tag(node: ET.Element, tag_name: str) -> Iterable[ET.Element]:
    target = tag_name.lower()
    for child in list(node):
        if _local_tag(child.tag) == target:
            yield child


def _extract_text(node: ET.Element | None, tags: list[str]) -> str:
    if node is None:
        return ""
    for t in tags:
        for found in _iter_children_by_tag(node, t):
            text = "".join(found.itertext()).strip()
            if text:
                return text
    return ""


def _extract_link(item: ET.Element) -> str:
    for link in _iter_children_by_tag(item, "link"):
        href = link.attrib.get("href")
        if href:
            return href.strip()
        text = "".join(link.itertext()).strip()
        if text:
            return text
    return ""


def _parse_feed(xml_text: str) -> list[CandidateStory]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.debug("XML parse error: %s", exc)
        return []

    items: list[ET.Element] = []
    for node in root.iter():
        tag = _local_tag(node.tag)
        if tag in {"item", "entry"}:
            items.append(node)

    out: list[CandidateStory] = []
    for item in items:
        title = _extract_text(item, ["title"])
        url = _extract_link(item)
        summary = _extract_text(item, ["description", "summary", "content"])
        published_raw = _extract_text(item, ["pubDate", "published", "updated"])
        if not title or not url:
            continue
        out.append(
            CandidateStory(
                title=title,
                url=canonical_url(url),
                source_domain=canonical_domain(url),
                published_at=parse_datetime(published_raw),
                summary=summary,
            )
        )
    return out


def _fetch_one_feed(feed_url: str, timeout: int) -> list[CandidateStory]:
    """Fetch and parse a single RSS feed. Returns an empty list on any error."""
    try:
        resp = requests.get(
            feed_url,
            timeout=timeout,
            headers={"User-Agent": "TheSignalBot/1.0"},
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.debug("Feed fetch failed (%s): %s", feed_url, exc)
        return []

    stories = _parse_feed(resp.text)
    logger.debug("Fetched %d stories from %s", len(stories), feed_url)
    return stories


# ---------------------------------------------------------------------------
# Full-article text fetching
# ---------------------------------------------------------------------------

_FULL_TEXT_CHAR_LIMIT = 16_000  # ~3 000 words; keeps prompt cost sane
_SKIP_TAGS = frozenset({"script", "style", "nav", "header", "footer", "aside", "noscript"})


class _TextExtractor(HTMLParser):
    """Minimal HTML → plain-text extractor using only the stdlib."""

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._depth = 0  # skip-tag nesting depth

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag.lower() in _SKIP_TAGS:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in _SKIP_TAGS and self._depth > 0:
            self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._depth == 0:
            text = data.strip()
            if text:
                self._chunks.append(text)

    def get_text(self) -> str:
        return " ".join(self._chunks)


def fetch_article_text(url: str, timeout: int = 10) -> str | None:
    """Fetch a URL and return its visible plain text, capped at _FULL_TEXT_CHAR_LIMIT chars.

    Returns None on any network/parse error so callers can fall back to the RSS summary.
    """
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; TheSignalBot/1.0)",
                "Accept": "text/html,application/xhtml+xml",
            },
            allow_redirects=True,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type:
            return None
        extractor = _TextExtractor()
        extractor.feed(resp.text)
        text = extractor.get_text()
        if not text:
            return None
        return text[:_FULL_TEXT_CHAR_LIMIT]
    except Exception as exc:
        logger.debug("Could not fetch full text for %s: %s", url, exc)
        return None


def fetch_article_text_batch(
    stories: list,  # list[ScoredStory]
    timeout: int = 10,
    workers: int = 6,
    on_done: Callable[[], None] | None = None,
) -> None:
    """Fetch full article text for each story in parallel, setting story.candidate.full_text in-place."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_story = {
            pool.submit(fetch_article_text, s.candidate.url, timeout): s for s in stories
        }
        for future in as_completed(future_to_story):
            story = future_to_story[future]
            try:
                story.candidate.full_text = future.result()
            except Exception as exc:
                logger.debug("Batch fetch failed for %s: %s", story.candidate.url, exc)
                story.candidate.full_text = None
            if on_done is not None:
                on_done()


def fetch_candidates(
    max_candidates: int = MAX_CANDIDATES,
    timeout: int = 8,
    feeds: list[str] | None = None,
    workers: int = _FETCH_WORKERS,
    on_feed_done: Callable[[], None] | None = None,
) -> list[CandidateStory]:
    """Fetch candidate stories from all RSS feeds in parallel.

    Falls back to sample_data/candidates.json if no live stories are fetched.

    on_feed_done: optional callback invoked after each feed completes (for progress bars).
    """
    feed_list = feeds if feeds is not None else RSS_FEEDS
    seen: set[str] = set()
    candidates: list[CandidateStory] = []

    logger.info("Fetching candidates from %d RSS feeds (workers=%d)…", len(feed_list), workers)

    # Fetch all feeds concurrently.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_feed = {
            pool.submit(_fetch_one_feed, feed, timeout): feed for feed in feed_list
        }
        for future in as_completed(future_to_feed):
            feed_url = future_to_feed[future]
            try:
                stories = future.result()
            except Exception as exc:
                logger.warning("Unexpected error fetching %s: %s", feed_url, exc)
                stories = []

            added = 0
            for story in stories:
                if story.url in seen:
                    continue
                seen.add(story.url)
                candidates.append(story)
                added += 1
                if added >= MAX_CANDIDATES_PER_FEED:
                    break
                if len(candidates) >= max_candidates:
                    break

            if on_feed_done is not None:
                on_feed_done()

            if len(candidates) >= max_candidates:
                break

    if candidates:
        logger.info("Fetched %d unique candidates from live feeds.", len(candidates))
        return candidates[:max_candidates]

    # Fallback to bundled sample data when all feeds are unreachable.
    fallback_path = Path("sample_data/candidates.json")
    if fallback_path.exists():
        logger.warning(
            "No live candidates fetched — falling back to %s.", fallback_path
        )
        payload = read_json(fallback_path)
        for item in payload:
            candidates.append(
                CandidateStory(
                    title=item["title"],
                    url=canonical_url(item["url"]),
                    source_domain=canonical_domain(item["url"]),
                    published_at=parse_datetime(item.get("published_at")),
                    summary=item.get("summary", ""),
                )
            )
    else:
        logger.warning("No live candidates and no fallback file found.")

    return candidates[:max_candidates]


def fetch_candidates_newsapi(
    start_date: date,
    end_date: date,
    api_key: str,
    max_results: int = 300,
) -> list[CandidateStory]:
    """Fetch AI-focused candidates from NewsAPI for a specific date range.

    Uses multiple targeted queries to get broad AI coverage while keeping every
    result anchored to an AI angle.  Full article text is not fetched here —
    that happens later via fetch_article_text(), just as with RSS candidates.

    NewsAPI free tier: last 30 days, 100 requests/day.
    Paid Developer tier: unlimited history.
    """
    # Every query must contain an AI term — no general tech drift.
    NEWSAPI_QUERIES = [
        # Core AI/ML topics
        '"artificial intelligence" OR "machine learning" OR "generative AI" OR "large language model" OR LLM',
        # Specific AI tools and products
        'ChatGPT OR "GPT-4" OR "GPT-5" OR "Claude AI" OR "Gemini AI" OR Copilot OR "AI assistant"',
        # Enterprise and workplace AI — the podcast's sweet spot
        '"enterprise AI" OR "AI adoption" OR "AI at work" OR "workplace AI" OR "AI productivity"',
        # Communications, PR, and content AI
        '"AI communications" OR "AI content" OR "AI marketing" OR "AI public relations" OR "AI journalism"',
        # AI agents and automation
        '"AI agent" OR "agentic AI" OR "AI automation" OR "AI workflow" OR "AI copilot"',
    ]

    NEWSAPI_URL = "https://newsapi.org/v2/everything"

    seen: set[str] = set()
    candidates: list[CandidateStory] = []

    for query in NEWSAPI_QUERIES:
        if len(candidates) >= max_results:
            break
        params = {
            "q": query,
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
            "language": "en",
            "sortBy": "relevancy",
            "pageSize": 100,
            "apiKey": api_key,
        }
        try:
            resp = requests.get(NEWSAPI_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") != "ok":
                logger.warning("NewsAPI error for query '%s…': %s", query[:40], data.get("message"))
                continue

            for article in data.get("articles", []):
                url = canonical_url(article.get("url", ""))
                if not url or url in seen:
                    continue

                title = (article.get("title") or "").strip()
                if not title or title == "[Removed]":
                    continue

                # Removed articles have no real content
                if article.get("source", {}).get("id") == "removed":
                    continue

                domain = canonical_domain(url)
                published_str = article.get("publishedAt")
                published_at = parse_datetime(published_str) if published_str else None
                description = (article.get("description") or "").strip()
                summary = description[:500] if description else ""

                seen.add(url)
                candidates.append(CandidateStory(
                    title=title,
                    url=url,
                    source_domain=domain,
                    published_at=published_at,
                    summary=summary,
                    full_text=None,
                ))

                if len(candidates) >= max_results:
                    break

        except requests.RequestException as exc:
            logger.warning("NewsAPI request failed for query '%s…': %s", query[:40], exc)

    logger.info(
        "NewsAPI returned %d unique AI candidates for %s–%s",
        len(candidates), start_date, end_date,
    )
    return candidates


def candidates_to_json(candidates: list[CandidateStory]) -> list[dict[str, str | None]]:
    out: list[dict[str, str | None]] = []
    for c in candidates:
        row = asdict(c)
        row["published_at"] = c.published_at.isoformat() if c.published_at else None
        out.append(row)
    return out
