#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf


@dataclass
class ClipReport:
    clip_id: str
    src_path: str
    out_path: str
    transcript: str
    duration_s: float
    sample_rate: int
    rms_dbfs: float
    peak: float
    clipping_ratio: float
    passed: bool
    warnings: list[str]


def _dbfs(wav: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(np.square(wav), dtype=np.float64)))
    return 20.0 * math.log10(max(rms, 1e-12))


def _load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader]
    required = {"clip_id", "audio_path", "transcript"}
    missing = required - set(rows[0].keys()) if rows else required
    if missing:
        raise ValueError(f"Manifest is missing required columns: {sorted(missing)}")
    return rows


def _process_clip(row: dict[str, str], refs_dir: Path) -> ClipReport | None:
    clip_id = (row.get("clip_id") or "").strip()
    src = (row.get("audio_path") or "").strip()
    transcript = (row.get("transcript") or "").strip()
    if not clip_id or not src:
        return None
    if not transcript:
        transcript = (row.get("text") or "").strip()

    src_path = Path(src).expanduser()
    if not src_path.exists():
        raise FileNotFoundError(f"Audio file not found for {clip_id}: {src_path}")

    wav, sr = librosa.load(str(src_path), sr=None, mono=True)
    wav = wav.astype(np.float32)
    if wav.size == 0:
        raise ValueError(f"Empty audio file for {clip_id}: {src_path}")

    # Trim leading/trailing room tone so prompt extraction is stable.
    wav, _ = librosa.effects.trim(wav, top_db=35)
    if wav.size == 0:
        raise ValueError(f"All-silence audio for {clip_id}: {src_path}")

    if sr != 24000:
        wav = librosa.resample(wav, orig_sr=sr, target_sr=24000)
        sr = 24000

    peak = float(np.max(np.abs(wav)))
    if peak > 0:
        wav = (wav / peak) * 0.89
    peak = float(np.max(np.abs(wav)))

    duration_s = float(len(wav) / sr)
    rms_dbfs = _dbfs(wav)
    clipping_ratio = float(np.mean(np.abs(wav) >= 0.999))

    warnings: list[str] = []
    if duration_s < 2.5:
        warnings.append("too_short")
    if duration_s > 20.0:
        warnings.append("too_long")
    if rms_dbfs < -34.0:
        warnings.append("too_quiet")
    if rms_dbfs > -12.0:
        warnings.append("too_loud")
    if clipping_ratio > 0.0005:
        warnings.append("possible_clipping")

    passed = len(warnings) == 0

    out_path = refs_dir / f"{clip_id}.wav"
    sf.write(str(out_path), wav, sr)

    return ClipReport(
        clip_id=clip_id,
        src_path=str(src_path),
        out_path=str(out_path),
        transcript=transcript,
        duration_s=duration_s,
        sample_rate=sr,
        rms_dbfs=rms_dbfs,
        peak=peak,
        clipping_ratio=clipping_ratio,
        passed=passed,
        warnings=warnings,
    )


def _write_profile_manifest(path: Path, reports: list[ClipReport]) -> None:
    fieldnames = [
        "clip_id",
        "audio_path",
        "transcript",
        "duration_s",
        "sample_rate",
        "rms_dbfs",
        "peak",
        "clipping_ratio",
        "passed",
        "warnings",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in reports:
            writer.writerow(
                {
                    "clip_id": r.clip_id,
                    "audio_path": r.out_path,
                    "transcript": r.transcript,
                    "duration_s": f"{r.duration_s:.3f}",
                    "sample_rate": r.sample_rate,
                    "rms_dbfs": f"{r.rms_dbfs:.2f}",
                    "peak": f"{r.peak:.4f}",
                    "clipping_ratio": f"{r.clipping_ratio:.6f}",
                    "passed": "yes" if r.passed else "no",
                    "warnings": ",".join(r.warnings),
                }
            )


def _write_report(path: Path, profile_id: str, reports: list[ClipReport]) -> None:
    passed = [r for r in reports if r.passed]
    total_seconds = sum(r.duration_s for r in reports)
    passed_seconds = sum(r.duration_s for r in passed)
    ready = len(passed) >= 8 and passed_seconds >= 90.0

    lines = [
        f"# Voice Profile Report: {profile_id}",
        "",
        f"- clips_total: {len(reports)}",
        f"- clips_passed: {len(passed)}",
        f"- seconds_total: {total_seconds:.1f}",
        f"- seconds_passed: {passed_seconds:.1f}",
        f"- ready_for_reuse: {'yes' if ready else 'no'}",
        "",
        "## Clip Diagnostics",
    ]

    for r in reports:
        warn = ",".join(r.warnings) if r.warnings else "none"
        lines.append(
            f"- {r.clip_id}: pass={'yes' if r.passed else 'no'}, "
            f"dur={r.duration_s:.2f}s, rms={r.rms_dbfs:.1f} dBFS, warnings={warn}"
        )

    lines.extend(
        [
            "",
            "## Quality Targets",
            "- At least 8 passed clips",
            "- At least 90 seconds of passed audio",
            "- Typical clip duration 3-12 seconds",
            "- Low room noise and no clipping",
            "",
            "If `ready_for_reuse` is `no`, re-record clips flagged in diagnostics.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and normalize recorded clips into a reusable voice profile.")
    parser.add_argument("--manifest", required=True, help="Path to filled recording manifest CSV.")
    parser.add_argument("--profile-id", default="jeff_v1", help="Profile id output folder name.")
    parser.add_argument("--output-dir", default="voice_profiles", help="Root directory for generated profile files.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    out_root = Path(args.output_dir).expanduser().resolve() / args.profile_id
    refs_dir = out_root / "refs"
    out_root.mkdir(parents=True, exist_ok=True)
    refs_dir.mkdir(parents=True, exist_ok=True)

    rows = _load_manifest(manifest_path)
    reports: list[ClipReport] = []
    for row in rows:
        report = _process_clip(row, refs_dir)
        if report:
            reports.append(report)

    if not reports:
        raise ValueError("No usable clips found in manifest. Fill `audio_path` rows and rerun.")

    profile_manifest = out_root / "profile_manifest.csv"
    report_md = out_root / "profile_report.md"
    profile_json = out_root / "profile.json"

    _write_profile_manifest(profile_manifest, reports)
    _write_report(report_md, args.profile_id, reports)

    passed = [r for r in reports if r.passed]
    payload = {
        "profile_id": args.profile_id,
        "source_manifest": str(manifest_path),
        "profile_manifest": str(profile_manifest),
        "clips_total": len(reports),
        "clips_passed": len(passed),
        "seconds_total": round(sum(r.duration_s for r in reports), 3),
        "seconds_passed": round(sum(r.duration_s for r in passed), 3),
        "ready_for_reuse": len(passed) >= 8 and sum(r.duration_s for r in passed) >= 90.0,
    }
    profile_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(profile_manifest)
    print(report_md)
    print(profile_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
