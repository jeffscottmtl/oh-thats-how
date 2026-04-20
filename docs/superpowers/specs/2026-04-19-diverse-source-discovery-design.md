# Diverse Source Discovery — Design Spec

**Date:** 2026-04-19
**Problem:** The research step produces too few, too similar sources. The "AI for Internal Communications" episode found only 5 articles from 3 domains (PR Daily x2, Ragan x2, Forbes x1), with 3/5 scoring 0 on AI Materiality. The script had to manufacture the AI angle.

**Root causes:**
1. Template-based query generation produces 7 near-identical keyword variations that all return the same results.
2. The LLM semantic filter rejects anything not *specifically* about the exact theme name — killing high-authority research sources (McKinsey, Edelman, Microsoft Work Trend Index) that would strengthen the episode as supporting evidence.

**Goal:** More diverse, higher-quality sources per episode — especially data-rich research from authoritative outlets — without degrading relevance.

---

## Change 1: LLM-Generated Search Queries

### What changes

Replace `_build_search_queries()` in `theme_research.py` (lines 116-144) with an LLM call that generates 8-10 diverse search queries.

### Current behavior

```python
def _build_search_queries(theme_name: str) -> list[str]:
    tokens = _tokenise(theme_name)
    keyword_str = " ".join(tokens)
    queries = [
        f"AI {theme_phrase} communications professionals",
        f"AI tools for {keyword_str} at work",
        f"how to use AI for {keyword_str} internal communications",
        ...  # 7 templates, all using the same keyword_str
    ]
```

For "AI for Internal Communications", every query contains "ai internal communications" — they're functionally identical.

### New behavior

A new function `_llm_generate_queries()` calls the LLM to produce 8-10 queries. The prompt instructs the LLM to:

- Generate queries that cover **different angles** of the theme: practical how-to, research/data, adjacent concepts, industry trends, trust/ethics, measurement
- Include at least **2 queries targeting research firms, surveys, or reports** (McKinsey, Gallup, Edelman, Microsoft Work Trend Index, Staffbase State of IC, etc.)
- Include at least **2 queries targeting adjacent concepts** that aren't in the theme name but are clearly related (e.g., for "AI for Internal Communications": employee engagement AI, digital workplace productivity, content personalization enterprise, AI trust workplace)
- Each query should surface **different sources** — no redundant keyword variations
- Keep 1-2 Gartner-specific queries (these move from the web search function to the query generator)

**Fallback:** If the LLM call fails, fall back to the current template-based approach (kept as `_build_search_queries_fallback()`).

**API cost:** One additional LLM call per episode using the same model already configured. Fast call — short prompt, short response. ~500 input tokens, ~300 output tokens.

### Example output

For theme "AI for Internal Communications", the LLM might generate:

1. `"AI tools internal communications employee engagement 2026"`
2. `"personalized employee messaging AI enterprise"`
3. `"Microsoft Work Trend Index digital workplace productivity"`
4. `"Edelman trust barometer AI-generated content credibility"`
5. `"AI content personalization intranet newsletters"`
6. `"internal comms measurement analytics AI beyond open rates"`
7. `"McKinsey employee productivity AI knowledge workers"`
8. `"AI video creation internal communications digital signage"`
9. `"site:gartner.com AI internal communications"`
10. `"site:gartner.com employee communications technology"`

### Interface

```python
def _llm_generate_queries(
    theme_name: str,
    api_key: str,
    model: str,
    project_id: str | None = None,
    organization: str | None = None,
) -> list[str]:
    """Ask the LLM to generate diverse search queries for a theme.
    
    Returns 8-10 queries covering different angles. Falls back to
    template-based queries on failure.
    """
```

Called from `_web_search_for_theme()`, replacing the current `_build_search_queries()` call. The Gartner-specific queries (lines 168-169) move into the LLM prompt so they're part of the generated set.

---

## Change 2: Supporting Evidence Tier in LLM Filter

### What changes

