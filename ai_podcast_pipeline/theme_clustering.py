"""Theme clustering: group scored articles into theme candidates for episode selection."""
from __future__ import annotations

import logging
from typing import Any

from .llm import chat_completion, parse_json_response, OpenAIError
from .models import ScoredStory, ThemeCandidate
from .script_writer import _pub_name

logger = logging.getLogger(__name__)

AUDIENCE_CONTEXT = (
    "The audience is communications professionals who build presentations for executives, "
    "draft speeches for leaders to deliver at town halls and events, write emails and newsletters, "
    "and manage digital signage. "
    "They want to know how AI can help their daily work — not enterprise deployment strategy."
)


def _build_clustering_prompt(scored_articles: list[ScoredStory]) -> str:
    article_lines = []
    for idx, s in enumerate(scored_articles, start=1):
        c = s.candidate
        pub = _pub_name(c.source_domain)
        article_lines.append(f"[{idx}] {c.title} ({pub}) — {c.summary[:200]}")
    article_block = "\n".join(article_lines)

    return f"""You are helping produce a weekly podcast for communicators — people who write,
present, draft, and edit content daily at a large organization.

{AUDIENCE_CONTEXT}

Below is a list of this week's top articles about AI and communications. Group them into
3-5 theme clusters. Each theme should be:
- Named in plain, non-technical language (e.g., "Getting unstuck on first drafts" not "LLM-assisted content generation")
- Relevant to the audience's daily work
- Supported by 2-4 articles from the list

Return JSON with a single key "themes", which is an array of objects with keys:
- "name": short plain-English theme name
- "description": one sentence explaining why this theme matters to communicators
- "article_indices": array of article numbers from the list below

Articles:
{article_block}
"""


def cluster_themes(
    api_key: str,
    model: str,
    scored_articles: list[ScoredStory],
    project_id: str | None = None,
    organization: str | None = None,
) -> list[ThemeCandidate]:
    """Cluster scored articles into 3-5 theme candidates."""
    prompt = _build_clustering_prompt(scored_articles)
    logger.info("Clustering %d articles into themes via %s…", len(scored_articles), model)

    content = chat_completion(
        api_key=api_key,
        model=model,
        messages=[
            {"role": "system", "content": "Output strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        project_id=project_id,
        organization=organization,
        temperature=0.3,
    )
    data = parse_json_response(content)
    raw_themes = data.get("themes", [])
    if not isinstance(raw_themes, list) or len(raw_themes) < 1:
        raise OpenAIError("Theme clustering returned no themes")

    themes: list[ThemeCandidate] = []
    for t in raw_themes:
        name = t.get("name", "").strip()
        desc = t.get("description", "").strip()
        indices = t.get("article_indices", [])
        if name and indices:
            themes.append(ThemeCandidate(
                name=name,
                description=desc,
                article_indices=[int(i) for i in indices],
            ))

    logger.info("Found %d theme candidates.", len(themes))
    return themes
