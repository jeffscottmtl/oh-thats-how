from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .constants import TIMEZONE


def format_episode_date(dt: datetime) -> str:
    local_dt = dt.astimezone(ZoneInfo(TIMEZONE))
    return f"{local_dt.strftime('%B')} {local_dt.day}, {local_dt.year}"


def build_episode_base_name(now: datetime | None = None) -> str:
    dt = (now or datetime.now(ZoneInfo(TIMEZONE))).astimezone(ZoneInfo(TIMEZONE))
    return f"The Signal \u2013 {format_episode_date(dt)}"


def resolve_episode_number(output_dir: Path) -> int:
    manifests = sorted(output_dir.glob("The Signal \u2013 * - Manifest.json"))

    max_number = 0
    for manifest_path in manifests:
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        value = payload.get("episode_number")
        if isinstance(value, int) and value > max_number:
            max_number = value

    if max_number > 0:
        return max_number + 1
    return len(manifests) + 1


def resolve_episode_name(output_dir: Path, now: datetime | None = None) -> str:
    base = build_episode_base_name(now=now)
    candidate = base
    suffix = 2
    while (output_dir / f"{candidate} - Manifest.json").exists():
        candidate = f"{base} {suffix}"
        suffix += 1
    return candidate


def build_artifact_paths(output_dir: Path, episode_name: str) -> dict[str, Path]:
    return {
        "script_md": output_dir / f"{episode_name} - Script.md",
        "script_json": output_dir / f"{episode_name} - Script.json",
        "sources_json": output_dir / f"{episode_name} - Sources.json",
        "cover_png": output_dir / f"{episode_name} - Cover.png",
        "mp3": output_dir / f"{episode_name}.mp3",
        "manifest_json": output_dir / f"{episode_name} - Manifest.json",
    }
