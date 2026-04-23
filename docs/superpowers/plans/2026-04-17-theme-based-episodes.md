# Theme-Based Episodes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert The Signal from a news-roundup format (3-5 individual story summaries) to theme-based episodes (one topic explored deeply through 2-4 supporting sources).

**Architecture:** The pipeline keeps its existing RSS ingestion and scoring. A new theme-clustering stage (LLM call via gpt-5.4-mini) groups scored articles into theme candidates. The user picks a theme. A rewritten script_writer synthesizes the theme's articles into one cohesive narrative using gpt-5.4. The assembly layer drops per-story transitions and cn_relevance in favor of a continuous flow with a "try this" segment.

**Tech Stack:** Python 3.14, OpenAI API (gpt-5.4 + gpt-5.4-mini), existing pipeline infrastructure (feedparser, requests, Pillow, Rich).

---

### Task 1: Add ThemeCandidate model and update ScriptParts

**Files:**
- Modify: `ai_podcast_pipeline/models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_models_theme.py`:

```python
"""Tests for theme-based models."""
import unittest
from ai_podcast_pipeline.models import ThemeCandidate, ScriptParts


class TestThemeCandidate(unittest.TestCase):
    def test_create_theme_candidate(self):
        tc = ThemeCandidate(
            name="Getting unstuck on first drafts",
            description="How AI can help communicators break through writer's block",
            article_indices=[3, 7, 12],
        )
        self.assertEqual(tc.name, "Getting unstuck on first drafts")
        self.assertEqual(len(tc.article_indices), 3)

    def test_script_parts_theme_fields(self):
        parts = ScriptParts(
            theme_name="Getting unstuck on first drafts",
            narrative="Full episode narrative here.",
            try_this="Next time you're stuck, try giving AI three bullet points...",
            food_for_thought="Here's some food for thought. I've been thinking...",
        )
        self.assertEqual(parts.theme_name, "Getting unstuck on first drafts")
        self.assertIsNotNone(parts.try_this)
        self.assertIsNone(parts.cn_relevance)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3 -m unittest tests.test_models_theme -v`
