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

from pathlib import Path

from .constants import SOURCE_ALLOWLIST_BASELINE
from .ingest import fetch_article_text, fetch_candidates
from .llm import chat_completion, parse_json_response, OpenAIError
from .models import CandidateStory

logger = logging.getLogger(__name__)

_USED_ARTICLES_PATH = Path("data/used_articles.json")


def _load_used_articles() -> dict[str, list[str]]:
    """Load the used articles tracker. Returns {url: [episode_name, ...]}."""
    import json
    if _USED_ARTICLES_PATH.exists():
        try:
            return json.loads(_USED_ARTICLES_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_used_articles(used: dict[str, list[str]]) -> None:
    """Save the used articles tracker."""
    import json
    _USED_ARTICLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _USED_ARTICLES_PATH.write_text(
        json.dumps(used, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def record_used_articles(urls: list[str], episode_name: str) -> None:
    """Record that these article URLs were used in an episode."""
    used = _load_used_articles()
    for url in urls:
        if url not in used:
            used[url] = []
        if episode_name not in used[url]:
            used[url].append(episode_name)
    _save_used_articles(used)

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
        f"how to use AI for {keyword_str} internal communications",
        f"ChatGPT {keyword_str} corporate communications",
        f"generative AI {keyword_str} workplace writing",
        f"{keyword_str} AI tips for communicators",
        f"AI {keyword_str} enterprise communications 2025 2026",
    ]

    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)

    return unique


def _llm_generate_queries(
    theme_name: str,
    theme_description: str = "",
    api_key: str = "",
    model: str = "",
    project_id: str | None = None,
    organization: str | None = None,
) -> list[str]:
    """Ask the LLM to generate diverse search queries for a theme.

    Returns 8-10 queries covering different angles: practical how-to,
    research/data, adjacent concepts, industry trends, trust/ethics.
    Falls back to template-based queries on failure.
    """
    desc_line = f'\nTheme description: "{theme_description}"\n' if theme_description else ""
    prompt = f"""Generate 8-10 web search queries to find diverse, high-quality articles for a podcast episode about: "{theme_name}"
{desc_line}
The podcast is for communications professionals at a large company — they build presentations, draft speeches, write emails and newsletters, and manage digital signage. They want practical AI advice, not enterprise strategy.

Requirements for query diversity:
- Cover DIFFERENT angles: practical how-to, real examples, adjacent concepts, trends, tips
- At least 2 queries targeting adjacent concepts related to the theme that use DIFFERENT keywords (e.g., for "AI for Internal Communications": employee engagement, digital workplace, content personalization, newsletter analytics)
- 1 query with "site:reddit.com" targeting practical discussions about the theme
- Do NOT name specific companies or research firms in queries — let the search engine find the best sources naturally
- Each query should surface different sources — NO redundant keyword variations
- Keep queries concise (5-10 words each, plus any site: prefix)

Return JSON with a single key "queries" — an array of search query strings.
Do NOT include explanations or commentary — just the JSON."""

    try:
        content = chat_completion(
            api_key=api_key,
            model=model,
            messages=[
                {"role": "system", "content": "Output strict JSON only."},
                {"role": "user", "content": prompt},
            ],
            project_id=project_id,
            organization=organization,
            temperature=0.7,
        )
        data = parse_json_response(content)
        queries = data.get("queries", [])

        if not isinstance(queries, list) or len(queries) < 3:
            logger.warning("LLM returned too few queries (%s) — falling back to templates.", len(queries) if isinstance(queries, list) else "invalid")
            return _build_search_queries(theme_name)

        # Filter to valid strings and deduplicate.
        valid: list[str] = []
        seen: set[str] = set()
        for q in queries:
            if isinstance(q, str) and q.strip() and q.strip() not in seen:
                seen.add(q.strip())
                valid.append(q.strip())

        if len(valid) < 3:
            logger.warning("LLM returned too few valid queries — falling back to templates.")
            return _build_search_queries(theme_name)

        logger.info("LLM generated %d search queries for theme '%s'.", len(valid), theme_name)
        return valid

    except Exception as exc:
        logger.warning("LLM query generation failed: %s — falling back to templates.", exc)
        return _build_search_queries(theme_name)


# ---------------------------------------------------------------------------
# 1b. Web search via OpenAI Responses API
# ---------------------------------------------------------------------------

_MAX_GARTNER_SOURCES = 1  # Cap Gartner so it doesn't dominate episodes.


def _search_ddg(query: str, max_results: int = 8) -> list[dict]:
    """Run a single DuckDuckGo search and return raw results."""
    try:
        from ddgs import DDGS
        return list(DDGS().text(query, max_results=max_results, timeout=15))
    except Exception as exc:
        logger.warning("DuckDuckGo search failed for '%s': %s", query, exc)
        return []


def _web_search_for_theme(
    theme_name: str,
    theme_description: str = "",
    api_key: str = "",
    model: str = "gpt-5.4-mini",
    project_id: str | None = None,
    organization: str | None = None,
) -> list[CandidateStory]:
    """Search for articles using DuckDuckGo, one search per LLM-generated query.

    Uses a real search engine for discovery (comprehensive, fast), then the
    LLM filter downstream handles quality evaluation.
    """
    from urllib.parse import urlparse

    queries = _llm_generate_queries(
        theme_name, theme_description=theme_description,
        api_key=api_key, model=model,
        project_id=project_id, organization=organization,
    )

    logger.info(
        "Running %d web searches for theme '%s'.",
        len(queries), theme_name,
    )

    # Run queries sequentially — DuckDuckGo rate-limits concurrent requests.
    import time as _time
    all_results: list[dict] = []
    for i, q in enumerate(queries):
        results = _search_ddg(q, 8)
        all_results.extend(results)
        logger.info("  Query %d/%d: %d results", i + 1, len(queries), len(results))
        if i < len(queries) - 1:
            _time.sleep(0.5)  # Brief pause between requests

    # Convert to CandidateStory and deduplicate by URL.
    seen_urls: set[str] = set()
    candidates: list[CandidateStory] = []
    for r in all_results:
        url = r.get("href", "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        parsed = urlparse(url)
        domain = parsed.netloc.lower().removeprefix("www.")
        candidates.append(CandidateStory(
            title=r.get("title", "").strip(),
            url=url,
            source_domain=domain,
            published_at=None,
            summary=r.get("body", "").strip(),
        ))

    logger.info(
        "Web search found %d results (%d unique) for theme '%s'.",
        len(all_results), len(candidates), theme_name,
    )
    return candidates


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


_MIN_SOURCE_SCORE = 15  # Sources below this threshold are too weak to use.


def _rank_sources(
    candidates: list[CandidateStory],
    theme_name: str,
    max_results: int = 8,
) -> list[CandidateStory]:
    """Return up to *max_results* candidates ranked by theme relevance score.

    Sources scoring below _MIN_SOURCE_SCORE are filtered out entirely.
    """
    scored = [
        (c, _score_source(c.title, c.published_at, c.source_domain, theme_name))
        for c in candidates
    ]
    # Filter out low-quality matches.
    scored = [(c, s) for c, s in scored if s >= _MIN_SOURCE_SCORE]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in scored[:max_results]]


# ---------------------------------------------------------------------------
# 4. LLM-based source validation
# ---------------------------------------------------------------------------


_MAX_SUPPORTING = 8  # Cap supporting evidence articles.


def _llm_filter_sources(
    theme_name: str,
    candidates: list[CandidateStory],
    api_key: str,
    model: str,
    theme_description: str = "",
    project_id: str | None = None,
    organization: str | None = None,
    max_keep: int = 15,
) -> tuple[list[int], list[int]]:
    """Ask the LLM to pick the most relevant articles for a theme.

    Returns a tuple of (primary_indices, supporting_indices) into `candidates`.
    Primary articles are directly about the theme. Supporting articles provide
    research, data, or frameworks from authoritative sources that strengthen
    the episode even if not directly about the theme name.
    """
    used_articles = _load_used_articles()

    article_lines = []
    for idx, c in enumerate(candidates):
        pub = c.published_at.strftime("%Y-%m-%d") if c.published_at else "unknown"
        summary = (c.summary or "")[:200]
        used_in = used_articles.get(c.url, [])
        used_tag = f" ⚠️ PREVIOUSLY USED in: {', '.join(used_in)}" if used_in else ""
        article_lines.append(f"[{idx}] {c.title} ({c.source_domain}, {pub}){used_tag}\n    {summary}")

    article_block = "\n".join(article_lines)

    prompt = f"""You are selecting articles for an episode of "The Signal," an internal AI podcast at CN.

CONTEXT:
- The Signal is a short podcast (~5-6 minutes) for communications professionals at CN.
- The audience builds PowerPoint presentations for executives, drafts speeches, writes emails and newsletters, and manages digital signage content.
- They are NOT technologists. They've heard of ChatGPT, they may have tried it, but they think in terms of "I have a draft due Thursday" — not models or prompts.
- The podcast's job is to help them feel confident about AI, give them practical techniques, and keep them aware of what's changing — in that order.

THIS EPISODE'S THEME: "{theme_name}"
{f'THEME DESCRIPTION: "{theme_description}"' if theme_description else ''}
Use the theme description to understand what this episode is specifically about — score articles higher if they match the description, not just the theme name.

YOUR TASK:
Select articles that could contribute to a compelling episode about "{theme_name}". Be GENEROUS — the user will review your selections and choose which to keep. It's better to include a borderline-relevant article than to miss a good one.

Classify each selected article as PRIMARY or SUPPORTING:

**PRIMARY** — articles that are clearly relevant to "{theme_name}" or closely adjacent topics.
Think broadly: if the theme is about editing with AI, then articles about AI writing tools, AI proofreading, AI for content quality, AI revision workflows, and practical AI writing tips ALL qualify.

A good primary source:
- Covers the theme directly OR a closely related aspect of it
- Contains practical advice, insights, examples, or research a communicator could use
- Doesn't have to use the exact words of the theme — topical relevance is what matters

**SUPPORTING** — research, data, surveys, or frameworks that provide evidence or context.
These don't need to be about the theme specifically — a productivity study or trust survey
that could strengthen a point in the episode counts.

REJECT articles that are:
- Not about AI — every selected article must have a clear AI angle (AI tools, AI workflows, AI impact, AI ethics, etc.). Articles about writing or editing that don't mention AI are off-topic for this podcast.
- Product landing pages, ads, or marketing fluff with no editorial substance
- About unrelated products, funding, or corporate news with no useful insights
- Published before 2024 — prefer recent articles (2025-2026). Only include older articles if they are exceptionally relevant and still accurate.

Select generously — aim for {max_keep} or more articles across both tiers.

Note: Gartner articles ARE allowed if relevant — they'll be flagged for the user to provide full text via login.

PREVIOUSLY USED ARTICLES:
Articles marked with ⚠️ PREVIOUSLY USED have been featured in past episodes.
- Strongly prefer fresh, unused articles over previously used ones.
- Only select a previously used article if it has a genuinely different angle for THIS theme
  that wasn't explored before.
- If no unused articles are relevant, it's better to return fewer results than to reuse sources.

Return JSON with two keys:
- "primary": array of objects [{{"index": N, "relevance": 1-10}}, ...] for primary articles (at most {max_keep}), where relevance is how useful this article is for the episode (10 = perfect fit, 1 = barely relevant)
- "supporting": array of objects [{{"index": N, "relevance": 1-10}}, ...] for supporting evidence (at most {_MAX_SUPPORTING})
Sort each array by relevance descending (most relevant first).
If none are relevant in a tier, return an empty array.

Candidate articles:
{article_block}"""

    try:
        content = chat_completion(
            api_key=api_key,
            model=model,
            messages=[
                {"role": "system", "content": "Output strict JSON only."},
                {"role": "user", "content": prompt},
            ],
            project_id=project_id,
            organization=organization,
            temperature=0.1,
        )
        data = parse_json_response(content)

        # Parse scored format: [{"index": N, "relevance": 1-10}, ...]
        def _parse_scored(items: list) -> list[tuple[int, int]]:
            """Parse items into (index, relevance) tuples, sorted by relevance desc."""
            parsed = []
            for item in items:
                if isinstance(item, dict):
                    idx = item.get("index")
                    rel = item.get("relevance", 5)
                elif isinstance(item, (int, float)):
                    idx, rel = int(item), 5  # fallback for plain index
                else:
                    continue
                if isinstance(idx, (int, float)) and 0 <= int(idx) < len(candidates):
                    parsed.append((int(idx), int(rel)))
            parsed.sort(key=lambda x: x[1], reverse=True)
            return parsed

        if "primary" in data:
            scored_primary = _parse_scored(data.get("primary", []))
            scored_supporting = _parse_scored(data.get("supporting", []))
            primary = [idx for idx, _ in scored_primary]
            supporting = [idx for idx, _ in scored_supporting[:_MAX_SUPPORTING]]
            # Remove any supporting that's also in primary.
            primary_set = set(primary)
            supporting = [i for i in supporting if i not in primary_set]
            # Store relevance scores on candidates.
            score_map = {idx: rel for idx, rel in scored_primary + scored_supporting}
            for idx in primary + supporting:
                candidates[idx].relevance_score = score_map.get(idx, 5)
            logger.info(
                "LLM selected %d primary + %d supporting for theme '%s'.",
                len(primary), len(supporting), theme_name,
            )
            return primary, supporting

        # Fallback: old format (selected_indices) — treat all as primary.
        indices = data.get("selected_indices", [])
        valid = [int(i) for i in indices if isinstance(i, (int, float)) and 0 <= int(i) < len(candidates)]
        logger.info("LLM selected %d candidates (old format) for theme '%s'.", len(valid), theme_name)
        return valid, []

    except Exception as exc:
        logger.warning("LLM source filtering failed: %s — falling back to all candidates.", exc)
        return list(range(min(max_keep, len(candidates)))), []


# ---------------------------------------------------------------------------
# 6. Main entry point
# ---------------------------------------------------------------------------


def research_theme(
    theme_name: str,
    theme_description: str = "",
    web_results: list[CandidateStory] | None = None,
    on_feed_done: Callable[[], None] | None = None,
    on_article_done: Callable[[], None] | None = None,
    max_sources: int = 15,
    api_key: str | None = None,
    model: str | None = None,
    project_id: str | None = None,
    organization: str | None = None,
    **kwargs,
) -> list[CandidateStory]:
    """Research a theme and return the top sources with full text fetched.

    Search-then-filter approach:
    1. LLM generates diverse search queries for the theme.
    2. DuckDuckGo searches each query, yielding 60-80 candidates.
    3. LLM evaluates candidates and picks the best 10-15.
    4. Fetch full article text for the winners.
    """
    import os

    # Resolve API credentials from args or environment.
    _api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
    _model = model or os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
    _smart_model = os.environ.get("OPENAI_SMART_MODEL", "gpt-4.1")

    # Step 1: Web search (primary discovery).
    web_search_results = []
    if _api_key:
        logger.info("Running web search for theme '%s'…", theme_name)
        web_search_results = _web_search_for_theme(
            theme_name, theme_description=theme_description,
            api_key=_api_key, model=_smart_model,
            project_id=project_id, organization=organization,
        )

    # Step 2: Merge web search + any externally provided.
    all_candidates: list[CandidateStory] = list(web_search_results)
    if web_results:
        all_candidates.extend(web_results)

    # Step 4: Deduplicate by URL AND by title.
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    deduped: list[CandidateStory] = []
    for candidate in all_candidates:
        title_key = candidate.title.strip().lower()[:80]
        if candidate.url in seen_urls:
            continue
        if title_key and title_key in seen_titles:
            continue
        seen_urls.add(candidate.url)
        if title_key:
            seen_titles.add(title_key)
        deduped.append(candidate)
    logger.info("After dedup: %d candidates for LLM evaluation.", len(deduped))

    # Step 5: LLM validation — the LLM picks the actually relevant ones.
    # Ask for MORE than we need so the user has options to choose from.
    _llm_max_keep = max(max_sources, 15)
    if _api_key and deduped:
        primary_indices, supporting_indices = _llm_filter_sources(
            theme_name=theme_name,
            theme_description=theme_description,
            candidates=deduped,
            api_key=_api_key,
            model=_smart_model,
            project_id=project_id,
            organization=organization,
            max_keep=_llm_max_keep,
        )
        # Set source roles on candidates.
        for i in primary_indices:
            deduped[i].source_role = "primary"
        for i in supporting_indices:
            deduped[i].source_role = "supporting"
        final = [deduped[i] for i in primary_indices] + [deduped[i] for i in supporting_indices]
        # Sort by relevance score (highest first).
        final.sort(key=lambda c: c.relevance_score, reverse=True)
    else:
        final = deduped[:max_sources]

    # Step 5b: Enforce per-domain diversity — max 3 results from any single domain.
    _MAX_PER_DOMAIN = 3
    domain_counts: dict[str, int] = {}
    diverse_final: list[CandidateStory] = []
    for c in final:
        domain = c.source_domain.lower()
        count = domain_counts.get(domain, 0)
        if count < _MAX_PER_DOMAIN:
            diverse_final.append(c)
            domain_counts[domain] = count + 1
    if len(diverse_final) < len(final):
        logger.info("Source diversity cap removed %d/%d sources.", len(final) - len(diverse_final), len(final))
    final = diverse_final

    # Step 6: Fetch full text in parallel.
    with ThreadPoolExecutor(max_workers=6) as pool:
        future_to_candidate = {
            pool.submit(fetch_article_text, c.url): c for c in final
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
        "research_theme('%s'): returning %d sources", theme_name, len(final)
    )
    return final
