# Diverse Source Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve podcast episode source diversity by replacing template-based search queries with LLM-generated queries, and adding a "supporting evidence" tier to the LLM source filter.

**Architecture:** Two changes in the research pipeline: (1) a new `_llm_generate_queries()` function replaces the template-based `_build_search_queries()` as the primary query source, with the old function kept as fallback; (2) `_llm_filter_sources()` gains a two-tier return format (primary/supporting) and the `CandidateStory` model gets a `source_role` field to carry this through to script generation.

**Tech Stack:** Python 3.9+, OpenAI API (chat completions), pytest, unittest.mock

**Spec:** `docs/superpowers/specs/2026-04-19-diverse-source-discovery-design.md`

**Test command:** `python3 -m pytest tests/test_theme_research.py -v --tb=short`

---

### Task 1: Add `source_role` field to CandidateStory

**Files:**
- Modify: `ai_podcast_pipeline/models.py:9-15`
- Test: `tests/test_theme_research.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_theme_research.py`:

```python
class TestCandidateStorySourceRole(unittest.TestCase):
    def test_default_source_role_is_primary(self):
        c = CandidateStory(
            title="Test", url="https://example.com", source_domain="example.com",
            published_at=None, summary="test",
        )
        self.assertEqual(c.source_role, "primary")

    def test_source_role_can_be_set_to_supporting(self):
        c = CandidateStory(
            title="Test", url="https://example.com", source_domain="example.com",
            published_at=None, summary="test", source_role="supporting",
        )
        self.assertEqual(c.source_role, "supporting")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_theme_research.py::TestCandidateStorySourceRole -v --tb=short`
Expected: FAIL — `TypeError: CandidateStory.__init__() got an unexpected keyword argument 'source_role'`

- [ ] **Step 3: Add `source_role` field to CandidateStory**

In `ai_podcast_pipeline/models.py`, change lines 9-15 from:

```python
@dataclass
class CandidateStory:
    title: str
    url: str
    source_domain: str
    published_at: datetime | None
    summary: str
    full_text: str | None = None  # fetched after user selection; None = not yet fetched
```

To:

```python
@dataclass
class CandidateStory:
    title: str
    url: str
    source_domain: str
    published_at: datetime | None
    summary: str
    full_text: str | None = None  # fetched after user selection; None = not yet fetched
    source_role: str = "primary"  # "primary" or "supporting"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_theme_research.py -v --tb=short`
Expected: All 25 tests PASS (23 existing + 2 new)

- [ ] **Step 5: Commit**

```bash
git add ai_podcast_pipeline/models.py tests/test_theme_research.py
git commit -m "feat: add source_role field to CandidateStory model"
```

---

### Task 2: Replace template queries with LLM-generated queries

**Files:**
- Modify: `ai_podcast_pipeline/theme_research.py:106-169`
- Test: `tests/test_theme_research.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_theme_research.py`. The test mocks `chat_completion` and verifies the new function parses the LLM response correctly. Also add a fallback test.

Update the imports at the top of the file:

```python
from unittest.mock import patch
import json

from ai_podcast_pipeline.theme_research import (
    _build_search_queries,
    _llm_generate_queries,
    _rank_sources,
    _score_source,
)
```

Then add the test class:

```python
class TestLlmGenerateQueries(unittest.TestCase):
    THEME = "AI for Internal Communications"

    @patch("ai_podcast_pipeline.theme_research.chat_completion")
    def test_returns_queries_from_llm(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "queries": [
                "AI tools internal communications employee engagement 2026",
                "personalized employee messaging AI enterprise",
                "Microsoft Work Trend Index digital workplace productivity",
                "Edelman trust barometer AI-generated content credibility",
                "AI content personalization intranet newsletters",
                "internal comms measurement analytics AI beyond open rates",
                "McKinsey employee productivity AI knowledge workers",
                "AI video creation internal communications digital signage",
                "site:gartner.com AI internal communications",
                "site:gartner.com employee communications technology",
            ]
        })
        queries = _llm_generate_queries(self.THEME, api_key="test-key", model="gpt-4.1-mini")
        self.assertGreaterEqual(len(queries), 8)
        self.assertLessEqual(len(queries), 12)
        for q in queries:
            self.assertIsInstance(q, str)
            self.assertTrue(len(q) > 0)

    @patch("ai_podcast_pipeline.theme_research.chat_completion")
    def test_falls_back_to_templates_on_failure(self, mock_chat):
        mock_chat.side_effect = Exception("API error")
        queries = _llm_generate_queries(self.THEME, api_key="test-key", model="gpt-4.1-mini")
        # Should fall back to template-based queries
        self.assertGreaterEqual(len(queries), 4)
        for q in queries:
            self.assertIsInstance(q, str)

    @patch("ai_podcast_pipeline.theme_research.chat_completion")
    def test_deduplicates_queries(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "queries": [
                "AI internal comms",
                "AI internal comms",  # duplicate
                "employee engagement AI",
            ]
        })
        queries = _llm_generate_queries(self.THEME, api_key="test-key", model="gpt-4.1-mini")
        self.assertEqual(len(queries), len(set(queries)))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_theme_research.py::TestLlmGenerateQueries -v --tb=short`
