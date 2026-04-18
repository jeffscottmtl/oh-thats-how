from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .constants import (
    DEFAULT_STORY_COUNT,
    MAX_STORY_COUNT,
    MIN_STORY_COUNT,
    SOURCE_ALLOWLIST_BASELINE,
)
from .utils import load_optional_env_file


@dataclass
class Settings:
    openai_api_key: str
    openai_project_id: str | None
    openai_organization: str | None
    qwen_profile_manifest: str
    qwen_tts_model: str
    qwen_ref_clip_id: str | None
    qwen_tts_language: str
    qwen_tts_instruct: str | None
    qwen_tts_temperature: float
    qwen_tts_top_p: float
    qwen_tts_top_k: int
    qwen_tts_max_new_tokens: int
    qwen_tts_speed: float
    qwen_tts_timeout_seconds: int
    openai_model: str
    openai_script_model: str
    story_count: int
    user_approved_domains: set[str]
    skip_verification: bool = False


class ConfigError(RuntimeError):
    pass


def _parse_float_env(name: str, default: float, min_value: float, max_value: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a float.") from exc
    if value < min_value or value > max_value:
        raise ConfigError(f"{name} must be between {min_value} and {max_value}.")
    return value


def _parse_int_env(name: str, default: int, min_value: int, max_value: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer.") from exc
    if value < min_value or value > max_value:
        raise ConfigError(f"{name} must be between {min_value} and {max_value}.")
    return value


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be a boolean (true/false).")


def load_settings(
    story_count: int,
    allow_domains: list[str] | None,
    skip_audio: bool,
    skip_verification: bool = False,
    env_file: str | None = None,
    qwen_profile_manifest_override: str | None = None,
    qwen_tts_model_override: str | None = None,
    qwen_ref_clip_id_override: str | None = None,
) -> Settings:
    if env_file:
        load_optional_env_file(Path(env_file))

    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    openai_project_id = os.getenv("OPENAI_PROJECT_ID", "").strip() or None
    openai_organization = os.getenv("OPENAI_ORGANIZATION", "").strip() or None
    qwen_profile_manifest = (
        qwen_profile_manifest_override
        or os.getenv("QWEN_PROFILE_MANIFEST", "voice_profiles/jeff_v1/profile_manifest.csv")
    ).strip()
    qwen_tts_model = (
        qwen_tts_model_override or os.getenv("QWEN_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-Base")
    ).strip()
    qwen_ref_clip_id = (qwen_ref_clip_id_override or os.getenv("QWEN_REF_CLIP_ID", "")).strip() or None
    qwen_tts_language = os.getenv("QWEN_TTS_LANGUAGE", "English").strip() or "English"
    qwen_tts_instruct_raw = os.getenv(
        "QWEN_TTS_INSTRUCT",
        "You are a friendly podcast host speaking naturally to colleagues. "
        "Speak at a relaxed, unhurried pace with clear diction. "
        "Pause noticeably after periods and between sentences — don't rush into the next thought. "
        "For questions, use a gentle natural rise in pitch at the end, like asking a friend a genuine question — not exaggerated or theatrical. "
        "Pause briefly before and after em dashes. "
        "Slow down slightly for important points and key takeaways. "
        "Keep the tone warm and conversational, like explaining something interesting to a smart colleague over coffee.",
    ).strip()
    qwen_tts_instruct = qwen_tts_instruct_raw or None
    qwen_tts_temperature = _parse_float_env("QWEN_TTS_TEMPERATURE", default=0.72, min_value=0.1, max_value=1.3)
    qwen_tts_top_p = _parse_float_env("QWEN_TTS_TOP_P", default=0.92, min_value=0.1, max_value=1.0)
    qwen_tts_top_k = _parse_int_env("QWEN_TTS_TOP_K", default=45, min_value=1, max_value=200)
    qwen_tts_max_new_tokens = _parse_int_env("QWEN_TTS_MAX_NEW_TOKENS", default=4096, min_value=512, max_value=16384)
    qwen_tts_speed = _parse_float_env("QWEN_TTS_SPEED", default=0.93, min_value=0.7, max_value=1.3)
    qwen_tts_timeout_seconds = _parse_int_env("QWEN_TTS_TIMEOUT_SECONDS", default=1800, min_value=60, max_value=7200)
    openai_model = os.getenv("OPENAI_MODEL", "gpt-5.3-chat-latest").strip() or "gpt-5.3-chat-latest"
    openai_script_model = os.getenv("OPENAI_SCRIPT_MODEL", "gpt-5.4").strip() or "gpt-5.4"

    missing = []
    if not openai_api_key:
        missing.append("OPENAI_API_KEY")
    if not skip_audio:
        if not qwen_profile_manifest:
            missing.append("QWEN_PROFILE_MANIFEST")
        if not qwen_tts_model:
            missing.append("QWEN_TTS_MODEL")

    if missing:
        raise ConfigError("Missing required environment variables: " + ", ".join(missing))

    if not skip_audio:
        profile_path = Path(qwen_profile_manifest).expanduser()
        if not profile_path.exists():
            raise ConfigError(f"Qwen profile manifest does not exist: {profile_path}")
        qwen_profile_manifest = str(profile_path.resolve())

    if story_count < MIN_STORY_COUNT or story_count > MAX_STORY_COUNT:
        raise ConfigError(f"story_count must be within {MIN_STORY_COUNT}-{MAX_STORY_COUNT}")

    approved_domains: set[str] = set(SOURCE_ALLOWLIST_BASELINE)
    for d in allow_domains or []:
        cleaned = d.strip().lower()
        if cleaned.startswith("www."):
            cleaned = cleaned[4:]
        if cleaned:
            approved_domains.add(cleaned)

    return Settings(
        openai_api_key=openai_api_key,
        openai_project_id=openai_project_id,
        openai_organization=openai_organization,
        qwen_profile_manifest=qwen_profile_manifest,
        qwen_tts_model=qwen_tts_model,
        qwen_ref_clip_id=qwen_ref_clip_id,
        qwen_tts_language=qwen_tts_language,
        qwen_tts_instruct=qwen_tts_instruct,
        qwen_tts_temperature=qwen_tts_temperature,
        qwen_tts_top_p=qwen_tts_top_p,
        qwen_tts_top_k=qwen_tts_top_k,
        qwen_tts_max_new_tokens=qwen_tts_max_new_tokens,
        qwen_tts_speed=qwen_tts_speed,
        qwen_tts_timeout_seconds=qwen_tts_timeout_seconds,
        openai_model=openai_model,
        openai_script_model=openai_script_model,
        story_count=story_count,
        user_approved_domains=approved_domains,
        skip_verification=skip_verification,
    )
