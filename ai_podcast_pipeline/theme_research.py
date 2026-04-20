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
        "be", "as", "it", "its", "not", "no", "but", "that", "this", "what",
        "when", "who", "can", "will", "do", "don", "does", "did", "has", "have",
        "had", "get", "got", "one", "use", "just", "like", "into", "over",
        "out", "up", "down", "off", "need", "without", "before", "after",
        "same", "different", "every", "each", "all", "any", "some", "more",
        "other", "new", "way", "make", "start", "starting", "stop", "thing",
        "work", "put", "take", "keep", "let", "hit", "send", "set",
        "piece", "catch",
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
    """Generate search queries by asking the LLM to think like a communicator.

    Instead of keyword combos, generates natural-language questions that a
    communications professional would type into Google when looking for help
    with this topic + AI. This produces much more contextual search results.
    Falls back to template-based queries on failure.
    """
    desc_line = f'\nTopic description: "{theme_description}"\n' if theme_description else ""
    prompt = f"""You are a communications professional at a large company. You build presentations for executives, draft speeches for town halls, write emails and newsletters, and manage digital signage.

You're preparing a podcast episode about: "{theme_name}"
{desc_line}
You need to find 10-12 articles about how AI can help with this specific aspect of your work.

Write the Google searches you would type — natural questions, not keyword combos.

Examples of GOOD queries (natural, contextual, specific):
- "how internal comms teams use AI to adapt messages for different audiences"
- "using ChatGPT to rewrite corporate announcements for executives vs frontline employees"
- "communications professional shares experience using AI for tone adjustment"
- "case study AI tailoring employee newsletter content"

Examples of BAD queries (keyword soup, too generic):
- "AI audience tone rewrite"
- "ChatGPT communications tools"
- "generative AI content adaptation"

Rules:
- Each query must naturally include AI/ChatGPT/Claude/Copilot or similar
- Each query must include communications context (not generic marketing/sales)
- Cover different angles: how-to, case studies, lessons learned, tips, trends
- Include 1 query with "site:reddit.com"
- No two queries should find the same articles

Return JSON: {{"queries": ["query1", "query2", ...]}}"""

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


def _search_tavily(query: str, max_results: int = 10) -> list[dict]:
    """Run a Tavily search with advanced depth and return results.

    Uses advanced search depth for highest relevance, excludes known
    product/tool domains at the search level, and returns Tavily's
    semantic relevance score alongside each result.
    """
    import os
    try:
        from tavily import TavilyClient
        api_key = os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            logger.warning("TAVILY_API_KEY not set — falling back to DuckDuckGo.")
            return _search_ddg_fallback(query, max_results)
        client = TavilyClient(api_key=api_key)
        results = client.search(
            query,
            max_results=max_results,
            search_depth="advanced",
            include_answer=False,
            time_range="year",
            exclude_domains=[
                "jasper.ai", "writesonic.com", "copy.ai", "quillbot.com",
                "grammarly.com", "wordtune.com", "slidesai.io", "gamma.app",
                "logicballs.com", "ahrefs.com", "semrush.com",
            ],
        )
        return [
            {
                "title": r.get("title", ""),
                "href": r.get("url", ""),
                "body": r.get("content", ""),
                "tavily_score": r.get("score", 0),
            }
            for r in results.get("results", [])
        ]
    except Exception as exc:
        logger.warning("Tavily search failed for '%s': %s — trying DuckDuckGo.", query, exc)
        return _search_ddg_fallback(query, max_results)


