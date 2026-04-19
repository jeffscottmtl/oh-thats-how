"""The Signal — Web App. Run with: python -m web.app"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

# Add project root to path so pipeline imports work.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ai_podcast_pipeline.config import load_settings
from ai_podcast_pipeline.constants import THEME_BANK_PATH
from ai_podcast_pipeline.artifacts import build_artifact_paths, resolve_episode_name, resolve_episode_number
from ai_podcast_pipeline.models import ScoredStory, ThemeCandidate, VerificationResult
from ai_podcast_pipeline.scoring import score_story
from ai_podcast_pipeline.script_writer import (
    generate_theme_script,
    build_theme_script_markdown,
    build_theme_script_json,
)
from ai_podcast_pipeline.theme_proposal import propose_themes, load_theme_bank, save_theme_bank, mark_theme_used
from ai_podcast_pipeline.theme_research import research_theme
from ai_podcast_pipeline.utils import count_words, ensure_dir, iso_utc_now, write_json
from ai_podcast_pipeline.pipeline import (
    _stage_generate_theme_script,
    _generate_companion_materials,
    _stage_render_cover,
    _stage_audio,
    _load_previous_food_for_thought,
    _sources_payload,
    _strip_fish_tags,
)
from ai_podcast_pipeline.qa import run_qa

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="The Signal")

_STATIC_DIR = Path(__file__).parent / "static"
_OUTPUT_DIR = _PROJECT_ROOT / "output"

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


def _get_settings():
    """Load settings from env."""
    from ai_podcast_pipeline.utils import load_optional_env_file
    env_file = _PROJECT_ROOT / ".env"
    if env_file.exists():
        load_optional_env_file(env_file)
    return load_settings(
        story_count=3,
        allow_domains=None,
        skip_audio=False,
        skip_verification=True,
        env_file=str(env_file) if env_file.exists() else None,
    )


# ── Pages ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(str(_STATIC_DIR / "index.html"))


# ── API ────────────────────────────────────────────────────────────────

@app.get("/api/episodes")
async def list_episodes():
    """List past episodes from output/ manifests."""
    ensure_dir(_OUTPUT_DIR)
    episodes = []
    for manifest_path in sorted(_OUTPUT_DIR.glob("*Manifest.json"), reverse=True):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            episodes.append({
                "name": data.get("episode_name", manifest_path.stem),
                "number": data.get("episode_number"),
                "status": data.get("run_status", "unknown"),
                "created_at": data.get("created_at"),
                "files": data.get("files", {}),
            })
        except Exception:
            continue
    return JSONResponse(episodes)


@app.get("/api/episodes/{name:path}")
async def get_episode(name: str):
    """Get a specific episode's script and metadata."""
    # Find the script markdown.
    script_path = _OUTPUT_DIR / f"{name} - Script.md"
    manifest_path = _OUTPUT_DIR / f"{name} - Manifest.json"
    teams_path = _OUTPUT_DIR / f"{name} - Teams Post.md"
    try_this_path = _OUTPUT_DIR / f"{name} - Try This.md"

    result = {"name": name}
    if script_path.exists():
        result["script"] = script_path.read_text(encoding="utf-8")
    if manifest_path.exists():
        result["manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
    if teams_path.exists():
        result["teams_post"] = teams_path.read_text(encoding="utf-8")
    if try_this_path.exists():
        result["try_this"] = try_this_path.read_text(encoding="utf-8")

    # Check for audio.
    mp3_path = _OUTPUT_DIR / f"{name}.mp3"
    if mp3_path.exists():
        result["has_audio"] = True
        result["audio_url"] = f"/api/files/{name}.mp3"
    else:
        result["has_audio"] = False

    return JSONResponse(result)


@app.post("/api/propose")
async def propose():
    """Scan RSS + theme bank, propose 4-5 themes."""
    settings = _get_settings()
    theme_bank_path = Path(THEME_BANK_PATH)

    proposals, bank_entries = propose_themes(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        theme_bank_path=theme_bank_path,
        project_id=settings.openai_project_id,
        organization=settings.openai_organization,
    )

    return JSONResponse([
        {
            "name": p.name,
            "pitch": p.pitch,
            "source_previews": p.source_previews,
            "bank_id": p.bank_id,
        }
        for p in proposals
    ])


@app.post("/api/research")
async def research(request: Request):
    """Research a chosen theme, return ranked sources."""
    body = await request.json()
    theme_name = body.get("theme_name", "")
    if not theme_name:
        return JSONResponse({"error": "theme_name required"}, status_code=400)

    results = research_theme(theme_name=theme_name)

    sources = []
    for c in results:
        sources.append({
            "title": c.title,
            "url": c.url,
            "source_domain": c.source_domain,
            "published_at": c.published_at.isoformat() if c.published_at else None,
            "summary": c.summary,
            "full_text": c.full_text,
            "word_count": len(c.full_text.split()) if c.full_text else 0,
        })

    return JSONResponse({"theme_name": theme_name, "sources": sources})


@app.post("/api/generate")
async def generate(request: Request):
    """Generate script + companion materials."""
    body = await request.json()
    theme_name = body.get("theme_name", "")
    sources = body.get("sources", [])

    if not theme_name:
        return JSONResponse({"error": "theme_name required"}, status_code=400)

    settings = _get_settings()
    ensure_dir(_OUTPUT_DIR)

    from datetime import datetime
    from zoneinfo import ZoneInfo
    from ai_podcast_pipeline.constants import TIMEZONE
    from ai_podcast_pipeline.models import CandidateStory

    episode_dt = datetime.now(ZoneInfo(TIMEZONE))
    episode_number = resolve_episode_number(_OUTPUT_DIR)
    episode_name = resolve_episode_name(_OUTPUT_DIR, now=episode_dt)
    paths = build_artifact_paths(_OUTPUT_DIR, episode_name)

    # Rebuild CandidateStory objects from source data.
    from ai_podcast_pipeline.utils import parse_datetime
    candidates = []
    for s in sources:
        pub = None
        if s.get("published_at"):
            try:
                pub = datetime.fromisoformat(s["published_at"])
            except Exception:
                pass
        candidates.append(CandidateStory(
            title=s["title"],
            url=s["url"],
            source_domain=s["source_domain"],
            published_at=pub,
            summary=s.get("summary", ""),
            full_text=s.get("full_text"),
        ))

    selected = [score_story(c) for c in candidates]
    selected_indices = list(range(1, len(selected) + 1))
    verifications = [VerificationResult(story=s, passed=True, reason=None) for s in selected]

    write_json(
        paths["sources_json"],
        _sources_payload(len(selected), selected, selected_indices, verifications),
    )

    # Generate script.
    chosen_theme = ThemeCandidate(name=theme_name, description="", article_indices=selected_indices)
    previous_fot = _load_previous_food_for_thought(_OUTPUT_DIR)

    script_markdown, parts, rewrite_attempts, explicit_fail_state = _stage_generate_theme_script(
        chosen_theme, selected, settings, previous_food_for_thought=previous_fot,
    )

    script_payload = build_theme_script_json(parts, selected, script_markdown)
    script_payload["episode_name"] = episode_name
    script_payload["generated_at"] = iso_utc_now()
    script_payload["rewrite_attempts"] = rewrite_attempts
    script_payload["explicit_fail_state"] = explicit_fail_state

    paths["script_md"].write_text(script_markdown, encoding="utf-8")
    write_json(paths["script_json"], script_payload)

    # Companion materials.
    _generate_companion_materials(parts, script_markdown, episode_name, paths)

    # Render cover.
    from ai_podcast_pipeline.pipeline import _stage_render_cover
    cover_probe_hash = _stage_render_cover(
        episode_name=episode_name,
        episode_dt=episode_dt,
        episode_number=episode_number,
        cover_path=paths["cover_png"],
    )

    # Update theme bank.
    bank_id = body.get("bank_id")
    if bank_id:
        theme_bank_path = Path(THEME_BANK_PATH)
        bank_entries = load_theme_bank(theme_bank_path)
        mark_theme_used(bank_entries, bank_id)
        save_theme_bank(theme_bank_path, bank_entries)

    # Write manifest (no audio yet).
    manifest = {
        "episode_name": episode_name,
        "episode_number": episode_number,
        "created_at": iso_utc_now(),
        "run_status": "success",
        "files": {k: str(v) for k, v in paths.items()},
        "notes": [],
    }
    write_json(paths["manifest_json"], manifest)

    teams_post = paths["teams_post"].read_text(encoding="utf-8") if paths["teams_post"].exists() else ""
    try_this = paths["try_this"].read_text(encoding="utf-8") if paths["try_this"].exists() else ""

    return JSONResponse({
        "episode_name": episode_name,
        "script": script_markdown,
        "teams_post": teams_post,
        "try_this": try_this,
        "word_count": count_words(script_markdown),
        "cover_url": f"/api/files/{episode_name} - Cover.png",
    })


@app.post("/api/audio")
async def generate_audio(request: Request):
    """Generate TTS audio for an episode."""
    body = await request.json()
    episode_name = body.get("episode_name", "")
    if not episode_name:
        return JSONResponse({"error": "episode_name required"}, status_code=400)

    settings = _get_settings()
    paths = build_artifact_paths(_OUTPUT_DIR, episode_name)

    script_path = paths["script_md"]
    if not script_path.exists():
        return JSONResponse({"error": "Script not found"}, status_code=404)

    script_markdown = script_path.read_text(encoding="utf-8")

    from datetime import datetime
    from zoneinfo import ZoneInfo
    from ai_podcast_pipeline.constants import TIMEZONE
    episode_dt = datetime.now(ZoneInfo(TIMEZONE))
    episode_number = resolve_episode_number(_OUTPUT_DIR)

    audio_generated, provider, notes, audio_error = _stage_audio(
        script_markdown=script_markdown,
        settings=settings,
        mp3_path=paths["mp3"],
        cover_path=paths["cover_png"],
        episode_name=episode_name,
        episode_number=episode_number,
        episode_dt=episode_dt,
        skip_audio=False,
        auto_confirm=True,
        explicit_fail_state=False,
    )

    if audio_error:
        return JSONResponse({"error": audio_error, "notes": notes}, status_code=500)

    return JSONResponse({
        "audio_url": f"/api/files/{episode_name}.mp3",
        "provider": provider,
        "notes": notes,
    })


@app.get("/api/files/{path:path}")
async def serve_file(path: str):
    """Serve output files."""
    file_path = _OUTPUT_DIR / path
    if not file_path.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)
    return FileResponse(str(file_path))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.app:app", host="127.0.0.1", port=8000, reload=True)
