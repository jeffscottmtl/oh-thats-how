#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path


TRAINING_LINES = [
    "Welcome to The Signal, where we break down the AI shifts that matter for communications teams.",
    "This week, we focus on practical changes, not hype, and what they mean for daily work.",
    "At CN, our goal is simple: communicate clearly, move quickly, and stay grounded in evidence.",
    "If a tool saves time but increases confusion, it is not an upgrade; it is technical debt.",
    "A strong message has three parts: what changed, why it matters, and what happens next.",
    "When you brief leaders, lead with the decision, then back it up with concise context.",
    "In fast-moving cycles, consistency beats novelty, especially when your audience spans many teams.",
    "For internal updates, clarity and timing matter more than perfect wording.",
    "A useful AI workflow is repeatable, measurable, and easy for others to adopt.",
    "When pilots succeed, document the process so results can scale across the organization.",
    "Today we reviewed automation in media monitoring, draft writing, and stakeholder updates.",
    "The value is not just speed; it is better judgment at the right moment.",
    "Teams that define quality standards early avoid rework later.",
    "In communications, trust is built in small moments, one clear message at a time.",
    "If the signal is weak, add context, not more volume.",
    "Our audience includes operators, leaders, partners, and communities, each with different needs.",
    "Good communication connects strategy to daily execution without losing either.",
    "We use AI to improve first drafts, then rely on humans for final accountability.",
    "For sensitive topics, we slow down, verify facts, and align before publishing.",
    "When priorities shift, reset expectations quickly and document the new plan.",
    "Here is the update for March 2, 2026, covering the week ahead.",
    "We reviewed five themes, two risks, and one immediate action for this quarter.",
    "The trial covered nine teams across three regions and two reporting cycles.",
    "Response time improved by 18 percent after we standardized templates and approvals.",
    "Use plain language first, then add technical detail only when needed.",
    "Say the acronym once in full, then use the short form for the rest of the brief.",
    "For example: artificial intelligence, or AI, now appears in nearly every planning conversation.",
    "If you hear conflicting guidance, escalate early and align the final source of truth.",
    "Thanks for listening to The Signal; we will see you next week.",
    "One more thing: faster tools are only useful when they support better decisions.",
]


def _write_recording_script(path: Path, speaker_name: str) -> None:
    lines = [
        f"# Qwen3 Voice Training Script ({speaker_name})",
        "",
        "Recording guidance:",
        "- Read naturally, as if delivering a polished internal podcast.",
        "- Record in a quiet room with the same microphone setup for every clip.",
        "- Leave 0.5-1.0 seconds of silence at the start and end of each clip.",
        "- Keep pace steady; avoid whispering, shouting, or dramatic acting.",
        "- If you stumble, restart the full line.",
        "",
        "Target quality:",
        "- 3-12 seconds per clip",
        "- Mono or stereo is fine (we will normalize later)",
        "- WAV preferred, MP3 acceptable",
        "",
        "## Lines To Record",
        "",
    ]
    for idx, text in enumerate(TRAINING_LINES, start=1):
        lines.append(f"{idx:02d}. {text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_manifest_template(path: Path) -> None:
    fieldnames = ["clip_id", "text", "transcript", "audio_path", "notes"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for idx, text in enumerate(TRAINING_LINES, start=1):
            writer.writerow(
                {
                    "clip_id": f"clip_{idx:02d}",
                    "text": text,
                    "transcript": text,
                    "audio_path": "",
                    "notes": "",
                }
            )


def _write_next_steps(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# Next Steps",
                "",
                "1. Record all lines in `recording_script.md`.",
                "2. Fill `recording_manifest_template.csv` with absolute file paths in `audio_path`.",
                "3. Keep `transcript` exactly what was spoken (edit if you improvised).",
                "4. Run:",
                "   ./scripts/qwen3_voice_profile_prepare.sh --manifest /absolute/path/to/recording_manifest_template.csv --profile-id jeff_v1",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a reusable Qwen3 voice-clone recording pack.")
    parser.add_argument("--speaker-name", default="Jeff Scott", help="Speaker name label.")
    parser.add_argument("--profile-id", default="jeff_v1", help="Profile id folder name.")
    parser.add_argument(
        "--output-dir",
        default="voice_profiles",
        help="Root output directory where training pack will be created.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(args.output_dir).expanduser().resolve() / args.profile_id / "training_pack"
    root.mkdir(parents=True, exist_ok=True)

    script_path = root / "recording_script.md"
    manifest_path = root / "recording_manifest_template.csv"
    next_steps_path = root / "next_steps.md"

    _write_recording_script(script_path, args.speaker_name)
    _write_manifest_template(manifest_path)
    _write_next_steps(next_steps_path)

    print(script_path)
    print(manifest_path)
    print(next_steps_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