def _search_ddg_fallback(query: str, max_results: int = 8) -> list[dict]:
    """Fallback: DuckDuckGo search if Tavily is unavailable."""
    try:
        from ddgs import DDGS
        return list(DDGS().text(query, max_results=max_results, timeout=15))
    except Exception as exc:
        logger.warning("DuckDuckGo fallback also failed for '%s': %s", query, exc)
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

    # Generate queries from two sources for maximum coverage.
    llm_queries = _llm_generate_queries(
        theme_name, theme_description=theme_description,
        api_key=api_key, model=model,
        project_id=project_id, organization=organization,
    )

    # Add natural-language direct queries as baseline coverage.
    direct_queries = [
        f"how communicators use AI for {theme_name.lower()}",
        f"using ChatGPT for {theme_name.lower()} in corporate communications",
    ]
    if theme_description:
        direct_queries.append(f"AI {theme_description.lower()[:60]}")

    # Combine, deduplicate, ensure AI in each.
    _AI_QUERY_TERMS = {"ai", "chatgpt", "gpt", "claude", "copilot", "gemini",
                       "mistral", "anthropic", "openai", "generative", "llm"}
    seen_q: set[str] = set()
    queries: list[str] = []
    for q in direct_queries + llm_queries:
        if not any(term in q.lower() for term in _AI_QUERY_TERMS):
            q = f"AI {q}"
        if q.lower() not in seen_q:
            seen_q.add(q.lower())
            queries.append(q)

    logger.info(
        "Running %d web searches for theme '%s'.",
        len(queries), theme_name,
    )

    # Run queries sequentially — DuckDuckGo rate-limits concurrent requests.
    import time as _time
    all_results: list[dict] = []
    for i, q in enumerate(queries):
        results = _search_tavily(q, 10)
        all_results.extend(results)
        logger.info("  Query %d/%d: %d results", i + 1, len(queries), len(results))
        if i < len(queries) - 1:
            _time.sleep(0.5)  # Brief pause between requests

    # Convert to CandidateStory and deduplicate by URL.
    # Keep highest Tavily score when deduping (same URL from multiple queries).
    seen_urls: dict[str, float] = {}  # url → best tavily score
    candidates: list[CandidateStory] = []
    for r in all_results:
        url = r.get("href", "").strip()
        if not url:
            continue
        tavily_score = r.get("tavily_score", 0)
        if url in seen_urls:
            # Keep the higher score if we've seen this URL before
            if tavily_score > seen_urls[url]:
                seen_urls[url] = tavily_score
                # Update the existing candidate's score
                for c in candidates:
                    if c.url == url:
                        c.relevance_score = tavily_score
                        break
            continue
        seen_urls[url] = tavily_score
        parsed = urlparse(url)
        domain = parsed.netloc.lower().removeprefix("www.")
        candidates.append(CandidateStory(
            title=r.get("title", "").strip(),
            url=url,
            source_domain=domain,
            published_at=None,
            summary=r.get("body", "").strip(),
            relevance_score=tavily_score,  # raw 0-1, normalized later
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
# 4. Keyword-based relevance scoring (replaces LLM-as-judge)
# ---------------------------------------------------------------------------

# AI signals — articles must mention at least one to be included.
_AI_SIGNALS = frozenset({
    "ai", "artificial intelligence", "llm", "chatgpt", "generative",
    "machine learning", "copilot", "gpt", "claude", "gemini",
    "large language model", "automation", "chatbot", "openai", "anthropic",
})


# Synonym map — common comms/writing terms and their related words.
# When a theme mentions one of these, all synonyms get added as keywords.
_SYNONYM_GROUPS: list[set[str]] = [
    {"edit", "editing", "editor", "proofread", "proofreading", "revise", "revision",
     "copyedit", "grammar", "polish", "refine", "correct", "rewrite"},
    {"audience", "audiences", "segment", "tailor", "personalize", "customize",
     "target", "adapt", "stakeholder", "stakeholders", "reader", "readers"},
    {"tone", "voice", "style", "register", "formal", "informal", "conversational"},
    {"draft", "drafting", "write", "writing", "writer", "compose", "create"},
    {"email", "emails", "inbox", "subject", "newsletter", "newsletters"},
    {"presentation", "presentations", "slides", "deck", "powerpoint", "keynote"},
    {"speech", "speeches", "remarks", "talking", "speaking", "town hall"},
    {"summarize", "summary", "summarizing", "distill", "condense", "briefing", "digest"},
    {"brainstorm", "brainstorming", "ideation", "ideas", "angles", "concepts", "creative"},
    {"feedback", "revisions", "review", "collaborate", "collaboration", "iterate"},
    {"measure", "measurement", "metrics", "analytics", "engagement", "performance", "roi"},
    {"crisis", "urgent", "rapid", "response", "incident", "statement"},
    {"change", "transformation", "transition", "announcement", "restructure"},
    {"trust", "credibility", "transparency", "ethics", "bias", "hallucination", "accuracy"},
    {"prompt", "prompts", "prompting", "instruction", "technique", "workflow"},
    {"personalize", "personalization", "segment", "segmentation", "targeted", "relevant"},
    {"frontline", "executive", "executives", "leadership", "management", "employee", "employees"},
    {"repurpose", "repurposing", "multichannel", "channel", "channels", "format", "formats"},
    {"signage", "display", "screen", "screens", "visual", "visuals", "graphic", "graphics"},
    {"research", "synthesis", "analyze", "analysis", "findings", "insights", "data"},
]


def _generate_theme_keywords(
    theme_name: str,
    theme_description: str,
    **kwargs,
) -> list[str]:
    """Generate relevance keywords for a theme using synonym expansion.

    Extracts words from the theme name + description, then expands each
    word through the synonym map to produce a broad keyword set.
    No LLM call needed — fast and deterministic.
    """
    # Extract meaningful words from theme name + description.
    source_words = set(_tokenise(f"{theme_name} {theme_description}"))

    # Expand through synonym groups.
    expanded: set[str] = set(source_words)
    for group in _SYNONYM_GROUPS:
        if source_words & group:  # any overlap?
            expanded |= group

    keywords = sorted(expanded)
    logger.info("Generated %d keywords for '%s' (from %d source words).",
                len(keywords), theme_name, len(source_words))
    return keywords


def _score_candidate(
    candidate: CandidateStory,
    theme_keywords: list[str],
) -> int:
    """Score a candidate article for relevance.

    The podcast is about AI FOR COMMUNICATORS. Every article must be about
    BOTH — using AI AND a communications topic. Articles about only comms
    (no AI) or only AI (no comms relevance) score zero.

    Returns 0 (reject) or 1-100 (higher = more relevant).
    """
    title = candidate.title.lower()
    summary = (candidate.summary or "").lower()
    text = f"{title} {summary}"

    # ── GATE 1: Must mention AI ────────────────────────────────────────
    # No AI = no use for this podcast. Hard reject.
    has_ai = any(re.search(rf"\b{re.escape(s)}\b", text) for s in _AI_SIGNALS)
    if not has_ai:
        return 0

    # ── GATE 2: Must match the topic ───────────────────────────────────
    # At least 1 theme keyword in the title, or 2+ in the summary.
    title_hits = sum(1 for kw in theme_keywords if kw in title)
    summary_hits = sum(1 for kw in theme_keywords if kw in summary)
    if title_hits == 0 and summary_hits < 2:
        return 0

    # ── GATE 3: Not a product page ─────────────────────────────────────
    _product_signals = [
        "free online", "no sign-up", "no signup", "sign up free", "try for free",
        "start free", "pricing", "free trial", "free ai", "no login",
        "unlimited words", "get started", "try it now", "start now",
        "sign up", "create account", "free plan",
        "paraphrasing tool", "paraphraser", "rewriter tool", "rewording tool",
        "humanizer",
        "photo editor", "photo editing", "image editor", "image editing",
        "video editor", "video editing", "code editing", "code editor",
        "presentation maker", "slide maker", "slide generator",
        "grammar checker", "email generator", "brainstorm generator",
    ]
    if any(s in text for s in _product_signals):
        return 0

    # .ai domains with promotional language are product sites
    domain = candidate.source_domain.lower()
    _LEGIT_AI_DOMAINS = {"openai.com", "anthropic.com", "ai.meta.com", "deepmind.google"}
    if domain.endswith(".ai") and domain not in _LEGIT_AI_DOMAINS:
        promo = sum(1 for s in ["tool", "generate", "create", "build", "maker",
                                "transform", "convert"] if s in text)
        if promo >= 2:
            return 0

    # ── GATE 4: Must be about communications/professional work ────────
    # Rejects generic AI tutorials ("ChatGPT settings guide") that match
    # topic keywords by accident but aren't about workplace communications.
    _COMMS_CONTEXT = [
        "communicat", "comms", "corporate", "internal", "employee",
        "stakeholder", "workplace", "business writing", "professional",
        "newsletter", "presentation", "speech", "email",
        "pr ", "public relations", "content strategy", "messaging",
        "team", "organization", "leadership", "executive",
        "writer", "writing", "draft", "publish", "editing", "editor",
        "proofread", "revision", "copywriting", "content creation",
        "brainstorm", "headline", "storytelling", "brief",
    ]
    has_comms_context = any(s in text for s in _COMMS_CONTEXT)
    if not has_comms_context:
        return 0

    # ── SCORE: How relevant is it? ─────────────────────────────────────
    # Simple: count keyword matches. Title matches worth more.
    score = title_hits * 6 + summary_hits * 2

    return max(score, 1)


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
    _smart_model = os.environ.get("OPENAI_SMART_MODEL", "gpt-5.4")

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
    logger.info("After dedup: %d candidates for scoring.", len(deduped))

    # Step 3: Generate theme-specific relevance keywords (used as quality gates).
    theme_keywords = _generate_theme_keywords(theme_name, theme_description)
    logger.info("Theme keywords: %s", theme_keywords[:10])

    # Step 4: Gate check + sort by Tavily's semantic score.
    scored = []
    for c in deduped:
        gate_score = _score_candidate(c, theme_keywords)
        if gate_score > 0:
            scored.append((c, c.relevance_score))
    scored.sort(key=lambda x: x[1], reverse=True)

    # Normalize Tavily scores (0.0-1.0) to 1-10 using the actual range.
    if scored:
        raw_scores = [s for _, s in scored]
        lo, hi = min(raw_scores), max(raw_scores)
        spread = hi - lo if hi > lo else 1.0
        for c, _ in scored:
            c.relevance_score = max(1, min(10, round(1 + 9 * (c.relevance_score - lo) / spread)))

    # Take top results (max 20 for user to browse).
    _MAX_RESULTS = 25
    final = [c for c, _ in scored[:_MAX_RESULTS]]
    logger.info(
        "Keyword scoring: %d passed AI gate from %d, showing top %d.",
        len(scored), len(deduped), len(final),
    )

    # Step 4b: Enforce per-domain diversity — max 3 results from any single domain.
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

    # Step 5: LLM cleanup — remove obviously wrong articles from the shortlist.
    # The keyword scoring is good but can't catch everything. A quick LLM pass
    # on 15-25 pre-filtered articles is fast and catches the last few misfits.
    if _api_key and final:
        article_list = "\n".join(
            f"[{i}] {c.title} ({c.source_domain})\n    {(c.summary or '')[:150]}"
            for i, c in enumerate(final)
        )
        desc_ctx = f'\nTopic description: "{theme_description}"' if theme_description else ""
        cleanup_prompt = (
            f'The podcast topic is: "{theme_name}"{desc_ctx}\n\n'
            f"This podcast helps communicators at a large company use AI in their daily work "
            f"(presentations, speeches, emails, newsletters, digital signage).\n\n"
            f"Review this shortlist and REMOVE any article that:\n"
            f"- Is NOT about using AI to help with communications work\n"
            f"- Is a product page, tool demo, or SaaS marketing\n"
            f"- Is about a different field (marketing automation, sales, HR, engineering)\n"
            f"- Is a generic AI tutorial not specific to professional communications\n\n"
            f"Return JSON: {{\"keep\": [list of index numbers to KEEP]}}\n\n"
            f"Articles:\n{article_list}"
        )
        try:
            content = chat_completion(
                api_key=_api_key, model=_smart_model,
                messages=[
                    {"role": "system", "content": "Output strict JSON only."},
                    {"role": "user", "content": cleanup_prompt},
                ],
                project_id=project_id, organization=organization,
                temperature=0.1,
            )
            data = parse_json_response(content)
            keep_indices = data.get("keep", [])
            if isinstance(keep_indices, list) and len(keep_indices) >= 3:
                kept = [final[int(i)] for i in keep_indices if isinstance(i, (int, float)) and 0 <= int(i) < len(final)]
                if len(kept) >= 3:
                    logger.info("LLM cleanup: kept %d/%d articles.", len(kept), len(final))
                    final = kept
        except Exception as exc:
            logger.warning("LLM cleanup failed: %s — keeping all.", exc)

    # Step 6: Fetch full text via Tavily extract (handles JS pages, returns markdown).
    # Falls back to basic HTML fetch if Tavily extract fails.
    import os as _os
    tavily_key = _os.environ.get("TAVILY_API_KEY", "")
    if tavily_key and final:
        try:
            from tavily import TavilyClient
            _tavily = TavilyClient(api_key=tavily_key)
            urls = [c.url for c in final]
            # Tavily extract handles up to 20 URLs per call.
            for batch_start in range(0, len(urls), 20):
                batch_urls = urls[batch_start:batch_start + 20]
                try:
                    extracted = _tavily.extract(urls=batch_urls)
                    for result in extracted.get("results", []):
                        url = result.get("url", "")
                        text = result.get("raw_content", "") or result.get("text", "")
                        for c in final:
                            if c.url == url and text:
                                c.full_text = text[:15000]  # cap to avoid massive texts
                                break
                except Exception as exc:
                    logger.warning("Tavily extract batch failed: %s", exc)
            logger.info("Tavily extracted text for %d/%d articles.",
                        sum(1 for c in final if c.full_text), len(final))
        except ImportError:
            logger.warning("tavily-python not installed — falling back to basic fetch.")

    # Fallback: fetch any articles that Tavily didn't extract.
    missing = [c for c in final if not c.full_text]
    if missing:
        logger.info("Fetching %d remaining articles with basic HTML parser.", len(missing))
        with ThreadPoolExecutor(max_workers=6) as pool:
            future_to_candidate = {
                pool.submit(fetch_article_text, c.url): c for c in missing
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