Expected: FAIL — `ImportError: cannot import name '_llm_generate_queries'`

- [ ] **Step 3: Implement `_llm_generate_queries`**

In `ai_podcast_pipeline/theme_research.py`, rename the existing function and add the new one. Replace lines 105-144 (the query generation section) with:

```python
# ---------------------------------------------------------------------------
# 1. Query generation
# ---------------------------------------------------------------------------


def _tokenise(text: str) -> list[str]:
    """Lowercase, strip punctuation, remove stopwords."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return [w for w in words if w not in _STOPWORDS]


def _build_search_queries(theme_name: str) -> list[str]:
    """Fallback: generate template-based search queries for a theme.

    Used when the LLM query generation fails.
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

    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)

    return unique


def _llm_generate_queries(
    theme_name: str,
    api_key: str,
    model: str,
    project_id: str | None = None,
    organization: str | None = None,
) -> list[str]:
    """Ask the LLM to generate diverse search queries for a theme.

    Returns 8-10 queries covering different angles: practical how-to,
    research/data, adjacent concepts, industry trends, trust/ethics.
    Falls back to template-based queries on failure.
    """
    prompt = f"""Generate 8-10 web search queries to find diverse, high-quality articles for a podcast episode about: "{theme_name}"

The podcast is for communications professionals at a large company — they write stories, build presentations, draft speeches, write emails and newsletters. They want practical AI advice, not enterprise strategy.

Requirements for query diversity:
- Cover DIFFERENT angles: practical how-to, research/data, adjacent concepts, trends, trust/ethics, measurement
- At least 2 queries targeting research firms, surveys, or data reports (McKinsey, Gallup, Edelman, Microsoft Work Trend Index, Staffbase, Poppulo, etc.)
- At least 2 queries targeting adjacent concepts related to the theme that use DIFFERENT keywords (e.g., for "AI for Internal Communications": employee engagement, digital workplace, content personalization, newsletter analytics)
- Include 1-2 queries with "site:gartner.com" targeting the theme
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_theme_research.py -v --tb=short`
Expected: All tests PASS (25 from Task 1 + 3 new = 28)

- [ ] **Step 5: Commit**

```bash
git add ai_podcast_pipeline/theme_research.py tests/test_theme_research.py
git commit -m "feat: add LLM-generated search queries with template fallback"
```

---

### Task 3: Wire LLM queries into web search

**Files:**
- Modify: `ai_podcast_pipeline/theme_research.py:154-246` (the `_web_search_for_theme` function)

- [ ] **Step 1: Update `_web_search_for_theme` to use LLM-generated queries**

In `ai_podcast_pipeline/theme_research.py`, modify `_web_search_for_theme` to accept and use the new query generation. Change lines 154-169 (the function signature and query generation) from:

```python
def _web_search_for_theme(
    theme_name: str,
    api_key: str,
    model: str = "gpt-4.1-mini",
) -> list[CandidateStory]:
    """Run web searches for a theme using OpenAI's web_search_preview tool.

    Returns CandidateStory objects with title, URL, source_domain, and summary.
    Full text is NOT fetched here — that happens later in the pipeline.
    """
    import requests as _requests

    queries = _build_search_queries(theme_name)
    # Add Gartner-specific queries targeting the theme.
    queries.append(f"site:gartner.com {theme_name}")
    queries.append(f"site:gartner.com AI {theme_name}")
```

To:

```python
def _web_search_for_theme(
    theme_name: str,
    api_key: str,
    model: str = "gpt-4.1-mini",
    project_id: str | None = None,
    organization: str | None = None,
) -> list[CandidateStory]:
    """Run web searches for a theme using OpenAI's web_search_preview tool.

    Returns CandidateStory objects with title, URL, source_domain, and summary.
    Full text is NOT fetched here — that happens later in the pipeline.
    """
    import requests as _requests

    queries = _llm_generate_queries(
        theme_name, api_key=api_key, model=model,
        project_id=project_id, organization=organization,
    )
```

