# Theme-First Pipeline Design for The Signal

## Context

The Signal is a podcast for CN communications professionals — writers, presenters, speech drafters, email authors, and content managers. The current pipeline fetches RSS feeds (7-day window), clusters articles into themes, and generates episodes from what it finds. This is fragile: some weeks there aren't enough quality articles to form a good theme.

The new approach flips the pipeline: **propose themes first, then research sources for the chosen theme.** This widens the source window (freshness-biased, no hard cutoff), expands source types (web search + RSS + blogs), and ensures every episode has a strong thematic foundation.

## Audience

Communications professionals at CN who:
- Write stories for the intranet
- Build PowerPoint decks for executives
- Draft speeches and emails
- Manage digital signage and newsletter content
- Are NOT technologists — they think "I have a draft due Thursday" not "which LLM should I use"

## Pipeline Flow

### Step 1: Theme Proposal

Pipeline performs a lightweight scan and proposes 4-5 themes:

1. **Theme bank** — load `data/theme_bank.json`, filter out themes used in the last 30 days
2. **RSS scan** — quick fetch of headlines/summaries from existing feed list (no full text)
3. **Web search** — 3-5 targeted queries (e.g., "AI for communications professionals," "AI writing tools new") to catch trends beyond RSS
4. **LLM synthesis** — gpt-5.4-mini receives bank candidates + RSS headlines + web search results. Prompt: "Pick 4-5 themes with the freshest, richest source material right now. Mix evergreen bank themes with emerging topics. For each, provide theme name, one-line pitch, and 2-3 source previews."

User picks a theme OR types their own topic. If they type their own, skip to Step 2.

### Step 2: Deep Research

Once a theme is chosen:

1. **Targeted web search** — 4-6 queries tailored to the theme
2. **RSS filter** — check existing feeds for articles matching the theme
3. **Fetch full text** — download full article text for top candidates
4. **Score and rank** — freshness bias (prefer recent, no hard cutoff), source credibility, relevance to theme
5. **Present 3-6 sources** to user for review — user can approve, drop, or paste their own article text

### Step 3: Script Generation

Same as current theme-based generation:
- Model: gpt-5.4 for script, gpt-5.4-mini for clustering/fix-ups
- Structure: theme intro → why it matters → 2-3 angles → try this → one more thing → close
- Target: 700-850 words (~5-6 minutes)
- Includes: source introductions, "here at CN" language, Fish Audio expression tags
- Rewrite loop if word count is out of range (max 2 attempts)

### Step 4: Companion Materials

Generated alongside the script:
- **Teams Post.md** — announcement with theme, summary, bullet points for Microsoft Teams
- **Try This.md** — extracted actionable steps/prompts from the try-this segment
- **Script.md** — full script text for sharing

### Step 5: Cover Art, Audio, QA

Unchanged from current pipeline:
- Cover PNG with determinism check
- Fish Audio S2 TTS (or Qwen fallback), user confirms before generating
- QA checks: schema validation, banned phrases, word count, delivery cues

## Theme Bank

File: `data/theme_bank.json`

### Schema

```json
{
  "themes": [
    {
      "id": "first-drafts",
      "name": "Getting unstuck on first drafts",
      "description": "Using AI as a brainstorming partner to break through blank-page paralysis",
      "tags": ["writing", "drafting", "productivity"],
      "last_used": null,
      "times_used": 0
    }
  ]
}
```

### Rules

- Themes used in the last 30 days are excluded from proposals (configurable via `THEME_COOLDOWN_DAYS`)
- When a theme is used, `last_used` is set to today and `times_used` increments
- New reusable themes discovered during web search are added to the bank automatically
- One-off news events are NOT added to the bank
- Seeded with ~25 starter themes covering: writing, presenting, editing, summarizing, email, speech prep, tone, research, brainstorming, media prep, content repurposing, meeting prep, stakeholder comms, data storytelling, accessibility

## Source Scoring

Sources are scored with freshness bias but no hard date cutoff:

- **Relevance to theme** (40%) — how directly the source supports the chosen theme
- **Freshness** (25%) — newer content scores higher, but great older content still qualifies
- **Credibility** (20%) — known publications and practitioners score higher
- **Practical value** (15%) — does it contain actionable advice for communicators?

## What Changes vs. Current Pipeline

| Component | Before | After |
|-----------|--------|-------|
| Theme discovery | Articles first → cluster into themes | Propose themes first → research sources |
| Source window | 7 days (RSS only) | No hard cutoff, freshness-biased (web search + RSS) |
| Source types | RSS feeds only | Web search + RSS + blogs/practitioner posts |
| User picks | A theme from clustered articles | A theme from proposals, or types their own |
| Theme bank | None | `data/theme_bank.json` — seeded + auto-growing |

## What Stays

- Script generation prompts and structure (theme-based)
- Companion materials generation (Teams Post, Try This)
- Source introductions, "here at CN" language, Fish Audio tags
- Cover art rendering
- Audio synthesis (Fish Audio S2 / Qwen)
- QA checks
- Exclusion keyword filtering
- Delivery cue enforcement
- Word count rewrite loop

## Files to Create

| File | Purpose |
|------|---------|
| `data/theme_bank.json` | Seeded theme bank (~25 themes) |
| `ai_podcast_pipeline/theme_proposal.py` | Theme proposal logic: bank + RSS + web search → LLM → proposals |
| `ai_podcast_pipeline/theme_research.py` | Deep research: targeted search + fetch + score for chosen theme |

## Files to Modify

| File | Changes |
|------|---------|
| `pipeline.py` | Replace theme clustering stage with theme proposal → deep research flow |
| `constants.py` | Add `THEME_COOLDOWN_DAYS = 30` |
| `config.py` | Add web search API settings if needed |

## Files to Remove or Deprecate

| File | Action |
|------|--------|
| `theme_clustering.py` | Deprecate — no longer needed (themes aren't derived from articles) |

## Verification

1. Run pipeline — verify 4-5 theme proposals appear with source previews
2. Pick a theme — verify deep research finds 3-6 quality sources
3. Type a custom theme — verify it skips proposals and goes to research
4. Verify theme bank updates after episode generation
5. Verify used themes don't reappear within 30 days
6. Verify sources span beyond 7-day window
7. Read the script — does it feel well-sourced and thematically coherent?
8. Check companion materials generate correctly