Expected: ImportError or AttributeError (ThemeCandidate doesn't exist yet)

- [ ] **Step 3: Update models.py**

Replace the `ScriptParts` dataclass and add `ThemeCandidate`:

```python
@dataclass
class ThemeCandidate:
    name: str
    description: str
    article_indices: list[int]  # indices into the scored article list


@dataclass
class ScriptParts:
    theme_name: str
    narrative: str              # the full episode body (theme intro + angles + why it matters)
    try_this: str               # one concrete technique to try
    food_for_thought: str
    cn_relevance: str | None = None  # kept for backward compat but not used in theme mode
    story_narratives: list[str] = field(default_factory=list)  # kept for backward compat
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python3 -m unittest tests.test_models_theme -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add ai_podcast_pipeline/models.py tests/test_models_theme.py
git commit -m "feat: add ThemeCandidate model, update ScriptParts for theme-based episodes"
```

---

### Task 2: Add dual-model config (script model vs clustering model)

**Files:**
- Modify: `ai_podcast_pipeline/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Add OPENAI_SCRIPT_MODEL to Settings**

In `config.py`, add a new field to the `Settings` dataclass:

```python
    openai_script_model: str  # model for script generation (defaults to gpt-5.4)
```

In `load_settings()`, after the existing `openai_model` parsing, add:

```python
    openai_script_model = os.environ.get("OPENAI_SCRIPT_MODEL", "gpt-5.4")
```

Pass it through to the Settings constructor.

- [ ] **Step 2: Update .env.example**

Add after the OPENAI_MODEL line:

```
OPENAI_SCRIPT_MODEL=gpt-5.4
```

- [ ] **Step 3: Verify existing tests still pass**

Run: `.venv/bin/python3 -m unittest discover -s tests -p 'test_*.py' -v 2>&1 | tail -5`
Expected: Same pass/fail count as before (122 tests, 3 pre-existing failures)

- [ ] **Step 4: Commit**

```bash
git add ai_podcast_pipeline/config.py .env.example
git commit -m "feat: add OPENAI_SCRIPT_MODEL config for dual-model support"
```

---

### Task 3: Implement theme clustering

**Files:**
- Create: `ai_podcast_pipeline/theme_clustering.py`
- Create: `tests/test_theme_clustering.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_theme_clustering.py`:

```python
"""Tests for theme clustering."""
import unittest
import json
from unittest.mock import patch
from datetime import datetime, timezone

from ai_podcast_pipeline.models import CandidateStory, ScoredStory, ThemeCandidate
from ai_podcast_pipeline.theme_clustering import cluster_themes, _build_clustering_prompt


def _make_scored(title, summary, domain="techcrunch.com", idx=0):
    c = CandidateStory(
        title=title, url=f"https://{domain}/art{idx}",
        source_domain=domain, published_at=datetime.now(timezone.utc),
        summary=summary,
    )
    return ScoredStory(candidate=c, credibility=90, comms_relevance=50,
                       freshness=80, ai_materiality=60, preferred_topic=0, total=55.0)


class TestBuildClusteringPrompt(unittest.TestCase):
    def test_prompt_contains_all_titles(self):
        articles = [
            _make_scored("AI helps writers draft faster", "Tools for first drafts", idx=1),
            _make_scored("New Claude model released", "Anthropic ships update", idx=2),
        ]
        prompt = _build_clustering_prompt(articles)
        self.assertIn("AI helps writers draft faster", prompt)
        self.assertIn("New Claude model released", prompt)
        self.assertIn("communicators", prompt.lower())

    def test_prompt_includes_indices(self):
        articles = [_make_scored(f"Story {i}", f"Summary {i}", idx=i) for i in range(5)]
        prompt = _build_clustering_prompt(articles)
        self.assertIn("[1]", prompt)
        self.assertIn("[5]", prompt)


class TestClusterThemes(unittest.TestCase):
    @patch("ai_podcast_pipeline.theme_clustering.chat_completion")
    def test_parses_valid_response(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "themes": [
                {
                    "name": "AI for first drafts",
                    "description": "How AI helps communicators get past the blank page",
                    "article_indices": [1, 3],
                },
                {
                    "name": "Choosing the right AI tool",
                    "description": "What to look for when picking AI tools for content work",
                    "article_indices": [2, 4, 5],
                },
            ]
        })
        articles = [_make_scored(f"Story {i}", f"Summary {i}", idx=i) for i in range(5)]
        themes = cluster_themes(
            api_key="test", model="gpt-5.4-mini", scored_articles=articles,
        )
        self.assertEqual(len(themes), 2)
        self.assertEqual(themes[0].name, "AI for first drafts")
        self.assertEqual(themes[0].article_indices, [1, 3])
        self.assertIsInstance(themes[0], ThemeCandidate)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3 -m unittest tests.test_theme_clustering -v`
Expected: ImportError (module doesn't exist)

- [ ] **Step 3: Implement theme_clustering.py**

Create `ai_podcast_pipeline/theme_clustering.py`:

```python
"""Theme clustering: group scored articles into theme candidates for episode selection."""
from __future__ import annotations

import logging
from typing import Any

from .llm import chat_completion, parse_json_response, OpenAIError
from .models import ScoredStory, ThemeCandidate
from .script_writer import _pub_name

logger = logging.getLogger(__name__)

