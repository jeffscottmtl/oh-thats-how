#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path

import soundfile as sf
import torch
from qwen_tts import Qwen3TTSModel


def _load_env_file(env_file: Path) -> None:
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _parse_dtype(dtype_name: str) -> torch.dtype:
    mapping = {
        "float32": torch.float32,
        "fp32": torch.float32,
        "float16": torch.float16,
        "fp16": torch.float16,
        "bfloat16": torch.bfloat16,
        "bf16": torch.bfloat16,
    }
    key = dtype_name.strip().lower()
    if key not in mapping:
        valid = ", ".join(sorted(mapping))
        raise ValueError(f"Unsupported dtype '{dtype_name}'. Use one of: {valid}")
    return mapping[key]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synthesize speech with Qwen3-TTS (voice clone for Base models, custom voice for CustomVoice models)"
    )
    parser.add_argument("--env-file", default=".env.qwen3-tts", help="Optional env file to load defaults from")
    parser.add_argument("--text", required=True, help="Text to synthesize in cloned voice")
    parser.add_argument("--output", default="qwen3_tts_clone_output.wav", help="Output WAV path")
    parser.add_argument(
        "--segments-file",
        default=None,
        help="Path to a text file with one segment per line (double-newline delimited). "
             "When provided, --text is ignored and each segment is synthesized sequentially "
             "with the model loaded once. Output files are numbered: output_001.wav, output_002.wav, etc.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("QWEN3_TTS_CLONE_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-Base"),
        help="Qwen TTS model ID or local model path",
    )
    parser.add_argument(
        "--ref-audio",
        action="append",
        default=[],
        help="Reference audio path; pass twice to use two files",
    )
    parser.add_argument(
        "--ref-text",
        action="append",
        default=[],
        help="Transcript for each reference audio; optional if --x-vector-only",
    )
    parser.add_argument("--x-vector-only", action="store_true", help="Use embedding-only clone mode (no transcripts)")
    parser.add_argument("--language", default="Auto", help="Synthesis language (Auto recommended)")
    parser.add_argument(
        "--instruct",
        default=os.getenv("QWEN3_TTS_CLONE_INSTRUCT", ""),
        help="Optional style/prosody instruction for more expressive delivery",
    )
    parser.add_argument(
        "--speaker",
        default=os.getenv("QWEN3_TTS_CUSTOM_SPEAKER", ""),
        help="CustomVoice speaker ID/name override (used only for CustomVoice models)",
    )
    parser.add_argument(
        "--device",
        default=os.getenv("QWEN3_TTS_DEVICE", "cpu"),
        help="Device map value (cpu or cuda:0)",
    )
    parser.add_argument(
        "--dtype",
        default=os.getenv("QWEN3_TTS_DTYPE", "float32"),
        help="Torch dtype (float32, float16, bfloat16)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=float(os.getenv("QWEN3_TTS_CLONE_TEMPERATURE", "0.72")),
        help="Generation temperature (higher = more expressive variability)",
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=float(os.getenv("QWEN3_TTS_CLONE_TOP_P", "0.92")),
        help="Nucleus sampling top_p",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=int(os.getenv("QWEN3_TTS_CLONE_TOP_K", "45")),
        help="Top-k sampling",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=int(os.getenv("QWEN3_TTS_CLONE_MAX_NEW_TOKENS", "4096")),
        help="Generation max_new_tokens",
    )
    return parser


def _resolve_refs(ref_audio: list[str], ref_text: list[str], x_vector_only: bool):
    n = len(ref_audio)
    if n == 1:
        if ref_text and len(ref_text) > 1:
            raise ValueError("For one --ref-audio, provide at most one --ref-text.")
        text_val = ref_text[0] if ref_text else None
        xvec_val = x_vector_only or text_val is None
        return ref_audio[0], text_val, xvec_val

    if ref_text and len(ref_text) not in {1, n}:
        raise ValueError(f"For {n} --ref-audio files, provide either 1 or {n} --ref-text values.")

    if not ref_text:
        text_vals = None
    elif len(ref_text) == 1:
        text_vals = [ref_text[0]] * n
    else:
        text_vals = ref_text

    xvec_val = [x_vector_only or text_vals is None] * n
    return ref_audio, text_vals, xvec_val


