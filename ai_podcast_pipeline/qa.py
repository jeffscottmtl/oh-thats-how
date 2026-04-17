from __future__ import annotations

import logging
import re
from pathlib import Path

try:
    from jsonschema import Draft202012Validator  # type: ignore
except Exception:  # pragma: no cover - optional dependency fallback
    Draft202012Validator = None

from .constants import (
    BANNED_BOILERPLATE,
    BANNED_TEMPLATE_MARKERS,
    ENDING_TOKEN,
    INTRO_TEXT,
    OUTRO_TEXT,
    TARGET_MAX_WORDS,
    TARGET_MIN_WORDS,
)
from .models import QaResult
from .security import scan_artifacts_for_secrets
from .utils import count_words, read_json, sha256_file

logger = logging.getLogger(__name__)


def _matches_type(value, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (isinstance(value, (int, float))) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _validate_node(value, schema: dict, path: str, errors: list[str]) -> None:
    expected_type = schema.get("type")
    if expected_type is not None:
        allowed = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_matches_type(value, t) for t in allowed):
            errors.append(f"{path} expected type {expected_type}, got {type(value).__name__}")
            return

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path} expected const {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path} value not in enum {schema['enum']!r}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path} string shorter than minLength {schema['minLength']}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path} below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path} above maximum {schema['maximum']}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path} has fewer than minItems {schema['minItems']}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path} has more than maxItems {schema['maxItems']}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                _validate_node(item, item_schema, f"{path}[{idx}]", errors)

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key} missing required property")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value.keys():
                if key not in properties:
                    errors.append(f"{path}.{key} is not allowed")
        for key, sub_schema in properties.items():
            if key in value and isinstance(sub_schema, dict):
                _validate_node(value[key], sub_schema, f"{path}.{key}", errors)


def validate_schema(instance_path: Path, schema_path: Path) -> tuple[bool, list[str]]:
    instance = read_json(instance_path)
    schema = read_json(schema_path)
    if Draft202012Validator is not None:
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(instance), key=lambda e: e.path)
        if not errors:
            return True, []
        return (
            False,
            [f"{instance_path.name}: {'.'.join(str(p) for p in err.path)} {err.message}" for err in errors],
        )

    fallback_errors: list[str] = []
    _validate_node(instance, schema, instance_path.name, fallback_errors)
    return (not fallback_errors, fallback_errors)


def _contains_banned(text: str) -> bool:
    lowered = text.lower()
    banned = BANNED_BOILERPLATE + BANNED_TEMPLATE_MARKERS
    return any(token.lower() in lowered for token in banned)


def _file_name_ok(script_path: Path, episode_name: str) -> bool:
    return script_path.name.startswith(episode_name) and script_path.name.endswith(" - Script.md")


def _check_script_prose(script_text: str) -> list[str]:
    """Catch common writing quality issues in the assembled script.

    Returns a list of human-readable warning strings (empty = all clear).
    """
    issues: list[str] = []

    # 1. Raw domain names — GPT should use publication names, not URLs.
    domain_hits = re.findall(
        r'\b[\w\-]+\.(com|ca|org|net|io|co\.uk|gov|edu)\b',
        script_text,
        flags=re.IGNORECASE,
    )
    if domain_hits:
        unique = sorted({h[0] and m for m, h in zip(domain_hits, re.finditer(
            r'\b([\w\-]+\.(?:com|ca|org|net|io|co\.uk|gov|edu))\b',
            script_text, flags=re.IGNORECASE
        ))})
        issues.append(
            f"Script contains raw domain name(s) — use publication names instead: "
            + ", ".join(sorted(set(
                m.group(0) for m in re.finditer(
                    r'\b[\w\-]+\.(?:com|ca|org|net|io|co\.uk|gov|edu)\b',
                    script_text, flags=re.IGNORECASE
                )
            )))
        )

    # 2. Repeated phrase within a short window — catches "this week…this week",
    #    "for communications…for communications", etc.
    words = script_text.lower().split()
    window = 30  # words to look ahead
    phrase_len = 4  # consecutive words to treat as a phrase
    seen_phrases: dict[tuple[str, ...], int] = {}
    for i, _ in enumerate(words):
        phrase = tuple(words[i:i + phrase_len])
        if len(phrase) < phrase_len:
            break
        # Skip phrases that are all stopwords
        stopwords = {"the", "a", "an", "and", "or", "of", "in", "to", "for",
                     "is", "it", "that", "this", "on", "at", "by", "with"}
        if all(w in stopwords for w in phrase):
            continue
        if phrase in seen_phrases and (i - seen_phrases[phrase]) <= window:
            issues.append(
                f"Repeated phrase detected within {window} words: "
                f'"{" ".join(phrase)}"'
            )
            # Only report each unique repeated phrase once
            del seen_phrases[phrase]
        else:
            seen_phrases[phrase] = i

    # 3. "[Removed]" placeholder — NewsAPI returns this for deleted articles.
    if "[Removed]" in script_text or "[removed]" in script_text:
        issues.append('Script contains "[Removed]" placeholder — a NewsAPI article with no content was used.')

    # 4. Suspiciously short script body (excluding intro/outro).
    body = script_text.replace(INTRO_TEXT, "").replace(OUTRO_TEXT, "")
    if len(body.split()) < 80:
        issues.append("Script body appears very short — the fallback template may have been used.")

    return issues


