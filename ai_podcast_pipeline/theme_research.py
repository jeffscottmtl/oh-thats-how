"""theme_research.py — theme-first source research for The Signal.

Given a chosen theme, this module generates search queries, fetches and filters
RSS candidates, scores and ranks them for relevance, then fetches full article
text in parallel.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable

from .constants import SOURCE_ALLOWLIST_BASELINE
from .ingest import fetch_article_text, fetch_candidates
from .models import CandidateStory

logger = logging.getLogger(__name__)

# Words to strip when tokenising theme names for matching.
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "of", "in", "on", "for", "to", "with",
        "at", "by", "from", "how", "your", "our", "my", "is", "are", "was",
        "be", "as", "it", "its",
    }
)

# Practical-value trigger phrases (checked in lowercase title).
_PRACTICAL_PHRASES = [
    "how to",
    "tips",
    "guide",
    "tutorial",
    "step-by-step",
    "checklist",
    "playbook",
    "best practices",
    "use case",
    "use cases",
]

# Communications-adjacent keywords that signal audience relevance.
_COMMS_KEYWORDS = [
    "communications",
    "communicators",
    "comms",
    "public relations",
    "pr",
    "writing",
    "drafting",
    "content",
    "messaging",
    "storytelling",
    "copywriting",
    "editing",
    "presentation",
    "speech",
    "email",
    "newsletter",
    "media",
    "marketing",
    "brand",
    "reputation",
]


# ---------------------------------------------------------------------------
# 1. Query generation
# ---------------------------------------------------------------------------


def _tokenise(text: str) -> list[str]:
    """Lowercase, strip punctuation, remove stopwords."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return [w for w in words if w not in _STOPWORDS]


def _build_search_queries(theme_name: str) -> list[str]:
    """Generate 4-6 web search query strings tailored to the given theme.

    Each query includes an AI angle so results stay relevant to the podcast's
    focus on AI tools for communications professionals.
    """
    tokens = _tokenise(theme_name)
    theme_phrase = theme_name.strip()
    keyword_str = " ".join(tokens)

    queries = [
        f"AI {theme_phrase} communications professionals",
        f"AI tools for {keyword_str} at work",
        f"{keyword_str} AI productivity tips",
        f"how to use AI for {keyword_str}",
        f"generative AI {keyword_str} workplace",
        f"AI writing assistant {keyword_str}",
    ]

    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)

    return unique


# ---------------------------------------------------------------------------
# 2. Scoring
# ---------------------------------------------------------------------------


def _days_ago(published_at: datetime | None) -> float | None:
    """Return how many days ago the article was published, or None."""
    if published_at is None:
        return None
    now = datetime.now(timezone.utc)
    # Ensure published_at is timezone-aware.
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    delta = now - published_at
    return max(delta.total_seconds() / 86400, 0)


def _score_source(
    title: str,
    published_at: datetime | None,
    source_domain: str,
    theme_name: str,
) -> float:
    """Score a single source for relevance to *theme_name*.

    Scoring breakdown (max 100):
      • Relevance to theme   0–40  (10 pts per matching word, cap 4 words)
      • Freshness bias       0–25  (based on article age)
      • Credibility          0–20  (allowlist / TLD)
      • Practical value      0–15  (how-to phrases / comms keywords)
    """
    score: float = 0.0

    # ── Relevance to theme (0–40) ──────────────────────────────────────────
    theme_tokens = set(_tokenise(theme_name))
    title_tokens = set(_tokenise(title))
    overlap = theme_tokens & title_tokens
    relevance = min(len(overlap) * 10, 40)
    score += relevance

    # ── Freshness bias (0–25) ──────────────────────────────────────────────
    days = _days_ago(published_at)
    if days is None:
        freshness = 0
    elif days <= 7:
        freshness = 25
    elif days <= 30:
        freshness = 20
    elif days <= 60:
        freshness = 15
    elif days <= 90:
        freshness = 10
    else:
        # Decreasing score for older articles: 5 pts at 180d, ~0 beyond ~360d.
        freshness = max(0, 10 - int((days - 90) / 30))
    score += freshness

    # ── Credibility (0–20) ────────────────────────────────────────────────
    domain_lower = source_domain.lower()
    if domain_lower in SOURCE_ALLOWLIST_BASELINE:
        credibility = 20
    elif any(domain_lower.endswith(tld) for tld in (".edu", ".gov", ".org")):
        credibility = 15
    else:
        credibility = 0
    score += credibility

    # ── Practical value (0–15) ────────────────────────────────────────────
    title_lower = title.lower()
    if any(phrase in title_lower for phrase in _PRACTICAL_PHRASES):
        practical = 15
    elif any(re.search(rf"\b{re.escape(kw)}\b", title_lower) for kw in _COMMS_KEYWORDS):
        practical = 10
    else:
        practical = 0
    score += practical

    return score