Remove the two Gartner-specific `queries.append(...)` lines (168-169) since Gartner queries are now generated by the LLM.

- [ ] **Step 2: Update the `research_theme` call site to pass credentials**

In `research_theme()` (line 500-501), update the `_web_search_for_theme` call from:

```python
        web_search_results = _web_search_for_theme(theme_name, api_key=_api_key)
```

To:

```python
        web_search_results = _web_search_for_theme(
            theme_name, api_key=_api_key, model=_model,
            project_id=project_id, organization=organization,
        )
```

- [ ] **Step 3: Run all tests to verify nothing breaks**

Run: `python3 -m pytest tests/test_theme_research.py -v --tb=short`
Expected: All 28 tests PASS. The existing `TestBuildSearchQueries` tests still pass because `_build_search_queries` is kept as a function.

- [ ] **Step 4: Commit**

```bash
git add ai_podcast_pipeline/theme_research.py
git commit -m "feat: wire LLM-generated queries into web search pipeline"
```

---

### Task 4: Add supporting evidence tier to LLM filter

**Files:**
- Modify: `ai_podcast_pipeline/theme_research.py:361-576` (`_llm_filter_sources` and `research_theme`)
- Test: `tests/test_theme_research.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_theme_research.py`:

```python
from ai_podcast_pipeline.theme_research import _llm_filter_sources

class TestLlmFilterSourcesTiered(unittest.TestCase):
    THEME = "AI for Internal Communications"

    def _make_candidates(self, n=5):
        return [
            _make_candidate(
                title=f"Article {i}", url=f"https://example.com/{i}",
                domain="example.com", summary=f"Summary {i}",
            )
            for i in range(n)
        ]

    @patch("ai_podcast_pipeline.theme_research.chat_completion")
    def test_returns_primary_and_supporting_indices(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "primary": [0, 1, 3],
            "supporting": [2, 4],
        })
        candidates = self._make_candidates(5)
        primary, supporting = _llm_filter_sources(
            theme_name=self.THEME, candidates=candidates,
            api_key="test-key", model="gpt-4.1-mini",
        )
        self.assertEqual(primary, [0, 1, 3])
        self.assertEqual(supporting, [2, 4])

    @patch("ai_podcast_pipeline.theme_research.chat_completion")
    def test_falls_back_from_old_format(self, mock_chat):
        """If LLM returns old format (selected_indices), treat all as primary."""
        mock_chat.return_value = json.dumps({
            "selected_indices": [0, 2, 4],
        })
        candidates = self._make_candidates(5)
        primary, supporting = _llm_filter_sources(
            theme_name=self.THEME, candidates=candidates,
            api_key="test-key", model="gpt-4.1-mini",
        )
        self.assertEqual(primary, [0, 2, 4])
        self.assertEqual(supporting, [])

    @patch("ai_podcast_pipeline.theme_research.chat_completion")
    def test_caps_supporting_at_max(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "primary": [0],
            "supporting": [1, 2, 3, 4, 5, 6],  # 6 supporting — should be capped at 4
        })
        candidates = self._make_candidates(7)
        primary, supporting = _llm_filter_sources(
            theme_name=self.THEME, candidates=candidates,
            api_key="test-key", model="gpt-4.1-mini",
        )
        self.assertLessEqual(len(supporting), 4)

    @patch("ai_podcast_pipeline.theme_research.chat_completion")
    def test_fallback_on_exception(self, mock_chat):
        mock_chat.side_effect = Exception("API error")
        candidates = self._make_candidates(5)
        primary, supporting = _llm_filter_sources(
            theme_name=self.THEME, candidates=candidates,
            api_key="test-key", model="gpt-4.1-mini",
        )
        # Fallback: all candidates as primary, no supporting
        self.assertGreater(len(primary), 0)
        self.assertEqual(supporting, [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_theme_research.py::TestLlmFilterSourcesTiered -v --tb=short`
Expected: FAIL — the current `_llm_filter_sources` returns `list[int]`, not a tuple.

- [ ] **Step 3: Update `_llm_filter_sources` to return tiered results**

In `ai_podcast_pipeline/theme_research.py`, replace the `_llm_filter_sources` function (lines 361-450) with:

