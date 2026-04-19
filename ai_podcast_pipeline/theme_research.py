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
from .llm import chat_completion, parse_json_response, OpenAIError
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


_MIN_SOURCE_SCORE = 25  # Sources below this threshold are too weak to use.


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


def _llm_filter_sources(
    theme_name: str,
    candidates: list[CandidateStory],
    api_key: str,
    model: str,
    project_id: str | None = None,
    organization: str | None = None,
    max_keep: int = 8,
) -> list[int]:
    """Ask the LLM to pick the most relevant articles for a theme.

    Returns a list of 0-based indices into `candidates` that the LLM
    considers relevant. This is the key quality gate — keyword matching
    is too loose, so we let the LLM judge semantic relevance.
    """
    article_lines = []
    for idx, c in enumerate(candidates):
        pub = c.published_at.strftime("%Y-%m-%d") if c.published_at else "unknown"
        summary = (c.summary or "")[:200]
        article_lines.append(f"[{idx}] {c.title} ({c.source_domain}, {pub})\n    {summary}")

    article_block = "\n".join(article_lines)

    prompt = f"""You are selecting articles for a podcast episode about: "{theme_name}"

The podcast is for communications professionals — people who write, edit, present,
and create content at work. The episode should help them understand how AI relates
to this theme in their daily work.

Below is a list of candidate articles. Select ONLY articles that are genuinely
relevant to the theme "{theme_name}" AND relate to AI, technology, or how
professionals work. Be strict — reject articles that are:
- About unrelated products (phones, gaming, hardware reviews)
- About layoffs, funding rounds, or corporate drama
- Only tangentially connected via a shared word
- Clickbait or listicles with no substance

Return JSON with a single key "selected_indices" — an array of the index numbers
(the [N] values) of the articles worth using. Pick at most {max_keep}.
If none are relevant, return an empty array.

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
        indices = data.get("selected_indices", [])
        valid = [int(i) for i in indices if isinstance(i, (int, float)) and 0 <= int(i) < len(candidates)]
        logger.info("LLM selected %d/%d candidates for theme '%s'.", len(valid), len(candidates), theme_name)
        return valid
    except Exception as exc:
        logger.warning("LLM source filtering failed: %s — falling back to all candidates.", exc)
        return list(range(min(max_keep, len(candidates))))


# ---------------------------------------------------------------------------
# 5. RSS gathering (broad, then LLM filters)
# ---------------------------------------------------------------------------


def _gather_rss_candidates(
    on_feed_done: Callable[[], None] | None = None,
) -> list[CandidateStory]:
    """Fetch all RSS candidates. No keyword filtering — the LLM decides relevance."""
    all_candidates = fetch_candidates(on_feed_done=on_feed_done)
    logger.info("Gathered %d RSS candidates for LLM filtering.", len(all_candidates))
    return all_candidates


# ---------------------------------------------------------------------------
# 6. Main entry point
# ---------------------------------------------------------------------------


def research_theme(
    theme_name: str,
    web_results: list[CandidateStory] | None = None,
    on_feed_done: Callable[[], None] | None = None,
    on_article_done: Callable[[], None] | None = None,
    max_sources: int = 8,
    api_key: str | None = None,
    model: str | None = None,
    project_id: str | None = None,
    organization: str | None = None,
) -> list[CandidateStory]:
    """Research a theme and return the top sources with full text fetched.

    Two-pass approach:
    1. Gather a broad pool of RSS candidates + web results.
    2. Use keyword scoring to pre-filter to top ~30 candidates.
    3. LLM validates which are actually relevant (if api_key provided).
    4. Fetch full article text for the winners.
    """
    import os

    # Resolve API credentials from args or environment.
    _api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
    _model = model or os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")

    # Step 1: Gather broad RSS pool.
    rss_candidates = _gather_rss_candidates(on_feed_done=on_feed_done)

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

    # Step 4: Pre-filter with keyword scoring to top ~30 (keeps LLM prompt small).
    pre_ranked = _rank_sources(deduped, theme_name, max_results=30)

    # Step 5: LLM validation — the LLM picks the actually relevant ones.
    if _api_key and pre_ranked:
        selected_indices = _llm_filter_sources(
            theme_name=theme_name,
            candidates=pre_ranked,
            api_key=_api_key,
            model=_model,
            project_id=project_id,
            organization=organization,
            max_keep=max_sources,
        )
        final = [pre_ranked[i] for i in selected_indices]
    else:
        # No API key — fall back to keyword scoring only.
        final = pre_ranked[:max_sources]

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
