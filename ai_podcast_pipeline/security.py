from __future__ import annotations

import os
import re
from pathlib import Path

SECRET_REGEXES = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?:api[_-]?key|token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
]


def redact(text: str) -> str:
    """Replace known secret values and secret-looking patterns with [REDACTED]."""
    output = text
    for key in (
        os.getenv("OPENAI_API_KEY", ""),
        os.getenv("ELEVENLABS_API_KEY", ""),
        os.getenv("ELEVENLABS_VOICE_ID", ""),
    ):
        if key:
            output = output.replace(key, "[REDACTED]")
    for regex in SECRET_REGEXES:
        output = regex.sub("[REDACTED]", output)
    return output


def scan_text_for_secrets(text: str) -> bool:
    """Return True if text appears to contain a secret value."""
    if any(
        k and k in text
        for k in (
            os.getenv("OPENAI_API_KEY", ""),
            os.getenv("ELEVENLABS_API_KEY", ""),
            os.getenv("ELEVENLABS_VOICE_ID", ""),
        )
    ):
        return True
    return any(regex.search(text) for regex in SECRET_REGEXES)


def scan_artifacts_for_secrets(paths: list[Path]) -> list[str]:
    """Return the names of any artifact files that appear to contain secrets."""
    flagged: list[str] = []
    for path in paths:
        if not path.exists() or path.suffix.lower() in {".png", ".mp3"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if scan_text_for_secrets(text):
            flagged.append(path.name)
    return flagged