```python
_MAX_SUPPORTING = 4  # Cap supporting evidence articles.


def _llm_filter_sources(
    theme_name: str,
    candidates: list[CandidateStory],
    api_key: str,
    model: str,
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
- The audience writes stories for the intranet, builds PowerPoint presentations for executives, drafts speeches, writes emails and newsletters, and manages digital signage content.
- They are NOT technologists. They've heard of ChatGPT, they may have tried it, but they think in terms of "I have a draft due Thursday" — not models or prompts.
- The podcast's job is to help them feel confident about AI, give them practical techniques, and keep them aware of what's changing — in that order.

THIS EPISODE'S THEME: "{theme_name}"

YOUR TASK:
Select articles into TWO tiers:

**PRIMARY** — articles that are specifically about "{theme_name}" for communications professionals.
These form the backbone of the episode. Be STRICT: ask yourself "Could a communicator read this and learn something specific about {theme_name}?" If the answer is no, it's not primary.

A good primary source:
- Is specifically about "{theme_name}" — not just about AI or writing in general
- Contains insights, research, practical advice, or a real example directly tied to this theme
- Could be synthesized into advice like "here's how {theme_name} works better when you..."

**SUPPORTING** — research, data, or frameworks from authoritative sources that provide evidence
or context that strengthens the episode, even if the article isn't specifically about "{theme_name}".

A good supporting source:
- Contains a specific, citable data point, statistic, or research finding
- Comes from a high-authority source (research firms, major publications, established surveys)
- Provides evidence that makes a primary source's point stronger (e.g., a Microsoft Work Trend Index stat about employee productivity, an Edelman finding about trust in AI content)
- Is NOT just another trade blog post restating the same ideas as the primary sources

REJECT articles that are:
- About AI or writing in general but NOT relevant to "{theme_name}" even as supporting evidence
- About unrelated products, announcements, funding, or corporate news
- Only tangentially connected via a shared word
- About a technology (like TTS, image generation, etc.) unless it directly helps communicators with "{theme_name}"

Note: Gartner articles ARE allowed if relevant — they'll be flagged for the user to provide full text via login.

PREVIOUSLY USED ARTICLES:
Articles marked with ⚠️ PREVIOUSLY USED have been featured in past episodes.
- Strongly prefer fresh, unused articles over previously used ones.
- Only select a previously used article if it has a genuinely different angle for THIS theme
  that wasn't explored before.
- If no unused articles are relevant, it's better to return fewer results than to reuse sources.

Return JSON with two keys:
- "primary": array of index numbers for primary articles (at most {max_keep})
- "supporting": array of index numbers for supporting evidence articles (at most {_MAX_SUPPORTING})
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

        # Handle new tiered format.
        if "primary" in data:
            raw_primary = data.get("primary", [])
            raw_supporting = data.get("supporting", [])
            primary = [int(i) for i in raw_primary if isinstance(i, (int, float)) and 0 <= int(i) < len(candidates)]
            supporting = [int(i) for i in raw_supporting if isinstance(i, (int, float)) and 0 <= int(i) < len(candidates)]
            # Cap supporting evidence.
            supporting = supporting[:_MAX_SUPPORTING]
            # Remove any supporting that's also in primary.
            primary_set = set(primary)
            supporting = [i for i in supporting if i not in primary_set]
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
```

- [ ] **Step 4: Update `research_theme` to handle the new return format**

In `research_theme()`, replace lines 529-556 (Steps 5 and 5b) with:

```python
    # Step 5: LLM validation — the LLM picks the actually relevant ones.
    if _api_key and pre_ranked:
        primary_indices, supporting_indices = _llm_filter_sources(
            theme_name=theme_name,
            candidates=pre_ranked,
            api_key=_api_key,
            model=_model,
            project_id=project_id,
            organization=organization,
            max_keep=max_sources,
        )
        # Set source roles on candidates.
        for i in primary_indices:
            pre_ranked[i].source_role = "primary"
        for i in supporting_indices:
            pre_ranked[i].source_role = "supporting"
        final = [pre_ranked[i] for i in primary_indices] + [pre_ranked[i] for i in supporting_indices]
    else:
        final = pre_ranked[:max_sources]

    # Step 5b: Enforce per-domain diversity — max 2 results from any single domain.
    _MAX_PER_DOMAIN = 2
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
```

- [ ] **Step 5: Run all tests to verify they pass**

Run: `python3 -m pytest tests/test_theme_research.py -v --tb=short`
Expected: All 32 tests PASS (28 from previous tasks + 4 new)

