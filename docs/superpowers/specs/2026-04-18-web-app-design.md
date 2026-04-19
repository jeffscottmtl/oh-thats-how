# The Signal — Web App Design

## Overview

A local web app at `http://localhost:8000` that replaces the CLI's interactive prompts with a step-by-step browser UI. FastAPI backend, vanilla HTML/CSS/JS frontend. No build step, no Node.js, no framework.

## Audience

Jeff Scott — sole user. Runs locally on his Mac. No auth, no multi-user, no deployment.

## User Flow

Single page, step-by-step wizard. Each step shows results and waits for user action before proceeding.

### Step 1: New Episode
- User clicks "New Episode" button
- Backend scans RSS + theme bank, calls LLM to propose 4-5 themes
- Frontend shows theme cards with name, pitch, source previews
- User clicks a theme card OR types a custom topic in a text field
- Loading spinner while proposals generate

### Step 2: Research
- Backend researches the chosen theme — RSS filter + web search + full text fetch
- Frontend shows source cards: title, publication, date, word count, full text preview (expandable)
- User can drop sources (uncheck them) or paste custom article text
- "Generate Script" button to proceed

### Step 3: Script
- Backend generates theme script via LLM
- Frontend shows the script in a readable format (styled markdown)
- Three tabs: **Script** | **Teams Post** | **Try This**
- User can read and review all three
- "Generate Audio" button (or "Skip Audio & Finish")

### Step 4: Audio
- Backend calls Fish Audio S2 TTS
- Progress indicator while generating
- Inline audio player to preview the episode
- Download button for MP3

### Step 5: Done
- Summary card: episode name, word count, source count, audio duration
- Download links for all output files (script, Teams post, Try This, cover, MP3, manifest)
- "Start New Episode" button to go back to Step 1

## Sidebar: Past Episodes

Left sidebar lists previous episodes (from output/ directory manifests). Click one to view its script, companions, and play audio.

## Architecture

### Backend — FastAPI

File: `web/app.py`

Endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Serve index.html |
| GET | `/api/episodes` | List past episodes from output/ manifests |
| GET | `/api/episodes/{name}` | Get a specific episode's data |
| POST | `/api/propose` | Scan RSS + bank, return 4-5 theme proposals |
| POST | `/api/research` | Research a chosen theme, return ranked sources with full text |
| POST | `/api/generate` | Generate script + companion materials from theme + sources |
| POST | `/api/audio` | Generate TTS audio, return file path |
| GET | `/api/files/{path}` | Serve output files (MP3, cover, etc.) |

Each endpoint calls existing pipeline functions directly — no new business logic. The web layer is purely orchestration and serialization.

### Frontend — Vanilla HTML/CSS/JS

Files in `web/static/`:

| File | Purpose |
|------|---------|
| `index.html` | Single page shell — wizard container + sidebar |
| `app.js` | Step logic, API calls, DOM manipulation |
| `style.css` | Clean, minimal styling |

No framework. No build step. Fetch API for requests. Template literals for rendering.

### Styling

Clean, professional, minimal. Dark header with "The Signal" branding. Card-based layout for themes and sources. Monospace for script text. Consistent with the podcast's tone — warm, not corporate.

## File Structure

```
web/
  app.py          — FastAPI application
  static/
    index.html    — Single page
    app.js        — Client logic
    style.css     — Styles
```

## What Stays

- All existing pipeline modules (theme_proposal, theme_research, script_writer, audio, qa, etc.)
- CLI entry point (`python -m ai_podcast_pipeline run`) still works
- Output file structure unchanged
- Theme bank, companion materials, cover art — all the same

## What Changes

- `web/app.py` wraps pipeline functions in FastAPI endpoints
- Pipeline functions may need minor refactoring to return data instead of printing to stdout (some already return data; the print statements are in `run_pipeline` which we bypass)

## Dependencies

- `fastapi` — already in project
- `uvicorn` — ASGI server to run the app

## Launch

```bash
python -m web.app
# or
uvicorn web.app:app --reload
```

Opens at `http://localhost:8000`

## Out of Scope

- Authentication / multi-user
- Cloud deployment
- Real-time WebSocket progress (use simple polling or SSE if needed)
- Mobile responsive (desktop browser only)