Modify `_llm_filter_sources()` in `theme_research.py` (lines 361-450) to ask the LLM to categorize selected articles into **primary** or **supporting** tiers.

### Current behavior

The LLM returns `{"selected_indices": [0, 1, 2, ...]}` — a flat list. It's instructed to be "STRICT about relevance" and reject anything not specifically about the theme.

### New behavior

The LLM prompt adds a second category:

- **Primary:** Directly about the theme — the current standard. These form the backbone of the episode.
- **Supporting:** Research, data, or frameworks from authoritative sources that provide evidence, statistics, or context that strengthens the episode — even if the article isn't specifically about the theme name. Examples: a Microsoft Work Trend Index stat about employee productivity, an Edelman Trust Barometer finding about AI-generated content, a McKinsey report on knowledge worker time allocation.

**Constraints on supporting evidence:**
- Cap at 4 articles maximum (`_MAX_SUPPORTING = 4`)
- Must come from high-authority sources (research firms, major publications, established surveys) — not more trade blog posts
- Must contain a specific, citable data point or finding — not just general commentary

**Return format changes from:**
```json
{"selected_indices": [0, 1, 2, 3, 4]}
```
**To:**
```json
{"primary": [0, 1, 3], "supporting": [2, 4]}
```

**Fallback:** If the LLM returns the old format (`selected_indices`), treat all as primary. This keeps backward compatibility if the model doesn't follow the new format.

### Model changes

Add a `source_role` field to `CandidateStory`:

```python
@dataclass
class CandidateStory:
    title: str
    url: str
    source_domain: str
    published_at: datetime | None
    summary: str
    full_text: str | None = None
    source_role: str = "primary"  # "primary" or "supporting"
```

This field is set by `research_theme()` after the LLM filter returns. Default is `"primary"` so existing code is unaffected.

### Downstream: script generation awareness

Two small changes to the script generation prompts:

1. **`_theme_articles_blob()`** (script_writer.py, line 804): Add a `role=primary` or `role=supporting` line to each article's formatted block.

2. **`generate_theme_script()` prompt** (script_writer.py, line 853): Add a short instruction:
   > "Articles marked role=supporting are evidence sources — use them for data points, statistics, and framing, not as main narrative threads. Primary articles drive the episode's substance."

No other prompt changes. The script writer already synthesizes articles into a flowing narrative — it just needs to know which ones are backbone vs evidence.

### Downstream: sources artifact

The sources JSON artifact (written by `artifacts.py`) already stores the selected stories. The `source_role` field will appear naturally when `CandidateStory` is serialized. No changes to the artifact code needed — it serializes whatever fields exist on the dataclass.

---

## What doesn't change

- **RSS feed list** — not relevant to this fix
- **Pre-ranking keyword scoring** (`_score_source`, `_rank_sources`) — still useful as a fast pre-filter before the LLM
- **Source diversity cap** (`_MAX_PER_DOMAIN = 2`) — stays in place
- **Full-text fetching** — unchanged
- **`scoring.py`** — the secondary scoring system is downstream and doesn't need changes
- **Audio generation, cover art, manifest** — untouched

---

## Files modified

| File | Change |
|------|--------|
| `ai_podcast_pipeline/theme_research.py` | Replace `_build_search_queries()` with `_llm_generate_queries()`, update `_llm_filter_sources()` prompt and return parsing, set `source_role` on candidates in `research_theme()` |
| `ai_podcast_pipeline/models.py` | Add `source_role: str = "primary"` to `CandidateStory` |
| `ai_podcast_pipeline/script_writer.py` | Update `_theme_articles_blob()` to include role, add one line to `generate_theme_script()` prompt |

---

## Risk and rollback

- **LLM query generation fails:** Falls back to existing templates. No degradation.
- **LLM filter returns old format:** Falls back to treating all as primary. No degradation.
- **Supporting evidence is low quality:** Cap of 3-4 limits damage. Script writer knows they're supporting, not primary.
- **More LLM calls = more cost:** One extra call (~500 input + ~300 output tokens). Negligible vs the web search and script generation calls.
