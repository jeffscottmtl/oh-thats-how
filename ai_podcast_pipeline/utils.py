from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo

from .constants import TIMEZONE

logger = logging.getLogger(__name__)

# Query parameters that are tracking-only and safe to strip for deduplication.
_TRACKING_PARAMS = frozenset(
    [
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "utm_id", "utm_reader", "utm_name",
        "ref", "referrer", "ref_source",
        "source", "src",
        "campaign",
        "fbclid", "gclid", "msclkid", "twclid", "dclid",
        "_hsenc", "_hsmi",
        "mc_cid", "mc_eid",
        "WT.mc_id",
    ]
)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with a clean timestamped format."""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"
    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, force=True)


def now_toronto() -> datetime:
    return datetime.now(ZoneInfo(TIMEZONE))


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    # Try ISO 8601 first (most feeds).
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    # Fall back to RFC 2822 (older RSS).
    try:
        dt = parsedate_to_datetime(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def canonical_domain(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def canonical_url(url: str) -> str:
    """Normalize a URL for consistent storage and deduplication.

    Normalizes scheme and host (strips www.), removes known tracking-only
    query parameters, and preserves all other query parameters so that
    functional URLs (e.g. Google News redirects) remain intact.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or "/"

    # Strip tracking-only params while preserving functional ones.
    if parsed.query:
        qs = parse_qs(parsed.query, keep_blank_values=True)
        cleaned = {k: v for k, v in qs.items() if k.lower() not in _TRACKING_PARAMS}
        query = urlencode(cleaned, doseq=True) if cleaned else ""
    else:
        query = ""

    normalized = urlunparse((parsed.scheme.lower(), host, path, "", query, ""))
    return normalized


def count_words(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_indices(raw: str, max_index: int) -> list[int]:
    """Parse a comma-separated list of 1-based indices, e.g. '1,3,5'."""
    indices: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            idx = int(part)
        except ValueError:
            raise ValueError(f"'{part}' is not a valid integer index")
        if idx < 1 or idx > max_index:
            raise ValueError(f"Index {idx} out of range 1..{max_index}")
        if idx not in indices:
            indices.append(idx)
    if not indices:
        raise ValueError("No indices provided")
    return indices


def load_optional_env_file(path: Path) -> None:
    """Load key=value pairs from a .env file into os.environ (if not already set).

    Handles quoted values, inline comments, and blank lines. Does not support
    multi-line values or shell variable expansion.
    """
    if not path.exists():
        return
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            logger.debug("Skipping malformed env line %d: no '=' found", lineno)
            continue
        k, _, v = stripped.partition("=")
        k = k.strip()
        if not k:
            continue
        # Strip inline comments and surrounding quotes from value.
        v = v.strip()
        if " #" in v:
            v = v[: v.index(" #")].strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in {'"', "'"}:
            v = v[1:-1]
        if k not in os.environ:
            os.environ[k] = v