def run_qa(
    episode_name: str,
    script_md_path: Path,
    script_json_path: Path,
    sources_json_path: Path,
    manifest_json_path: Path,
    cover_path: Path,
    schema_dir: Path,
    selected_indices: list[int],
    selected_verification_passed: bool,
    explicit_fail_state_recorded: bool,
    cover_determinism_probe_hash: str,
) -> QaResult:
    logger.info("Running post-run QA checks…")
    failures: list[str] = []
    checks: dict[str, bool] = {}

    script_text = script_md_path.read_text(encoding="utf-8")
    script_json = read_json(script_json_path)

    checks["intro_exact"] = script_text.startswith(INTRO_TEXT)
    if not checks["intro_exact"]:
        # Downgraded to a warning — the pipeline auto-corrects the intro before audio
        # generation. A mismatch here would mean the auto-correction itself failed.
        logger.warning("QA: intro text does not match canonical INTRO_TEXT (auto-correction may not have applied)")

    # Check that the food for thought segment is present exactly once via its spoken opener.
    fot_count = script_text.lower().count("here's some food for thought")
    checks["ending_token_exact_once"] = fot_count == 1
    if not checks["ending_token_exact_once"]:
        failures.append(
            f"Food for Thought opener appears {fot_count} time(s) — expected exactly once"
        )

    indices_in_sources = read_json(sources_json_path).get("selected_indices", [])
    checks["selected_order"] = indices_in_sources == selected_indices
    if not checks["selected_order"]:
        failures.append("Selected stories do not match requested picks and order")

    checks["verification"] = selected_verification_passed
    if not checks["verification"]:
        failures.append("One or more selected stories failed verification")

    wc = count_words(script_text)
    checks["word_count_gate"] = (TARGET_MIN_WORDS <= wc <= TARGET_MAX_WORDS) or explicit_fail_state_recorded
    if not checks["word_count_gate"]:
        failures.append(f"Script word count outside {TARGET_MIN_WORDS}-{TARGET_MAX_WORDS} without fail state")

    schema_checks = []
    for filename, schema in [
        (script_json_path, schema_dir / "script.schema.json"),
        (sources_json_path, schema_dir / "sources.schema.json"),
        (manifest_json_path, schema_dir / "manifest.schema.json"),
    ]:
        ok, errs = validate_schema(filename, schema)
        schema_checks.append(ok)
        failures.extend(errs)
    checks["schemas"] = all(schema_checks)

    checks["no_banned_phrases"] = not _contains_banned(script_text)
    if not checks["no_banned_phrases"]:
        failures.append("Script contains banned boilerplate/template phrases")

    prose_issues = _check_script_prose(script_text)
    checks["prose_quality"] = not prose_issues
    for issue in prose_issues:
        failures.append(f"Prose quality: {issue}")

    flagged = scan_artifacts_for_secrets(
        [script_md_path, script_json_path, sources_json_path, manifest_json_path]
    )
    checks["no_secrets"] = not flagged
    if flagged:
        failures.append("Secret-like tokens detected in artifacts: " + ", ".join(flagged))

    checks["filename_rule"] = _file_name_ok(script_md_path, episode_name)
    if not checks["filename_rule"]:
        failures.append("File naming does not match episode naming rules")

    checks["cover_deterministic"] = sha256_file(cover_path) == cover_determinism_probe_hash
    if not checks["cover_deterministic"]:
        failures.append("Cover output is not deterministic for identical inputs")

    result = QaResult(passed=all(checks.values()), checks=checks, failures=failures)
    if result.passed:
        logger.info("QA passed — all %d checks OK.", len(checks))
    else:
        logger.warning("QA FAILED — %d failures: %s", len(failures), failures)
    return result
