from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CandidateStory:
    title: str
    url: str
    source_domain: str
    published_at: datetime | None
    summary: str
    full_text: str | None = None  # fetched after user selection; None = not yet fetched


@dataclass
class ScoredStory:
    candidate: CandidateStory
    credibility: int
    comms_relevance: int
    freshness: int
    ai_materiality: int
    preferred_topic: int
    total: float


@dataclass
class VerificationResult:
    story: ScoredStory
    passed: bool
    reason: str | None = None


@dataclass
class ThemeCandidate:
    name: str
    description: str
    article_indices: list[int]


@dataclass
class ScriptParts:
    # Theme-based fields (used by new theme pipeline)
    theme_name: str = ""
    narrative: str = ""
    try_this: str = ""
    # Shared
    food_for_thought: str = ""
    cn_relevance: str | None = None
    # Legacy news-roundup fields (kept for backward compat)
    story_narratives: list[str] = field(default_factory=list)


@dataclass
class QaResult:
    passed: bool
    checks: dict[str, bool]
    failures: list[str]


@dataclass
class RunArtifacts:
    script_md: str
    script_json: str
    sources_json: str
    cover_png: str
    mp3: str | None
    manifest_json: str


@dataclass
class Manifest:
    episode_name: str
    episode_number: int
    timezone: str
    created_at: str
    run_status: str
    selected_story_indices: list[int]
    selected_count: int
    files: dict[str, str | None]
    qa: dict[str, Any]
    notes: list[str] = field(default_factory=list)