# ---------------------------------------------------------------------------
# 3. Ranking
# ---------------------------------------------------------------------------


def _rank_sources(
    candidates: list[CandidateStory],
    theme_name: str,
    max_results: int = 8,
) -> list[CandidateStory]:
    """Return up to *max_results* candidates ranked by theme relevance score."""
    scored = sorted(
        candidates,
        key=lambda c: _score_source(c.title, c.published_at, c.source_domain, theme_name),
        reverse=True,
    )
    return scored[:max_results]


# ---------------------------------------------------------------------------
# 4. RSS filtering
# ---------------------------------------------------------------------------


def _filter_rss_for_theme(
    theme_name: str,
    on_feed_done: Callable[[], None] | None = None,
) -> list[CandidateStory]:
    """Fetch RSS feeds and return candidates that share at least one meaningful
    word with the theme name (checked against title and summary).
    """
    theme_tokens = set(_tokenise(theme_name))
    if not theme_tokens:
        return []

    all_candidates = fetch_candidates(on_feed_done=on_feed_done)

    matched: list[CandidateStory] = []
    for candidate in all_candidates:
        text = (candidate.title + " " + (candidate.summary or "")).lower()
        text_tokens = set(re.findall(r"[a-zA-Z]+", text))
        if theme_tokens & text_tokens:
            matched.append(candidate)

    logger.info(
        "RSS filter: %d/%d candidates matched theme '%s'",
        len(matched),
        len(all_candidates),
        theme_name,
    )
    return matched


# ---------------------------------------------------------------------------
# 5. Main entry point
# ---------------------------------------------------------------------------


def research_theme(
    theme_name: str,
    web_results: list[CandidateStory] | None = None,
    on_feed_done: Callable[[], None] | None = None,
    on_article_done: Callable[[], None] | None = None,
    max_sources: int = 8,
) -> list[CandidateStory]:
    """Research a theme and return the top sources with full text fetched.

    Steps:
    1. Fetch RSS candidates that match the theme.
    2. Merge with any externally-supplied *web_results*.
    3. Deduplicate by URL.
    4. Rank by theme relevance score.
    5. Fetch full article text in parallel (6 workers).
    6. Return ranked candidates (with full_text populated where possible).
    """
    # Step 1: RSS candidates matching the theme.
    rss_candidates = _filter_rss_for_theme(theme_name, on_feed_done=on_feed_done)

    # Step 2: Merge with web results.
    all_candidates: list[CandidateStory] = list(rss_candidates)
    if web_results:
        all_candidates.extend(web_results)

    # Step 3: Deduplicate by URL.
    seen_urls: set[str] = set()
    deduped: list[CandidateStory] = []
    for candidate in all_candidates:
        if candidate.url not in seen_urls:
            seen_urls.add(candidate.url)
            deduped.append(candidate)

    # Step 4: Rank by theme relevance.
    ranked = _rank_sources(deduped, theme_name, max_results=max_sources)

    # Step 5: Fetch full text in parallel.
    with ThreadPoolExecutor(max_workers=6) as pool:
        future_to_candidate = {
            pool.submit(fetch_article_text, c.url): c for c in ranked
        }
        for future in as_completed(future_to_candidate):
            candidate = future_to_candidate[future]
            try:
                candidate.full_text = future.result()
            except Exception as exc:
                logger.debug("Full-text fetch failed for %s: %s", candidate.url, exc)
                candidate.full_text = None
            if on_article_done is not None:
                on_article_done()

    logger.info(
        "research_theme('%s'): returning %d sources", theme_name, len(ranked)
    )
    return ranked
