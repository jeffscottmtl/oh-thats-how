from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import requests

from .security import redact

logger = logging.getLogger(__name__)

# Retry settings for transient API failures.
_MAX_RETRIES = 2
_RETRY_BACKOFF_BASE = 2.0  # seconds; doubled on each retry

# Reasoning/thinking models reject `temperature` and `response_format`.
# o-series (o1/o3/o4) and gpt-5.x and above use reasoning_effort instead.
# GPT-4.x models (including gpt-4.1-mini, gpt-4o) are NOT reasoning models.
_REASONING_MODEL_RE = re.compile(
    r"^(o1|o3|o4)"              # OpenAI o-series
    r"|^gpt-[5-9]\.(?!.*mini)",  # gpt-5.x+ but NOT mini variants
    re.IGNORECASE,
)
_REASONING_TIMEOUT = 300  # seconds — thinking models can be slow


def _is_reasoning_model(model: str) -> bool:
    return bool(_REASONING_MODEL_RE.match(model))


class OpenAIError(RuntimeError):
    pass


def chat_completion(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    project_id: str | None = None,
    organization: str | None = None,
    temperature: float = 0.3,
    reasoning_effort: str | None = None,
    timeout: int = 60,
) -> str:
    """Call the OpenAI Chat Completions API with automatic retry on transient errors.

    For reasoning models (gpt-5.x, o-series): temperature and response_format are
    omitted automatically. Pass reasoning_effort ("low"/"medium"/"high"/"xhigh") to
    control thinking depth; defaults to "high" for reasoning models.

    Returns the raw content string from the first choice.
    Raises OpenAIError on non-retryable or exhausted-retry failures.
    """
    reasoning = _is_reasoning_model(model)
    if reasoning:
        logger.info("Model %s detected as reasoning model — omitting temperature/response_format.", model)
        timeout = max(timeout, _REASONING_TIMEOUT)
        # GPT-5 and o-series models use "developer" role instead of "system".
        messages = [
            {**m, "role": "developer"} if m.get("role") == "system" else m
            for m in messages
        ]

    url = "https://api.openai.com/v1/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if not reasoning:
        payload["temperature"] = temperature
        payload["response_format"] = {"type": "json_object"}
    else:
        effort = reasoning_effort or "medium"
        payload["reasoning_effort"] = effort
        logger.debug("Using reasoning_effort=%s for model %s.", effort, model)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if project_id:
        headers["OpenAI-Project"] = project_id
    if organization:
        headers["OpenAI-Organization"] = organization

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        if attempt > 0:
            wait = _RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
            logger.warning("OpenAI API retry %d/%d in %.0fs…", attempt, _MAX_RETRIES, wait)
            time.sleep(wait)

        try:
            t0 = time.monotonic()
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            elapsed = time.monotonic() - t0
        except requests.RequestException as exc:
            logger.warning("OpenAI request error (attempt %d): %s", attempt + 1, exc)
            last_exc = exc
            # Connection/timeout errors are retryable.
            continue

        logger.debug(
            "OpenAI %s response: HTTP %d in %.2fs", model, resp.status_code, elapsed
        )

        # Rate-limited or server errors are retryable; auth/validation errors are not.
        if resp.status_code in {429, 500, 502, 503, 504}:
            body = redact(resp.text[:200])
            logger.warning(
                "OpenAI retryable HTTP %d (attempt %d): %s", resp.status_code, attempt + 1, body
            )
            last_exc = OpenAIError(f"OpenAI API HTTP {resp.status_code}: {body}")
            continue

        try:
            resp.raise_for_status()
        except requests.RequestException as exc:
            raw_body = getattr(exc.response, "text", str(exc))[:600]
            status = getattr(exc.response, "status_code", "unknown")
            body = redact(raw_body)
            logger.warning(
                "OpenAI API HTTP %s error (attempt %d): %s",
                status, attempt + 1, body,
            )
            raise OpenAIError(f"OpenAI API HTTP {status}: {body}") from exc

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise OpenAIError("OpenAI API returned no choices")
        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise OpenAIError("OpenAI API returned empty content")
        return content

    # All retries exhausted.
    raise OpenAIError(
        f"OpenAI API failed after {_MAX_RETRIES + 1} attempts"
    ) from last_exc


def parse_json_response(content: str) -> dict[str, Any]:
    """Extract a JSON object from a model response.

    Handles plain JSON, JSON wrapped in markdown code fences (```json ... ```),
    and JSON with leading/trailing whitespace.
    """
    raw = content.strip()

    # Strip markdown code fences: ```json ... ``` or ``` ... ```
    if raw.startswith("```"):
        # Find the end of the opening fence line.
        first_newline = raw.find("\n")
        if first_newline != -1:
            raw = raw[first_newline + 1:]
        else:
            raw = raw[3:]  # degenerate: no newline after fence
        # Strip the closing fence.
        if raw.endswith("```"):
            raw = raw[: -3]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OpenAIError(
            f"Model response was not valid JSON: {content[:240]}"
        ) from exc
