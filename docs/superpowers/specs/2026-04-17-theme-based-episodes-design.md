# Theme-Based Episodes for The Signal

## Context

The Signal is a weekly AI podcast for CN communications professionals — people who write stories, build presentations, draft speeches, create emails, and manage content across intranets and digital signage. They work with internal clients daily and want to understand how AI can help them do their jobs better.

The podcast's primary job is **confidence** (reduce anxiety, demystify AI, help them feel capable), then **practical skills** (techniques that save time, improve quality, advance careers), then **awareness** (know what's changing so they're not blindsided).

The current pipeline is built around a news-roundup format: fetch RSS feeds, score articles, pick 3-5 individual stories, summarize each one. This produces scripts that feel like AI news briefs — informative but disconnected from the audience's daily reality.

The new format is **theme-based**: each episode picks one comms-related subject and goes deep — best practices, innovations, what AI changes about it, and something specific to try.

## Audience

Communications professionals at CN who:
- Write stories for the intranet
- Build PowerPoint decks for executives
- Draft speeches
- Write emails and newsletters
- Manage digital signage content
- Work with internal clients ("I need a presentation for the board")

They are **not** technologists. They've heard of ChatGPT, may have tried it, but don't think in terms of models, prompts, or pipelines. They think: "I have a draft due Thursday and I'm stuck on the opening."

## Episode Structure

5-6 minutes (~700-850 words). One theme per episode.

1. **Theme intro** — state the theme in plain terms, why it's on your radar this week
2. **Why it matters** — connect it to the audience's daily work
3. **2-3 angles** — drawn from the week's sources, each illuminating a different facet of the theme. Woven into a continuous narrative, not summarized individually.
4. **Try this** — one concrete technique or approach they can actually use at work
5. **Food for thought** — a parting idea to sit with
6. **Close**

No per-story transitions ("To start," / "Next,"). The script flows as one continuous piece. Sources are evidence supporting the theme, not standalone segments.

## Pipeline Changes

### Theme Discovery (new)

After scoring and filtering articles, the pipeline:

1. Collects the top ~30 scored article titles + summaries
2. Sends them to gpt-5.4-mini with a prompt asking: "Group these into 3-5 theme clusters relevant to communicators who write, present, draft, and edit daily. Each theme should have a plain-English name and 2-4 supporting articles."
3. Presents the themes to the user for selection (CLI or web UI)
4. User picks a theme; the pipeline proceeds with that theme's supporting articles

### Script Generation (rewritten)

- **Model**: gpt-5.4 (full model for better synthesis quality)
- **Input**: theme name, 2-4 supporting articles (full text), audience description, episode structure
- **Output**: one cohesive script following the episode structure — not per-story summaries
- **System message**: podcast host persona with cardinal opening rule (no source-first)
- **Temperature**: 0.5 for creative synthesis
- **cn_relevance section**: removed (the whole episode is already framed for CN communicators)
- **Food for thought**: stays, but opener softened — no forced "Here's some food for thought." label if it doesn't fit naturally
- **"Try this" segment**: new, explicit in the prompt — one specific technique, not a vague takeaway

### What Stays

- RSS feed fetching and concurrent ingestion (ingest.py)
- Article scoring with 4-dimension weights (scoring.py)
- Exclusion keywords filter
- Cover art generation (cover.py)
- Audio synthesis (audio.py) — Qwen TTS or skip
- QA checks (qa.py) — adapted for new structure
- Web UI and CLI entry points
- Opening-diversity validator
- Delivery cue enforcement
- Word count rewrite loop
- Story-drop logic (simplified: theme has 2-4 sources, less likely to overshoot)

### What Changes

| Component | Before | After |
|-----------|--------|-------|
| Story selection UX | "Pick story indices 1-30" | "Pick a theme" (with supporting articles shown) |
| Script prompt | Per-story summaries with transitions | Single cohesive theme narrative |
| Script structure | Intro → Story 1 → Story 2 → ... → cn_relevance → FoT → Close | Intro → Theme → Why it matters → Angles → Try this → FoT → Close |
| Transitions | Programmatic ("To start," / "Next,") | None — continuous flow |
| cn_relevance | Separate optional section | Removed (whole episode is CN-focused) |
| Model for script gen | gpt-5.4-mini | gpt-5.4 (full) |
| Model for clustering/fix-ups | N/A | gpt-5.4-mini |

### Model Usage

| Call | Model | Why |
|------|-------|-----|
| Theme clustering | gpt-5.4-mini | Simple grouping task, cost-efficient |
| Script generation | gpt-5.4 | Creative synthesis needs the stronger model |
| Delivery cue fix-up | gpt-5.4-mini | Surgical edits, low creativity needed |
| Opening diversity fix-up | gpt-5.4-mini | Same |
| Script rewrite (word count) | gpt-5.4-mini | Trimming, not creating |

## Files to Modify

| File | Changes |
|------|---------|
| `pipeline.py` | New theme-clustering stage, updated selection UX, updated script generation call |
| `script_writer.py` | New theme-based prompt, remove per-story transitions, remove cn_relevance, add "try this" segment, update build_script_markdown for new structure |
| `models.py` | New ThemeCandidate dataclass, update ScriptParts to reflect new structure |
| `constants.py` | Update INTRO_TEXT if approved, remove transition starters/mids/closers |
| `config.py` | Add OPENAI_SCRIPT_MODEL setting (defaults to gpt-5.4, separate from clustering model) |
| `qa.py` | Update checks for new episode structure (no cn_relevance, new "try this" check) |
| `schemas/script.schema.json` | Update to reflect theme-based structure |
| `web/server.py` | Update API to present themes instead of individual stories |

## Verification

1. Unit tests pass: `python3 -m unittest discover -s tests`
2. Run pipeline — verify theme candidates are proposed and selectable
3. Pick a theme — verify script is cohesive, not per-story summaries
4. Verify script includes a concrete "try this" technique
5. Verify word count is 700-850 (~5-6 min)
6. Run eval harness — verify opening diversity holds
7. Read the script aloud — does it sound like a person talking about one subject, or a news roundup?
