"""
FastAPI web server for The Signal podcast pipeline.

Run from the project root:
    uvicorn web.server:app --port 8765 --reload
Or via launch.command.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from queue import Empty, Queue  # Queue kept for potential future use
from typing import Any, Optional

from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── project root on Python path ──────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from ai_podcast_pipeline.artifacts import (
    build_artifact_paths,
    resolve_episode_name,
    resolve_episode_number,
)
from ai_podcast_pipeline.audio import QwenTTSError, synthesize_qwen_clone_mp3
from ai_podcast_pipeline.config import load_settings
from ai_podcast_pipeline.constants import (
    MAX_PER_SOURCE_WEEK,
    MAX_SHORTLIST,
    OUTRO_TEXT,
    RSS_FEEDS,
    TIMEZONE,
)
from ai_podcast_pipeline.cover import render_cover
from ai_podcast_pipeline.ingest import fetch_article_text, fetch_candidates, fetch_candidates_newsapi
from ai_podcast_pipeline.models import CandidateStory, QaResult, ScoredStory
from ai_podcast_pipeline.pipeline import (
    _apply_weekly_per_source_cap,
    _cap_full_list,
    _episode_word_targets,
    _filter_by_date_window,
    _passes_local_candidate_checks,
    _stage_generate_script,
)
from ai_podcast_pipeline.qa import run_qa
from ai_podcast_pipeline.scoring import is_relevant_story, score_story, story_sort_key
from ai_podcast_pipeline.script_writer import build_script_json
from ai_podcast_pipeline.utils import (
    count_words,
    ensure_dir,
    iso_utc_now,
    load_optional_env_file,
    now_toronto,
    parse_datetime,
    write_json,
)
from ai_podcast_pipeline.verification import verify_selection

logger = logging.getLogger(__name__)

# ── app setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title="The Signal")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = ROOT / "output"
ENV_FILE = ROOT / ".env"
SCHEMA_DIR = ROOT / "schemas"
STATIC_DIR = Path(__file__).parent / "static"

# In-memory job registry.
_jobs: dict[str, dict[str, Any]] = {}


def _tts_device_label() -> str:
    """Human-readable TTS device label for progress events."""
    device = os.environ.get("QWEN3_TTS_DEVICE", "mps").lower()
    return {"mps": "Metal (MPS)", "cuda": "CUDA", "cpu": "CPU"}.get(device, device.upper())


def _load_settings(skip_audio: bool = False):
    if ENV_FILE.exists():
        load_optional_env_file(ENV_FILE)
    return load_settings(
        story_count=3,
        allow_domains=None,
        skip_audio=skip_audio,
        env_file=str(ENV_FILE) if ENV_FILE.exists() else None,
    )


# ── static + index ────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


# ── /api/stories ──────────────────────────────────────────────────────────────
@app.get("/api/stories")
def get_stories(
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
):
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError:
        raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")

    if end_date < start_date:
        raise HTTPException(400, "end must be on or after start.")

    try:
        settings = _load_settings(skip_audio=True)
    except Exception as exc:
        raise HTTPException(500, f"Configuration error: {exc}")

    # Freshness is measured relative to the search window's end date, not today,
    # so historical queries aren't penalised (a Dec article is "fresh" re: Dec 31).
    tz = ZoneInfo("America/Toronto")
    freshness_ref = datetime.combine(end_date, datetime.min.time()).replace(tzinfo=tz)

    # Choose source: NewsAPI for anything older than 7 days (RSS feeds don't
    # retain articles that long); RSS for current / near-current searches.
    today = date.today()
    days_since_end = (today - end_date).days
    news_api_key = os.getenv("NEWS_API_KEY", "")

    if days_since_end > 7 and news_api_key:
        logger.info("Historical search (%d days old) — using NewsAPI.", days_since_end)
        candidates = fetch_candidates_newsapi(
            start_date=start_date,
            end_date=end_date,
            api_key=news_api_key,
        )
    else:
        logger.info("Recent search — using RSS feeds.")
        candidates = fetch_candidates()

    scored_all = [score_story(c, reference_date=freshness_ref) for c in candidates]

    full_list: list[ScoredStory] = []
    for item in scored_all:
        ok, _ = _passes_local_candidate_checks(item, settings.user_approved_domains)
        if ok and is_relevant_story(item):
            full_list.append(item)

    full_list, _ = _filter_by_date_window(full_list, start_date, end_date)
    full_list.sort(key=story_sort_key)
    full_list, _ = _apply_weekly_per_source_cap(full_list, MAX_PER_SOURCE_WEEK)
    full_list, _ = _cap_full_list(full_list, MAX_SHORTLIST)

    return [_story_to_dict(i, s) for i, s in enumerate(full_list)]


def _story_to_dict(index: int, story: ScoredStory) -> dict:
    c = story.candidate
    return {
        "index": index,
        "title": c.title,
        "url": c.url,
        "source_domain": c.source_domain,
        "published_at": c.published_at.isoformat() if c.published_at else None,
        "summary": (c.summary or "")[:500],
        "scores": {
            "credibility": story.credibility,
            "comms_relevance": story.comms_relevance,
            "freshness": story.freshness,
            "ai_materiality": story.ai_materiality,
            "preferred_topic": story.preferred_topic,
            "total": round(story.total, 1),
        },
    }


# ── /api/article ──────────────────────────────────────────────────────────────
@app.get("/api/article")
def get_article(url: str = Query(...)):
    text = fetch_article_text(url)
    if text is None:
        return {"text": None, "word_count": 0, "error": "Could not fetch article (paywall or bot-blocked)"}
    return {"text": text, "word_count": len(text.split()), "error": None}


# ── /api/outputs ──────────────────────────────────────────────────────────────
@app.get("/api/outputs")
def list_outputs():
    ensure_dir(OUTPUT_DIR)
    episodes = []
    for manifest_path in sorted(OUTPUT_DIR.glob("* - Manifest.json"), reverse=True):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            ep_name = manifest_path.stem.replace(" - Manifest", "")
            paths = build_artifact_paths(OUTPUT_DIR, ep_name)
            episodes.append({
                "name": ep_name,
                "episode_number": data.get("episode_number"),
                "created_at": data.get("created_at"),
                "run_status": data.get("run_status"),
                "word_count": data.get("word_count"),
                "has_audio": paths["mp3"].exists(),
                "has_cover": paths["cover_png"].exists(),
                "has_script": paths["script_md"].exists(),
            })
        except Exception:
            continue
    return episodes


@app.get("/api/outputs/{episode_name}/audio")
def serve_audio(episode_name: str):
    mp3 = OUTPUT_DIR / f"{episode_name}.mp3"
    if not mp3.exists():
        raise HTTPException(404, "Audio not found")
    return FileResponse(str(mp3), media_type="audio/mpeg")


@app.get("/api/outputs/{episode_name}/cover")
def serve_cover(episode_name: str):
    cover = OUTPUT_DIR / f"{episode_name} - Cover.png"
    if not cover.exists():
        raise HTTPException(404, "Cover not found")
    return FileResponse(str(cover), media_type="image/png")


@app.get("/api/outputs/{episode_name}/script")
def serve_script(episode_name: str):
    script_md = OUTPUT_DIR / f"{episode_name} - Script.md"
    if not script_md.exists():
        raise HTTPException(404, "Script not found")
    return {"script": script_md.read_text(encoding="utf-8")}


# ── /api/generate ─────────────────────────────────────────────────────────────
class StoryInput(BaseModel):
    title: str
    url: str
    source_domain: str
    published_at: Optional[str] = None
    summary: str = ""
    full_text: Optional[str] = None
    credibility: int = 70
    comms_relevance: int = 0
    freshness: int = 80
    ai_materiality: int = 0
    preferred_topic: int = 0
    total: float = 50.0


class GenerateRequest(BaseModel):
    stories: list[StoryInput]
    skip_audio: bool = False


@app.post("/api/generate")
def start_generate(req: GenerateRequest):
    if not req.stories:
        raise HTTPException(400, "No stories selected")
    if len(req.stories) > 6:
        raise HTTPException(400, "Maximum 6 stories per episode")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "events": [],                   # append-only; never consumed/removed
        "events_lock": threading.Lock(),
        "status": "running",
        "approval_event": threading.Event(),
        "approved_script": None,
    }

    t = threading.Thread(
        target=_run_generation,
        args=(job_id, req),
        daemon=True,
    )
    t.start()
    return {"job_id": job_id}


# ── /api/generate/{job_id}/approve — resume after script review ───────────────
class ApproveRequest(BaseModel):
    script: str


@app.post("/api/generate/{job_id}/approve")
def approve_script(job_id: str, body: ApproveRequest):
    if job_id not in _jobs:
        raise HTTPException(404, "Job not found")
    job = _jobs[job_id]
    job["approved_script"] = body.script.strip()
    job["approval_event"].set()
    return {"ok": True}


# ── /api/generate/{job_id}/retry-audio — re-run audio for completed job ───────
@app.post("/api/generate/{job_id}/retry-audio")
def retry_audio(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, "Job not found")

    # Find episode_name from the complete event
    episode_name = None
    for event in _jobs[job_id]["events"]:
        if event.get("type") == "complete":
            episode_name = event.get("episode_name")
            break

    if not episode_name:
        raise HTTPException(400, "No completed episode found for this job — cannot retry audio")

    script_path = OUTPUT_DIR / f"{episode_name} - Script.md"
    if not script_path.exists():
        raise HTTPException(400, f"Script file not found for episode: {episode_name}")

    script_md = script_path.read_text(encoding="utf-8")

    new_job_id = str(uuid.uuid4())
    _jobs[new_job_id] = {
        "events": [],
        "events_lock": threading.Lock(),
        "status": "running",
        "approval_event": threading.Event(),
        "approved_script": None,
    }

    t = threading.Thread(
        target=_run_retry_audio,
        args=(new_job_id, episode_name, script_md),
        daemon=True,
    )
    t.start()
    return {"job_id": new_job_id}


def _run_retry_audio(job_id: str, episode_name: str, script_md: str) -> None:
    job = _jobs[job_id]

    def emit(event_type: str, **data: Any) -> None:
        with job["events_lock"]:
            job["events"].append({"type": event_type, **data})

    try:
        settings = _load_settings()
        paths = build_artifact_paths(OUTPUT_DIR, episode_name)

        emit("progress", stage="audio",
             message="Generating audio — this takes a few minutes…",
             detail=f"Qwen TTS · {_tts_device_label()}", pct=0)
        try:
            synthesize_qwen_clone_mp3(
                profile_manifest_path=Path(settings.qwen_profile_manifest),
                model_id=settings.qwen_tts_model,
                text=script_md,
                output_path=paths["mp3"],
                cover_art_path=paths["cover_png"],
                episode_name=episode_name,
                ref_clip_id=settings.qwen_ref_clip_id,
                language=settings.qwen_tts_language,
                instruct=settings.qwen_tts_instruct,
                temperature=settings.qwen_tts_temperature,
                top_p=settings.qwen_tts_top_p,
                top_k=settings.qwen_tts_top_k,
                max_new_tokens=settings.qwen_tts_max_new_tokens,
                speed=settings.qwen_tts_speed,
                timeout=settings.qwen_tts_timeout_seconds,
            )
            emit("progress", stage="audio", message="Audio complete", detail="", pct=100)

            # Update manifest to record mp3
            if paths["manifest_json"].exists():
                manifest = json.loads(paths["manifest_json"].read_text(encoding="utf-8"))
                manifest["run_status"] = "passed"
                manifest.setdefault("files", {})["mp3"] = paths["mp3"].name
                write_json(paths["manifest_json"], manifest)

            emit("complete",
                 episode_name=episode_name,
                 audio_generated=True,
                 audio_error=None,
                 audio_url=f"/api/outputs/{episode_name}/audio",
                 cover_url=f"/api/outputs/{episode_name}/cover" if paths["cover_png"].exists() else None,
                 )
        except QwenTTSError as exc:
            error_msg = str(exc)
            emit("progress", stage="audio",
                 message="Audio generation failed",
                 detail=error_msg[:80], pct=100)
            emit("error", stage="audio", message=error_msg)

    except Exception as exc:
        logger.exception("Unexpected error in retry-audio job %s", job_id)
        emit("error", stage="unknown", message=str(exc))


# ── /api/generate/{job_id}/stream — SSE ───────────────────────────────────────
@app.get("/api/generate/{job_id}/stream")
async def stream_job(job_id: str, request: Request, after: int = Query(0)):
    """Stream generation events as SSE.

    Use ?after=N to reconnect mid-job (e.g. after script approval) and receive
    only the events emitted after the first N.  Events are stored in an
    append-only list so no event is ever lost due to reconnection races.
    """
    if job_id not in _jobs:
        raise HTTPException(404, "Job not found")

    job = _jobs[job_id]

    async def event_gen():
        pos = max(0, after)
        while True:
            # Stop if the client has gone away
            if await request.is_disconnected():
                break

            events = job["events"]
            if pos < len(events):
                event = events[pos]
                pos += 1
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in ("complete", "error"):
                    break
            else:
                # No new events yet — yield a ping and wait briefly
                yield "data: {\"type\":\"ping\"}\n\n"
                await asyncio.sleep(0.25)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── generation worker (runs in background thread) ─────────────────────────────
def _run_generation(job_id: str, req: GenerateRequest) -> None:
    job = _jobs[job_id]

    def emit(event_type: str, **data: Any) -> None:
        with job["events_lock"]:
            job["events"].append({"type": event_type, **data})

    try:
        # ── load settings ─────────────────────────────────────────────────────
        try:
            settings = _load_settings(skip_audio=req.skip_audio)
        except Exception as exc:
            emit("error", stage="init", message=f"Configuration error: {exc}")
            return

        stories = req.stories
        n = len(stories)

        # ── stage 1: fetch any missing article text ───────────────────────────
        emit("progress", stage="fetch", message="Fetching article text…", detail="", pct=0)
        for i, s in enumerate(stories):
            if not s.full_text:
                emit("progress", stage="fetch",
                     message=f"Fetching article {i + 1} of {n}…",
                     detail=s.title[:60], pct=int(i / n * 100))
                s.full_text = fetch_article_text(s.url)
        emit("progress", stage="fetch", message="Article text ready", detail="", pct=100)

        missing = [s.title for s in stories if not s.full_text]
        if missing:
            emit("error", stage="fetch",
                 message=f"Could not fetch full text for: {', '.join(missing[:3])}. "
                         f"Please use the Preview button and paste manually.")
            return

        # ── build ScoredStory objects ─────────────────────────────────────────
        selected: list[ScoredStory] = []
        for s in stories:
            candidate = CandidateStory(
                title=s.title,
                url=s.url,
                source_domain=s.source_domain,
                published_at=parse_datetime(s.published_at) if s.published_at else None,
                summary=s.summary,
                full_text=s.full_text,
            )
            scored = ScoredStory(
                candidate=candidate,
                credibility=s.credibility,
                comms_relevance=s.comms_relevance,
                freshness=s.freshness,
                ai_materiality=s.ai_materiality,
                preferred_topic=s.preferred_topic,
                total=s.total,
            )
            selected.append(scored)

        # ── stage 2: generate script ──────────────────────────────────────────
        _, _, aim_w = _episode_word_targets(len(selected))
        emit("progress", stage="script",
             message=f"Writing script ({settings.openai_model})…",
             detail=f"Targeting ~{aim_w} words • {len(selected)} stor{'y' if len(selected) == 1 else 'ies'}",
             pct=0)

        try:
            script_md, parts, attempts, fail_state, intro_fixed = _stage_generate_script(
                selected, settings
            )
        except Exception as exc:
            emit("error", stage="script", message=f"Script generation failed: {exc}")
            return

        wc = count_words(script_md)
        emit("progress", stage="script",
             message="Script complete",
             detail=f"{wc:,} words{' · ' + str(attempts) + ' rewrite(s)' if attempts else ''}",
             pct=100)

        # ── resolve episode artifacts ─────────────────────────────────────────
        ensure_dir(OUTPUT_DIR)
        episode_dt = now_toronto()
        episode_number = resolve_episode_number(OUTPUT_DIR)
        episode_name = resolve_episode_name(OUTPUT_DIR)
        paths = build_artifact_paths(OUTPUT_DIR, episode_name)

        # ── stage 3: cover art ────────────────────────────────────────────────
        emit("progress", stage="cover", message="Generating cover art…", detail="", pct=0)
        cover_hash = ""
        try:
            from ai_podcast_pipeline.pipeline import _stage_render_cover
            cover_hash = _stage_render_cover(episode_name, episode_dt, episode_number, paths["cover_png"])
            emit("progress", stage="cover", message="Cover ready", detail="", pct=100)
        except Exception as exc:
            emit("progress", stage="cover", message=f"Cover skipped: {exc}", detail="", pct=100)

        # ── script review pause — wait for user approval ─────────────────────
        emit("script_ready",
             script=script_md,
             word_count=wc,
             episode_name=episode_name,
             episode_number=episode_number,
             cover_url=f"/api/outputs/{episode_name}/cover" if paths["cover_png"].exists() else None,
             )

        approved = _jobs[job_id]["approval_event"].wait(timeout=7200)  # 2 hr timeout
        if not approved:
            emit("error", stage="audio", message="Timed out waiting for script approval.")
            return

        # Use the (possibly edited) script the user approved.
        script_md = _jobs[job_id]["approved_script"] or script_md
        wc = count_words(script_md)

        # ── save script files ─────────────────────────────────────────────────
        script_json_data = build_script_json(parts, selected, script_md)
        paths["script_md"].write_text(script_md, encoding="utf-8")
        write_json(paths["script_json"], script_json_data)

        # Write a minimal sources file so QA can open it.
        write_json(paths["sources_json"], {
            "generated_at": iso_utc_now(),
            "selected_count": len(selected),
            "selected_stories": [
                {"title": s.candidate.title, "url": s.candidate.url}
                for s in selected
            ],
        })

        # ── stage 4: audio ────────────────────────────────────────────────────
        audio_generated = False
        audio_error: Optional[str] = None

        if req.skip_audio:
            emit("progress", stage="audio", message="Audio skipped", detail="", pct=100)
        else:
            emit("progress", stage="audio",
                 message="Generating audio — this takes a few minutes…",
                 detail=f"Qwen TTS · {_tts_device_label()}", pct=0)
            try:
                synthesize_qwen_clone_mp3(
                    profile_manifest_path=Path(settings.qwen_profile_manifest),
                    model_id=settings.qwen_tts_model,
                    text=script_md,
                    output_path=paths["mp3"],
                    cover_art_path=paths["cover_png"],
                    episode_name=episode_name,
                    episode_number=episode_number,
                    episode_dt=episode_dt,
                    ref_clip_id=settings.qwen_ref_clip_id,
                    language=settings.qwen_tts_language,
                    instruct=settings.qwen_tts_instruct,
                    temperature=settings.qwen_tts_temperature,
                    top_p=settings.qwen_tts_top_p,
                    top_k=settings.qwen_tts_top_k,
                    max_new_tokens=settings.qwen_tts_max_new_tokens,
                    speed=settings.qwen_tts_speed,
                    timeout=settings.qwen_tts_timeout_seconds,
                )
                audio_generated = True
                emit("progress", stage="audio", message="Audio complete", detail="", pct=100)
            except QwenTTSError as exc:
                audio_error = str(exc)
                emit("progress", stage="audio",
                     message="Audio generation failed",
                     detail=audio_error[:80], pct=100)

        # ── stage 5: QA ───────────────────────────────────────────────────────
        emit("progress", stage="qa", message="Running QA checks…", detail="", pct=0)
        qa_result: Optional[QaResult] = None
        try:
            # Write a temporary manifest so QA can check it.
            _tmp_manifest = {
                "episode_name": episode_name,
                "episode_number": episode_number,
                "run_status": "running",
                "selected_count": len(selected),
                "word_count": wc,
            }
            write_json(paths["manifest_json"], _tmp_manifest)

            qa_result = run_qa(
                episode_name=episode_name,
                script_md_path=paths["script_md"],
                script_json_path=paths["script_json"],
                sources_json_path=paths["sources_json"],
                manifest_json_path=paths["manifest_json"],
                cover_path=paths["cover_png"],
                schema_dir=SCHEMA_DIR,
                selected_indices=list(range(1, len(selected) + 1)),
                selected_verification_passed=True,
                explicit_fail_state_recorded=fail_state,
                cover_determinism_probe_hash=cover_hash,
            )
            qa_label = "Passed ✓" if qa_result.passed else f"{len(qa_result.failures)} warning(s)"
            emit("progress", stage="qa", message="QA complete", detail=qa_label, pct=100)
        except Exception as exc:
            emit("progress", stage="qa", message=f"QA skipped: {exc}", detail="", pct=100)

        # ── save final manifest ───────────────────────────────────────────────
        run_status = "failed" if audio_error else ("passed" if (qa_result and qa_result.passed) else "warning")
        final_manifest = {
            "episode_name": episode_name,
            "episode_number": episode_number,
            "timezone": TIMEZONE,
            "created_at": iso_utc_now(),
            "run_status": run_status,
            "selected_count": len(selected),
            "word_count": wc,
            "qa": {
                "passed": qa_result.passed if qa_result else None,
                "checks": qa_result.checks if qa_result else {},
                "failures": qa_result.failures if qa_result else [],
            },
            "files": {
                "script_md": paths["script_md"].name,
                "cover_png": paths["cover_png"].name if paths["cover_png"].exists() else None,
                "mp3": paths["mp3"].name if audio_generated else None,
            },
        }
        write_json(paths["manifest_json"], final_manifest)

        emit("complete",
             episode_name=episode_name,
             episode_number=episode_number,
             script=script_md,
             word_count=wc,
             audio_generated=audio_generated,
             audio_error=audio_error,
             qa_passed=qa_result.passed if qa_result else None,
             qa_failures=qa_result.failures if qa_result else [],
             run_status=run_status,
             cover_url=f"/api/outputs/{episode_name}/cover" if paths["cover_png"].exists() else None,
             audio_url=f"/api/outputs/{episode_name}/audio" if audio_generated else None,
             )

    except Exception as exc:
        logger.exception("Unexpected error in generation job %s", job_id)
        emit("error", stage="unknown", message=str(exc))


# ── entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    print("\n📡 The Signal — starting web server…")
    print("   Open http://localhost:8765 in your browser\n")
    os.chdir(ROOT)
    uvicorn.run("web.server:app", host="127.0.0.1", port=8765, reload=False)