def _resolve_custom_speaker(model: Qwen3TTSModel, requested: str) -> str | None:
    supported = model.get_supported_speakers()
    if not supported:
        return requested.strip() or None

    if requested.strip():
        requested_lower = requested.strip().lower()
        for candidate in supported:
            if candidate.lower() == requested_lower:
                return candidate

    return supported[0]


def _read_segments_file(segments_file: Path) -> list[str]:
    """Read a segments file where segments are separated by a delimiter line '---'."""
    raw = segments_file.read_text(encoding="utf-8")
    segments = [s.strip() for s in raw.split("\n---\n") if s.strip()]
    return segments


def _generate_one(model, args, text: str, ref_audio_val, ref_text_val, xvec_val) -> tuple:
    """Generate audio for a single text using the already-loaded model."""
    model_type = getattr(model.model, "tts_model_type", "")

    if model_type == "custom_voice":
        speaker = _resolve_custom_speaker(model, args.speaker)
        if not speaker:
            raise ValueError(
                "CustomVoice model requires a speaker. Set --speaker or QWEN3_TTS_CUSTOM_SPEAKER."
            )
        return model.generate_custom_voice(
            text=text,
            speaker=speaker,
            language=args.language,
            instruct=args.instruct if args.instruct else None,
            temperature=args.temperature,
            top_p=args.top_p,
            top_k=args.top_k,
            max_new_tokens=args.max_new_tokens,
        )
    else:
        text_input: str | list[str]
        if isinstance(ref_audio_val, list) and len(ref_audio_val) > 1:
            text_input = [text] * len(ref_audio_val)
        else:
            text_input = text

        return model.generate_voice_clone(
            text=text_input,
            language=args.language,
            instruct=args.instruct if args.instruct else None,
            ref_audio=ref_audio_val,
            ref_text=ref_text_val,
            x_vector_only_mode=xvec_val,
            temperature=args.temperature,
            top_p=args.top_p,
            top_k=args.top_k,
            max_new_tokens=args.max_new_tokens,
        )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    _load_env_file(Path(args.env_file))

    import time
    t0 = time.monotonic()
    model = Qwen3TTSModel.from_pretrained(
        args.model,
        device_map=args.device,
        dtype=_parse_dtype(args.dtype),
    )
    load_time = time.monotonic() - t0
    print(f"[tts] Model loaded in {load_time:.1f}s", flush=True)

    # Resolve reference audio once
    ref_audio_val, ref_text_val, xvec_val = None, None, None
    model_type = getattr(model.model, "tts_model_type", "")
    if model_type != "custom_voice":
        if not args.ref_audio:
            raise ValueError("Base clone models require at least one --ref-audio argument.")
        ref_audio_val, ref_text_val, xvec_val = _resolve_refs(args.ref_audio, args.ref_text, args.x_vector_only)

    # Multi-segment mode: load model once, generate each segment sequentially
    if args.segments_file:
        segments = _read_segments_file(Path(args.segments_file))
        if not segments:
            raise ValueError(f"No segments found in {args.segments_file}")

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)

        print(f"[tts] Generating {len(segments)} segments…", flush=True)
        for idx, seg_text in enumerate(segments):
            seg_t0 = time.monotonic()
            wavs, sample_rate = _generate_one(model, args, seg_text, ref_audio_val, ref_text_val, xvec_val)
            seg_time = time.monotonic() - seg_t0

            seg_path = output.parent / f"{output.stem}_{idx:03d}{output.suffix}"
            sf.write(str(seg_path), wavs[0] if len(wavs) == 1 else wavs[0], sample_rate)
            print(f"[tts] Segment {idx+1}/{len(segments)} done in {seg_time:.1f}s → {seg_path}", flush=True)

        total = time.monotonic() - t0
        print(f"[tts] All {len(segments)} segments complete in {total:.1f}s (model load: {load_time:.1f}s)", flush=True)
        return 0

    # Single text mode (original behavior)
    wavs, sample_rate = _generate_one(model, args, args.text, ref_audio_val, ref_text_val, xvec_val)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if len(wavs) == 1:
        sf.write(str(output), wavs[0], sample_rate)
        print(output)
        return 0

    for i, wav in enumerate(wavs, start=1):
        numbered = output.with_name(f"{output.stem}_{i}{output.suffix}")
        sf.write(str(numbered), wav, sample_rate)
        print(numbered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
