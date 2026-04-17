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
    parser = argparse.ArgumentParser(description="Generate speech with Qwen3-TTS CustomVoice model")
    parser.add_argument("--env-file", default=".env.qwen3-tts", help="Optional env file to load defaults from")
    parser.add_argument("--text", required=True, help="Text to synthesize")
    parser.add_argument("--output", default="qwen3_tts_output.wav", help="Output WAV path")
    parser.add_argument(
        "--model",
        default=os.getenv("QWEN3_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"),
        help="Model ID or local model path",
    )
    parser.add_argument(
        "--language",
        default=os.getenv("QWEN3_TTS_LANGUAGE", "English"),
        help="Language label supported by the model",
    )
    parser.add_argument(
        "--speaker",
        default=os.getenv("QWEN3_TTS_SPEAKER", "Ryan"),
        help="Speaker supported by the selected custom-voice model",
    )
    parser.add_argument(
        "--instruct",
        default=os.getenv("QWEN3_TTS_INSTRUCT", ""),
        help="Optional style instruction, e.g. 'confident and calm'",
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
    parser.add_argument("--max-new-tokens", type=int, default=2048, help="Generation max_new_tokens")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    _load_env_file(Path(args.env_file))

    model = Qwen3TTSModel.from_pretrained(
        args.model,
        device_map=args.device,
        dtype=_parse_dtype(args.dtype),
    )

    wavs, sample_rate = model.generate_custom_voice(
        text=args.text,
        language=args.language,
        speaker=args.speaker,
        instruct=args.instruct if args.instruct else None,
        max_new_tokens=args.max_new_tokens,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output), wavs[0], sample_rate)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