- [ ] **Step 6: Commit**

```bash
git add ai_podcast_pipeline/theme_research.py tests/test_theme_research.py
git commit -m "feat: add supporting evidence tier to LLM source filter"
```

---

### Task 5: Pass source role to script generation

**Files:**
- Modify: `ai_podcast_pipeline/script_writer.py:804-924`
- Test: `tests/test_theme_script_writer.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_theme_script_writer.py`:

```python
class TestThemeArticlesBlobSourceRole(unittest.TestCase):
    def test_includes_source_role(self):
        from ai_podcast_pipeline.script_writer import _theme_articles_blob
        c = CandidateStory(
            title="Test Article", url="https://example.com/art",
            source_domain="example.com",
            published_at=datetime.now(timezone.utc),
            summary="A test article", full_text="Full text here.",
            source_role="supporting",
        )
        scored = ScoredStory(
            candidate=c, credibility=90, comms_relevance=50,
            freshness=80, ai_materiality=60, preferred_topic=0, total=55.0,
        )
        blob = _theme_articles_blob([scored])
        self.assertIn("role=supporting", blob)

    def test_primary_role_shown(self):
        from ai_podcast_pipeline.script_writer import _theme_articles_blob
        c = CandidateStory(
            title="Test Article", url="https://example.com/art",
            source_domain="example.com",
            published_at=datetime.now(timezone.utc),
            summary="A test article", full_text="Full text here.",
        )
        scored = ScoredStory(
            candidate=c, credibility=90, comms_relevance=50,
            freshness=80, ai_materiality=60, preferred_topic=0, total=55.0,
        )
        blob = _theme_articles_blob([scored])
        self.assertIn("role=primary", blob)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_theme_script_writer.py::TestThemeArticlesBlobSourceRole -v --tb=short`
Expected: FAIL — `"role=supporting"` not in the blob output.

- [ ] **Step 3: Update `_theme_articles_blob` to include role**

In `ai_podcast_pipeline/script_writer.py`, modify `_theme_articles_blob` (lines 804-816). Change the row formatting from:

```python
        rows.append(
            f"{idx}. title={c.title}\n"
            f"   source={_pub_name(c.source_domain)}\n"
            f"   published_at={published}\n"
            f"   full_article_text={c.full_text or c.summary}"
        )
```

To:

```python
        rows.append(
            f"{idx}. title={c.title}\n"
            f"   source={_pub_name(c.source_domain)}\n"
            f"   role={c.source_role}\n"
            f"   published_at={published}\n"
            f"   full_article_text={c.full_text or c.summary}"
        )
```

- [ ] **Step 4: Add source role guidance to the theme script prompt**

In `ai_podcast_pipeline/script_writer.py`, in the `generate_theme_script` function, find this line in the prompt (around line 860):

```python
Weave insights from the supporting articles into a single flowing narrative. Sources are
evidence supporting your points — not standalone segments.
```

Replace it with:

```python
Weave insights from the articles into a single flowing narrative.

SOURCE ROLES:
- Articles marked role=primary drive the episode's substance and narrative.
- Articles marked role=supporting are evidence sources — use them for specific data points,
  statistics, and framing that strengthen your arguments. Don't build narrative arcs around
  supporting sources; cite their findings to add weight and credibility to your primary points.
```

- [ ] **Step 5: Run all tests**

Run: `python3 -m pytest tests/test_theme_script_writer.py tests/test_theme_research.py -v --tb=short`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add ai_podcast_pipeline/script_writer.py tests/test_theme_script_writer.py
git commit -m "feat: pass source role through to script generation prompt"
```

---

### Task 6: Final verification — run full test suite

**Files:** None (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `python3 -m pytest tests/ -v --tb=short`
Expected: All tests PASS.

- [ ] **Step 2: Verify no import errors**

Run: `python3 -c "from ai_podcast_pipeline.theme_research import _llm_generate_queries, _llm_filter_sources, research_theme; print('imports OK')"`
Expected: `imports OK`

- [ ] **Step 3: Verify source_role field works end-to-end**

Run: `python3 -c "from ai_podcast_pipeline.models import CandidateStory; c = CandidateStory(title='t', url='u', source_domain='d', published_at=None, summary='s', source_role='supporting'); print(f'role={c.source_role}')"`
Expected: `role=supporting`

- [ ] **Step 4: Commit (if any fixups were needed)**

Only if issues were found and fixed in previous steps.