AUDIENCE_CONTEXT = (
    "The audience is communications professionals who write stories, build presentations, "
    "draft speeches, create emails, and manage content like intranets and digital signage. "
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python3 -m unittest tests.test_theme_clustering -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add ai_podcast_pipeline/theme_clustering.py tests/test_theme_clustering.py
git commit -m "feat: add theme clustering module for grouping articles by topic"
```

---

### Task 4: Rewrite script_writer for theme-based synthesis

**Files:**
- Modify: `ai_podcast_pipeline/script_writer.py`
- Create: `tests/test_theme_script_writer.py`

This is the largest task. The generate_script_parts function gets a new companion `generate_theme_script` and `build_theme_script_markdown` replaces `build_script_markdown` for theme episodes.

- [ ] **Step 1: Write the failing test**

Create `tests/test_theme_script_writer.py`:

```python
"""Tests for theme-based script generation."""
import unittest
import json
from unittest.mock import patch
from datetime import datetime, timezone

from ai_podcast_pipeline.models import CandidateStory, ScoredStory, ScriptParts
from ai_podcast_pipeline.script_writer import (
    generate_theme_script,
    build_theme_script_markdown,
)
from ai_podcast_pipeline.constants import INTRO_TEXT, OUTRO_TEXT


def _make_scored(title, summary, domain="wired.com", full_text="Full article content here."):
    c = CandidateStory(
        title=title, url=f"https://{domain}/art",
        source_domain=domain,
        published_at=datetime.now(timezone.utc),
        summary=summary, full_text=full_text,
    )
    return ScoredStory(candidate=c, credibility=90, comms_relevance=50,
                       freshness=80, ai_materiality=60, preferred_topic=0, total=55.0)


class TestBuildThemeScriptMarkdown(unittest.TestCase):
    def test_contains_intro_and_outro(self):
        parts = ScriptParts(
            theme_name="AI for first drafts",
            narrative="The body of the episode goes here.",
            try_this="Try giving AI three bullet points and asking for five openings.",
            food_for_thought="Here's a parting thought about drafts.",
        )
        md = build_theme_script_markdown(parts)
        self.assertIn(INTRO_TEXT, md)
        self.assertIn(OUTRO_TEXT, md)
        self.assertIn("The body of the episode goes here.", md)
        self.assertIn("Try giving AI three bullet points", md)
        self.assertIn("parting thought about drafts", md)

    def test_no_per_story_transitions(self):
        parts = ScriptParts(
            theme_name="test",
            narrative="One flowing narrative.",
            try_this="Try this thing.",
            food_for_thought="A thought.",
        )
        md = build_theme_script_markdown(parts)
        self.assertNotIn("To start,", md)
        self.assertNotIn("Next,", md)
        self.assertNotIn("And finally,", md)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3 -m unittest tests.test_theme_script_writer -v`
Expected: ImportError (generate_theme_script doesn't exist)

- [ ] **Step 3: Implement generate_theme_script and build_theme_script_markdown**

Add to `ai_podcast_pipeline/script_writer.py`:

```python
AUDIENCE_DESCRIPTION = (
    "Your audience is your colleagues — communications professionals who spend their days "
    "writing stories, building presentations, drafting speeches, creating emails, and managing "
    "content across channels like intranets and digital signage. They want to know how AI can "
    "make their daily work better — not enterprise deployment strategy. Keep it practical, "
    "specific, and useful. They are not technologists. They've heard of ChatGPT, they may have "
    "tried it, but they don't think in terms of models or prompts. They think in terms of: "
    "I have a draft due Thursday and I'm stuck on the opening."
)


def _theme_articles_blob(selected: list[ScoredStory]) -> str:
    """Format selected articles for the theme-based script prompt."""
    rows: list[str] = []
    for idx, story in enumerate(selected, start=1):
        c = story.candidate
        published = c.published_at.isoformat() if c.published_at else "unknown"
        rows.append(
            f"{idx}. title={c.title}\n"
            f"   source={_pub_name(c.source_domain)}\n"
            f"   published_at={published}\n"
            f"   full_article_text={c.full_text or c.summary}"
        )
    return "\n\n".join(rows)


def generate_theme_script(
    api_key: str,
    model: str,
    theme_name: str,
    selected: list[ScoredStory],
    target_total_words: int,
    project_id: str | None = None,
    organization: str | None = None,
    previous_food_for_thought: list[str] | None = None,
) -> ScriptParts:
    """Generate a cohesive theme-based script from supporting articles."""
    articles_blob = _theme_articles_blob(selected)
    fot_history = _build_fot_history_block(previous_food_for_thought or [])
    content_words = target_total_words - 70  # subtract intro/outro

    prompt = f"""You are the host of a friendly, upbeat weekly podcast called The Signal.

{AUDIENCE_DESCRIPTION}

This week's theme: "{theme_name}"

Write ONE cohesive podcast script about this theme. Do NOT summarize articles one by one.
Weave insights from the supporting articles into a single flowing narrative. Sources are
evidence supporting your points — not standalone segments.

Episode structure (follow this order):
1. THEME INTRO — state the theme in plain terms, why it caught your attention this week
2. WHY IT MATTERS — connect it directly to the audience's daily work (writing, editing, presenting, emailing)
3. 2-3 ANGLES — each illuminating a different facet of the theme, drawing from the supporting articles. Weave source attribution naturally mid-sentence or later — never open a paragraph with a publication name.
4. TRY THIS — one specific, concrete technique they can use at work. Not vague advice. Something they can literally do tomorrow. Be specific about the steps.
5. ONE MORE THING — a parting idea to sit with. Can connect to the theme or stand alone.

Voice and tone:
- Conversational, warm, plain language. You're a colleague sharing something useful, not a news anchor.
- Use contractions: "it's", "you'll", "I've", "couldn't", "that's", "here's".
- Never read articles verbatim. Synthesize and put everything in your own words.
- No jargon. If you must use a technical term, explain it immediately in plain English.
- No corporate-speak, no consulting-speak, no "in today's rapidly evolving landscape."

Delivery cues (MANDATORY for text-to-speech):
- Em dashes (—) for mid-sentence pivots and pauses: at least 4-5 across the full script
- Rhetorical questions for vocal inflection: at least 2-3 across the full script
- Short impact sentences (5 words or fewer) after longer buildups
- *Italicized emphasis* for vocal stress on key words: at least 2-3 across the full script

Perspective:
- Third person when referencing articles: "the author argues", "the piece describes"
- First person for your own reactions, the try-this segment, and the "one more thing" closing
- NEVER start a paragraph with a publication name or source attribution

Return ONLY valid JSON with exactly these keys:
- narrative: string (the full episode body — theme intro through the last angle, as one flowing text)
- try_this: string (the concrete technique segment)
- food_for_thought: string
{fot_history}
Length: aim for ~{content_words} words total across all three fields combined (narrative + try_this + food_for_thought).
Prioritize quality and natural flow over exact count.

Supporting articles:
{articles_blob}
""".strip()

    messages = [
        {"role": "system", "content": (
            "You are a natural, confident podcast host who explains things the way you'd "
            "share something useful with a colleague over coffee. You genuinely understand "
            "the material and focus on what's practical. You must output strict JSON only."
        )},
        {"role": "user", "content": prompt},
    ]

    logger.info("Generating theme script for '%s' via %s…", theme_name, model)
    try:
        content = chat_completion(
            api_key=api_key,
            model=model,
            messages=messages,
            project_id=project_id,
            organization=organization,
            temperature=0.5,
        )
        data = parse_json_response(content)
        narrative = data.get("narrative", "")
        try_this = data.get("try_this", "")
        food = data.get("food_for_thought", "")

        if not narrative or not try_this or not food:
            raise OpenAIError("Theme script response missing required fields")

        food = _clean_food_for_thought(food)

        # Validate delivery cues on the narrative
        cue_issues = _validate_delivery_cues_text(narrative)
        if cue_issues:
            logger.warning("Delivery cue issues in theme narrative (%d).", len(cue_issues))

        logger.info("Theme script generated successfully.")
        return ScriptParts(
            theme_name=theme_name,
            narrative=narrative.strip(),
            try_this=try_this.strip(),
            food_for_thought=food,
        )
    except OpenAIError:
        raise
    except Exception as exc:
        raise OpenAIError(f"Theme script generation failed: {exc}") from exc


def _validate_delivery_cues_text(text: str) -> list[str]:
    """Validate delivery cues on a single text block (not per-story)."""
    issues: list[str] = []
    dashes = _count_em_dashes(text)
    questions = _count_questions(text)
    if dashes < 4:
        issues.append(f"Only {dashes} em dashes in narrative (need ≥4)")
    if questions < 2:
        issues.append(f"Only {questions} rhetorical questions (need ≥2)")
    if _count_italic_emphasis(text) < 2:
        issues.append("Fewer than 2 italicized emphasis instances")
    return issues


def build_theme_script_markdown(parts: ScriptParts) -> str:
    """Assemble the theme-based episode into final markdown."""
    from .constants import INTRO_TEXT, OUTRO_TEXT

    sections = [
        INTRO_TEXT,
        "",
        parts.narrative,
        "",
        parts.try_this,
        "",
        parts.food_for_thought,
        "",
        OUTRO_TEXT,
        "",
    ]
    return "\n".join(sections)


def build_theme_script_json(
    parts: ScriptParts,
    selected: list[ScoredStory],
    script_markdown: str,
) -> dict[str, Any]:
    """Build the JSON payload for a theme-based episode."""
    from .constants import INTRO_TEXT
    from .utils import count_words
    from datetime import datetime, timezone

    return {
        "episode_name": "",  # filled by caller
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "theme": parts.theme_name,
        "intro": INTRO_TEXT,
        "sources": [
            {
                "index": i + 1,
                "title": s.candidate.title,
                "source_domain": s.candidate.source_domain,
                "source_url": s.candidate.url,
                "published_at": s.candidate.published_at.isoformat() if s.candidate.published_at else None,
            }
            for i, s in enumerate(selected)
        ],
        "narrative": parts.narrative,
        "try_this": parts.try_this,
        "food_for_thought": parts.food_for_thought,
        "word_count": count_words(script_markdown),
        "script_markdown": script_markdown,
        "rewrite_attempts": 0,
        "explicit_fail_state": False,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python3 -m unittest tests.test_theme_script_writer -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add ai_podcast_pipeline/script_writer.py tests/test_theme_script_writer.py
git commit -m "feat: add theme-based script generation and markdown assembly"
```

---

### Task 5: Wire theme mode into the pipeline

**Files:**
- Modify: `ai_podcast_pipeline/pipeline.py`

This is the integration task — adding the theme clustering stage, theme selection UX, and connecting to the new script generation.

- [ ] **Step 1: Add imports at top of pipeline.py**

```python
from .theme_clustering import cluster_themes
from .script_writer import (
    generate_theme_script,
    build_theme_script_markdown,
    build_theme_script_json,
    rewrite_script_to_target,
)
```

- [ ] **Step 2: Add _stage_cluster_themes function**

Add after `_stage_build_full_list`:

```python
def _stage_cluster_themes(
    full_list_items: list[ScoredStory],
    settings: Settings,
) -> list[ThemeCandidate]:
    """Cluster the top articles into theme candidates."""
    # Use up to top 30 articles for clustering
    top_articles = full_list_items[:min(len(full_list_items), MAX_SHORTLIST)]
    themes = cluster_themes(
        api_key=settings.openai_api_key,
        model=settings.openai_model,  # mini model for clustering
        scored_articles=top_articles,
        project_id=settings.openai_project_id,
        organization=settings.openai_organization,
    )
    return themes
```

- [ ] **Step 3: Add _prompt_theme_selection function**

```python
def _prompt_theme_selection(themes: list[ThemeCandidate], full_list: list[ScoredStory]) -> int:
    """Display theme candidates and prompt user to pick one. Returns 0-based index."""
    print("\n\nThis week's theme candidates:\n")
    for idx, theme in enumerate(themes, start=1):
        print(f"[{idx}] {theme.name}")
        print(f"    {theme.description}")
        articles = []
        for ai in theme.article_indices:
            if 1 <= ai <= len(full_list):
                a = full_list[ai - 1]
                articles.append(f"      • {a.candidate.title} ({a.candidate.source_domain})")
        print("\n".join(articles))
        print()

    while True:
        try:
            raw = input(f"Pick a theme (1..{len(themes)}): ").strip()
            choice = int(raw)
            if 1 <= choice <= len(themes):
                return choice - 1
        except (ValueError, EOFError):
            pass
        print(f"Please enter a number between 1 and {len(themes)}.")
```

- [ ] **Step 4: Add _stage_generate_theme_script function**

```python
def _stage_generate_theme_script(
    theme: ThemeCandidate,
    selected: list[ScoredStory],
    settings: Settings,
    previous_food_for_thought: list[str] | None = None,
) -> tuple[str, ScriptParts, int, bool]:
    """Generate the theme-based script. Returns (markdown, parts, rewrite_attempts, fail_state)."""
    min_words, max_words, aim_words = TARGET_MIN_WORDS, TARGET_MAX_WORDS, (TARGET_MIN_WORDS + TARGET_MAX_WORDS) // 2
    parts = generate_theme_script(
        api_key=settings.openai_api_key,
        model=settings.openai_script_model,  # full model for script gen
        theme_name=theme.name,
        selected=selected,
        target_total_words=aim_words,
        project_id=settings.openai_project_id,
        organization=settings.openai_organization,
        previous_food_for_thought=previous_food_for_thought,
    )
    script_markdown = build_theme_script_markdown(parts)
    wc = count_words(script_markdown)
    logger.info("Initial theme script: %d words (target %d–%d).", wc, min_words, max_words)

    attempts = 0
    explicit_fail_state = False

    while not (min_words <= wc <= max_words):
        if attempts >= MAX_REWRITES:
            logger.warning(
                "Word-count gate failed after %d rewrite(s); proceeding with %d words.",
                MAX_REWRITES, wc,
            )
            explicit_fail_state = True
            break
        attempts += 1
        try:
            script_markdown = rewrite_script_to_target(
                api_key=settings.openai_api_key,
                model=settings.openai_model,  # mini for rewrite
                script_markdown=script_markdown,
                min_words=min_words,
                max_words=max_words,
                project_id=settings.openai_project_id,
                organization=settings.openai_organization,
            )
        except Exception as exc:
            logger.error("Rewrite failed: %s", exc)
            explicit_fail_state = True
            break
        wc = count_words(script_markdown)
        logger.info("After rewrite %d: %d words.", attempts, wc)

    return script_markdown, parts, attempts, explicit_fail_state
```

- [ ] **Step 5: Update run_pipeline to use theme mode**

In the main `run_pipeline` function, after Stage 1 (build full list), replace Stages 2-3 with:

```python
    # ── Stage 2: Cluster themes ──────────────────────────────────
    themes = _stage_cluster_themes(full_list_items, settings)

    # ── Stage 2b: User selects theme ─────────────────────────────
    theme_idx = _prompt_theme_selection(themes, full_list_items)
    chosen_theme = themes[theme_idx]
    logger.info("Theme selected: '%s'", chosen_theme.name)

    # Resolve selected articles from theme indices
    selected: list[ScoredStory] = []
    for ai in chosen_theme.article_indices:
        if 1 <= ai <= len(full_list_items):
            selected.append(full_list_items[ai - 1])
    selected_indices = chosen_theme.article_indices

    # ── Stage 2c: Fetch full article text ────────────────────────
    # (reuse existing fetch_article_text_batch logic)

    # ── Stage 3: Generate theme script ───────────────────────────
    script_markdown, parts, rewrite_attempts, explicit_fail_state = _stage_generate_theme_script(
        chosen_theme, selected, settings, previous_food_for_thought,
    )

    # Write script artifacts using theme-based builders
    script_json_payload = build_theme_script_json(parts, selected, script_markdown)
    script_json_payload["episode_name"] = episode_name
    script_json_payload["rewrite_attempts"] = rewrite_attempts
    script_json_payload["explicit_fail_state"] = explicit_fail_state
```

Note: The existing stages for cover, audio, manifest, and QA remain largely the same. The key difference is that `build_script_json` is replaced by `build_theme_script_json` and `build_script_markdown` by `build_theme_script_markdown`.

- [ ] **Step 6: Verify the pipeline runs end-to-end**

Run: `printf '1\ny\n' | .venv/bin/python3 -m ai_podcast_pipeline run --output-dir ./output --skip-audio --env-file .env 2>&1 | tail -20`
Expected: Pipeline completes with theme selection, generates a cohesive script

- [ ] **Step 7: Commit**

```bash
git add ai_podcast_pipeline/pipeline.py
git commit -m "feat: wire theme clustering and theme script generation into pipeline"
```

---

### Task 6: Update QA and schema for theme-based episodes

**Files:**
- Modify: `ai_podcast_pipeline/qa.py`
- Modify: `schemas/script.schema.json`

- [ ] **Step 1: Update script.schema.json**

Replace the schema to reflect theme-based structure:

```json
{
  "$schema": "https://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": [
    "episode_name", "generated_at", "theme", "intro",
    "sources", "narrative", "try_this", "food_for_thought",
    "word_count", "script_markdown", "rewrite_attempts", "explicit_fail_state"
  ],
  "properties": {
    "episode_name": {"type": "string"},
    "generated_at": {"type": "string"},
    "theme": {"type": "string"},
    "intro": {"type": "string"},
    "sources": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["index", "title", "source_domain", "source_url"],
        "properties": {
          "index": {"type": "integer"},
          "title": {"type": "string"},
          "source_domain": {"type": "string"},
          "source_url": {"type": "string", "format": "uri"},
          "published_at": {"type": ["string", "null"]}
        }
      }
    },
    "narrative": {"type": "string"},
    "try_this": {"type": "string"},
    "food_for_thought": {"type": "string"},
    "word_count": {"type": "integer", "minimum": 1},
    "script_markdown": {"type": "string"},
    "rewrite_attempts": {"type": "integer", "minimum": 0, "maximum": 5},
    "explicit_fail_state": {"type": "boolean"}
  }
}
```

- [ ] **Step 2: Update QA checks in qa.py**

The `selected_order` check and `ending_token_exact_once` check need updating since we no longer have per-story indices or a mandatory closing segment opener. Update the relevant checks to work with the new JSON structure. Remove the `cn_relevance` reference. Keep: intro_exact, word_count_gate, schemas, no_banned_phrases, prose_quality, cover_deterministic, filename_rule, no_secrets.

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/python3 -m unittest discover -s tests -p 'test_*.py' -v 2>&1 | tail -5`
Expected: Tests pass (some existing script_writer tests may need updating for new ScriptParts fields)

