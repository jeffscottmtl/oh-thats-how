from __future__ import annotations

import logging
import re
from datetime import datetime

from .constants import (
    AI_KEYWORDS,
    COMMS_KEYWORDS,
    EXCLUDE_KEYWORDS,
    MAX_SHORTLIST,
    PREFERRED_KEYWORDS,
    SOURCE_ALLOWLIST_BASELINE,
    WORKPLACE_KEYWORDS,
)
from .models import CandidateStory, ScoredStory
from .utils import now_toronto

logger = logging.getLogger(__name__)

WEIGHTS = {
    "ai_materiality": 0.35,
    "comms_relevance": 0.35,
    "freshness": 0.15,
    "credibility": 0.15,
}

TITLE_AI_SIGNAL_KEYWORDS = [
    "ai",
    "artificial intelligence",
    "llm",
    "generative",
    "copilot",
    "assistant",
    "chatbot",
    "automation",
    "AI agent",
    "large language model",
]

COMMS_FOCUSED_DOMAINS = {
    "prdaily.com",
    "prweek.com",
    "prmoment.com",
    "meltwater.com",
    "everything-pr.com",
    "cision.com",
    "ragan.com",
    "spinsucks.com",
    "axios.com",
    "hbr.org",
    "fastcompany.com",
}

AI_FOCUSED_DOMAINS = {
    "openai.com",
    "anthropic.com",
    "deepmind.google",
    "blog.google",
    "microsoft.com",
    "blogs.microsoft.com",
    "huggingface.co",
    "engineering.fb.com",
    "ai.meta.com",
    "simonwillison.net",
    "jack-clark.net",
    "thedeepview.substack.com",
    "therundown.substack.com",
    "lastweekin.ai",
    "venturebeat.com",
    "techcrunch.com",
    "theverge.com",
    "wired.com",
    "technologyreview.com",
    "arstechnica.com",
    "zdnet.com",
    "infoq.com",
}


def _keyword_hits(text: str, keywords: list[str]) -> int:
    lowered = text.lower()
    hits = 0
    for kw in keywords:
        kw_l = kw.lower()
        if " " in kw_l or "-" in kw_l:
            if kw_l in lowered:
                hits += 1
            continue
        if re.search(rf"\b{re.escape(kw_l)}\b", lowered):
            hits += 1
    return hits


def is_excluded(story: CandidateStory) -> bool:
    text = f"{story.title} {story.summary}"
    return _keyword_hits(text, EXCLUDE_KEYWORDS) > 0


def credibility_score(story: CandidateStory) -> int:
    if story.source_domain in SOURCE_ALLOWLIST_BASELINE:
        return 95
    if story.source_domain.endswith(".edu") or story.source_domain.endswith(".org"):
        return 80
    return 70


def comms_relevance_score(story: CandidateStory) -> int:
    text = f"{story.title} {story.summary}"
    comms_hits = _keyword_hits(text, COMMS_KEYWORDS)
    preferred_hits = _keyword_hits(text, PREFERRED_KEYWORDS)
    workplace_hits = _keyword_hits(text, WORKPLACE_KEYWORDS)
    return min(100, comms_hits * 20 + preferred_hits * 12 + workplace_hits * 10)


def freshness_score(story: CandidateStory, now: datetime | None = None) -> int:
    if story.published_at is None:
        return 30
    now = now or now_toronto()
    age_days = max(0.0, (now - story.published_at.astimezone(now.tzinfo)).total_seconds() / 86400)
    if age_days <= 1:
        return 100
    if age_days <= 3:
        return 90
    if age_days <= 7:
        return 80
    if age_days <= 14:
        return 60
    if age_days <= 30:
        return 40
    return 20


def ai_materiality_score(story: CandidateStory) -> int:
    hits = _keyword_hits(f"{story.title} {story.summary}", AI_KEYWORDS)
    return min(100, hits * 25)


def preferred_topic_score(story: CandidateStory) -> int:
    text = f"{story.title} {story.summary}"
    hits = _keyword_hits(text, PREFERRED_KEYWORDS)
    workplace_hits = _keyword_hits(text, WORKPLACE_KEYWORDS)
    return min(100, hits * 18 + workplace_hits * 14)


def _relevance_gate(scored: ScoredStory) -> bool:
    """Strict gate: strong AI signal + solid comms relevance + min total."""
    title = scored.candidate.title
    title_ai_signal = _keyword_hits(title, TITLE_AI_SIGNAL_KEYWORDS) >= 1
    strong_ai_signal = scored.ai_materiality >= 50
    return (
        scored.ai_materiality >= 25
        and (title_ai_signal or strong_ai_signal)
        and scored.comms_relevance >= 20
        and scored.total >= 45
    )


def _relaxed_relevance_gate(scored: ScoredStory) -> bool:
    """Relaxed gate: slightly lower thresholds for borderline strong stories."""
    title = scored.candidate.title
    title_ai_signal = _keyword_hits(title, TITLE_AI_SIGNAL_KEYWORDS) >= 1
    return (
        scored.ai_materiality >= 25
        and (title_ai_signal or scored.ai_materiality >= 50)
        and (scored.comms_relevance >= 10 or scored.ai_materiality >= 50)
        and scored.total >= 38
    )


def _broad_relevance_gate(scored: ScoredStory) -> bool:
    """Broad gate: domain authority lifts the bar; catches AI-forward outlets."""
    title = scored.candidate.title
    title_ai_signal = _keyword_hits(title, TITLE_AI_SIGNAL_KEYWORDS) >= 1
    domain = scored.candidate.source_domain
    domain_ai_signal = domain in AI_FOCUSED_DOMAINS
    return (
        (scored.ai_materiality >= 20 or title_ai_signal or domain_ai_signal)
        and (
            scored.comms_relevance >= 10
            or domain in COMMS_FOCUSED_DOMAINS
            or domain_ai_signal
        )
        and scored.total >= 28
    )


def is_relevant_story(scored: ScoredStory) -> bool:
    return _relevance_gate(scored) or _relaxed_relevance_gate(scored) or _broad_relevance_gate(scored)


def story_sort_key(item: ScoredStory) -> tuple[float, float, int, str]:
    """Canonical sort key: highest total score first, then newest, then credibility, then URL."""
    published = item.candidate.published_at
    timestamp = published.timestamp() if published else -1.0
    return (-item.total, -timestamp, -item.credibility, item.candidate.url)


def score_story(story: CandidateStory, reference_date: datetime | None = None) -> ScoredStory:
    """Score a story.

    reference_date: the date to measure freshness against — use the search
    window's end date so historical queries aren't unfairly penalised.
    Defaults to now (correct for live/current-week use).
    """
    cred = credibility_score(story)
    comms = comms_relevance_score(story)
    fresh = freshness_score(story, now=reference_date)
    ai = ai_materiality_score(story)
    total = (
        WEIGHTS["ai_materiality"] * ai
        + WEIGHTS["comms_relevance"] * comms
        + WEIGHTS["freshness"] * fresh
        + WEIGHTS["credibility"] * cred
    )
    scored = ScoredStory(
        candidate=story,
        credibility=cred,
        comms_relevance=comms,
        freshness=fresh,
        ai_materiality=ai,
        preferred_topic=0,
        total=round(total, 4),
    )
    logger.debug(
        "Scored '%s' → total=%.2f (ai=%d comms=%d fresh=%d cred=%d)",
        story.title[:60],
        scored.total,
        ai,
        comms,
        fresh,
        cred,
    )
    return scored