- [ ] **Step 4: Commit**

```bash
git add ai_podcast_pipeline/qa.py schemas/script.schema.json
git commit -m "feat: update QA checks and schema for theme-based episodes"
```

---

### Task 7: End-to-end verification

**Files:** None (testing only)

- [ ] **Step 1: Run full test suite**

Run: `.venv/bin/python3 -m unittest discover -s tests -p 'test_*.py' -v`
Expected: All tests pass (excluding pre-existing failures)

- [ ] **Step 2: Run a full test episode**

Run: `printf '1\ny\n' | .venv/bin/python3 -m ai_podcast_pipeline run --output-dir ./output --skip-audio --env-file .env`

Verify:
- Theme candidates are displayed
- User can pick a theme
- Script is cohesive (one narrative, not per-story summaries)
- Script includes a "try this" segment
- Word count is 700-850
- QA passes

- [ ] **Step 3: Read the script aloud**

Does it sound like a person talking about one subject, or a news roundup? Every paragraph should connect to the theme. No paragraph should feel like a standalone story summary.

- [ ] **Step 4: Run eval harness**

Run: `.venv/bin/python3 scripts/eval_script_quality.py "output/[latest]-Script.json"`
Verify: 0 source-first openings, varied patterns

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete theme-based episode pipeline — tested end-to-end"
```
