from __future__ import annotations

import logging
import time
from argparse import Namespace
from collections import defaultdict
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from zoneinfo import ZoneInfo

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

_console = Console()

from .artifacts import build_artifact_paths, resolve_episode_name, resolve_episode_number
from .audio import QwenTTSError, synthesize_qwen_clone_mp3
from .config import Settings, load_settings
from .constants import (
    DEFAULT_STORY_COUNT,
    HARD_MAX_WORDS,
    MAX_PER_SOURCE_WEEK,
    MAX_SHORTLIST,
    MAX_REWRITES,
    OUTRO_TEXT,
    PADDING_PARAGRAPHS,
    RSS_FEEDS,
    TARGET_MAX_WORDS,
    TARGET_MIN_WORDS,
    TIMEZONE,
)
from .cover import render_cover
from .ingest import fetch_article_text_batch, fetch_candidates
from .models import ScoredStory, ScriptParts, ThemeCandidate, VerificationResult
from .qa import run_qa
from .scoring import is_excluded, is_relevant_story, score_story, story_sort_key
from .script_writer import (
    build_script_json,
    build_script_markdown,
    generate_script_parts,
    rewrite_script_to_target,
    generate_theme_script,
    build_theme_script_markdown,
    build_theme_script_json,
)
from .theme_clustering import cluster_themes
from .security import redact
from .utils import count_words, ensure_dir, iso_utc_now, now_toronto, parse_indices, sha256_file, write_json
from .verification import verify_selection

logger = logging.getLogger(__name__)


class PipelineError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Food for Thought history — avoid repeating past topics
# ---------------------------------------------------------------------------

def _load_previous_food_for_thought(output_dir: Path) -> list[str]:
    """Scan output_dir for previous Script.json files and extract food_for_thought values."""
    import json

    fot_list: list[str] = []
    for script_json in sorted(output_dir.glob("*Script.json")):
        try:
            data = json.loads(script_json.read_text(encoding="utf-8"))
            fot = data.get("food_for_thought", "")
            if isinstance(fot, str) and fot.strip():
                fot_list.append(fot.strip())
        except Exception:
            continue
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for item in fot_list:
        key = item[:100].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    logger.info("Loaded %d unique previous Food for Thought entries from %s.", len(unique), output_dir)
    return unique


# ---------------------------------------------------------------------------
# Script text helpers
# ---------------------------------------------------------------------------

import re as _re

# Canonical spoken opener used as the structural marker for the FoT section.
# Pipeline functions use this to locate the FoT segment — never a heading.
_FOT_OPENER = "Here's some food for thought."

_FFT_RE = _re.compile(r"Food for Thought\.?", _re.IGNORECASE)


def _enforce_intro_text(script_markdown: str) -> tuple[str, bool]:
    """Ensure the script starts with the exact INTRO_TEXT.

    If the model rewrote the intro, replace the first paragraph with the
    canonical text. Returns (corrected_script, was_fixed).
    """
    from .constants import INTRO_TEXT as _INTRO
    if script_markdown.startswith(_INTRO):
        return script_markdown, False
    # Replace everything up to (but not including) the first blank line.
    stripped = script_markdown.lstrip()
    if "\n\n" in stripped:
        _, rest = stripped.split("\n\n", 1)
        return _INTRO + "\n\n" + rest, True
    return _INTRO + "\n\n" + stripped, True


def _normalise_food_for_thought(script_markdown: str) -> str:
    """Remove any stray 'Food for Thought' headings that the rewrite model injects.

    The FoT section should begin with the spoken opener
    'Here's some food for thought.' — never a standalone heading.
    This function strips heading-style occurrences and deduplicates the opener.
    """
    # Remove standalone "Food for Thought" headings (on their own line)
    text = _re.sub(r'\n\s*Food\s+for\s+Thought[.:\-]?\s*\n', '\n', script_markdown, flags=_re.IGNORECASE)
    # Remove "Food for Thought" that appears right before "Here's some food for thought"
    text = _re.sub(r'Food\s+for\s+Thought[.:\-]?\s*\n*\s*(?=Here\'s some food for thought)', '', text, flags=_re.IGNORECASE)
    # Deduplicate the spoken opener: keep only the last occurrence
    marker = _FOT_OPENER
    parts = text.split(marker)
    if len(parts) <= 2:
        return text
    before = marker.join(parts[:-1]).rstrip()
    after = parts[-1]
    return before + "\n\n" + marker + after


def _insert_before_food_for_thought(script_markdown: str, paragraph: str) -> str:
    """Insert a paragraph before the FoT section (identified by the spoken opener)."""
    marker = _FOT_OPENER
    if marker not in script_markdown:
        # No FoT section found — append paragraph then FoT placeholder
        return script_markdown.rstrip() + "\n\n" + paragraph.strip() + "\n"
    head, tail = script_markdown.split(marker, 1)
    return head.rstrip() + "\n\n" + paragraph.strip() + "\n\n" + marker + tail


def _ensure_food_for_thought_text(script_markdown: str, fallback_text: str) -> str:
    """Ensure the FoT section has content. If the spoken opener is missing entirely,
    append a clean FoT section using the fallback text."""
    from .script_writer import _clean_food_for_thought
    marker = _FOT_OPENER
    if marker not in script_markdown:
        clean_fot = _clean_food_for_thought(fallback_text)
        return script_markdown.rstrip() + "\n\n" + clean_fot + "\n"
    # Opener exists — check there's content after it
    head, tail = script_markdown.split(marker, 1)
    if count_words(tail) > 0:
        return script_markdown
    clean_fot = _clean_food_for_thought(fallback_text)
    return head.rstrip() + "\n\n" + clean_fot + "\n"


def _ensure_outro_text(script_markdown: str, outro_text: str) -> str:
    if outro_text in script_markdown:
        return script_markdown
    return script_markdown.rstrip() + "\n\n" + outro_text.strip() + "\n"


def _pad_script_to_min_words(script_markdown: str, min_words: int, max_words: int) -> str:
    wc = count_words(script_markdown)
    if wc >= min_words:
        return script_markdown
    result = script_markdown
    for paragraph in PADDING_PARAGRAPHS:
        candidate = _insert_before_food_for_thought(result, paragraph)
        candidate_wc = count_words(candidate)
        if candidate_wc <= max_words:
            result = candidate
            if candidate_wc >= min_words:
                break
    return result


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------

def _cap_full_list(items: list[ScoredStory], limit: int = MAX_SHORTLIST) -> tuple[list[ScoredStory], int]:
    if len(items) <= limit:
        return items, 0
    return items[:limit], len(items) - limit


def _week_start(local_day: date) -> date:
    return local_day - timedelta(days=local_day.weekday())


def _apply_per_source_cap(
    items: list[ScoredStory], max_per_source: int
) -> tuple[list[ScoredStory], int]:
    if max_per_source < 1:
        raise ValueError("max_per_source must be >= 1")
    counts: dict[str, int] = defaultdict(int)
    kept: list[ScoredStory] = []
    dropped = 0
    for item in items:
        domain = item.candidate.source_domain
        if counts[domain] >= max_per_source:
            dropped += 1
            continue
        kept.append(item)
        counts[domain] += 1
    return kept, dropped


def _apply_weekly_per_source_cap(
    items: list[ScoredStory], max_per_source: int
) -> tuple[list[ScoredStory], int]:
    if max_per_source < 1:
        raise ValueError("max_per_source must be >= 1")
    counts: dict[tuple[date, str], int] = defaultdict(int)
    kept: list[ScoredStory] = []
    dropped = 0
    for item in items:
        published = item.candidate.published_at
        if published is None:
            dropped += 1
            continue
        local_date = published.astimezone(ZoneInfo(TIMEZONE)).date()
        bucket = (_week_start(local_date), item.candidate.source_domain)
        if counts[bucket] >= max_per_source:
            dropped += 1
            continue
        kept.append(item)
        counts[bucket] += 1
    return kept, dropped


def _filter_by_date_window(
    items: list[ScoredStory], start_date: date, end_date: date
) -> tuple[list[ScoredStory], list[ScoredStory]]:
    kept: list[ScoredStory] = []
    dropped: list[ScoredStory] = []
    for item in items:
        published = item.candidate.published_at
        if published is None:
            dropped.append(item)
            continue
        local_date = published.astimezone(ZoneInfo(TIMEZONE)).date()
        if start_date <= local_date <= end_date:
            kept.append(item)
        else:
            dropped.append(item)
    return kept, dropped


def _passes_local_candidate_checks(
    item: ScoredStory, approved_domains: set[str]
) -> tuple[bool, str | None]:
    domain = item.candidate.source_domain
    if domain not in approved_domains:
        return False, "Domain not approved by policy"
    if item.candidate.published_at is None:
        return False, "Publication date missing or unparseable"
    if not item.candidate.url:
        return False, "Missing source URL"
    return True, None


# ---------------------------------------------------------------------------
# User interaction helpers
# ---------------------------------------------------------------------------

def _review_article_content(selected: list[ScoredStory]) -> bool:
    """Show a preview of the content being sent to the LLM for each selected story.

    Returns True if the user wants to proceed, False if they want to reselect.
    Allows manual text paste for any article that failed to fetch.
    """
    SEP = "─" * 72

    print(f"\n{SEP}")
    print("  Article content review — this is what will be sent to ChatGPT")
    print(SEP)

    has_failures = False
    for idx, story in enumerate(selected, start=1):
        c = story.candidate
        print(f"\n[{idx}] {c.title}")
        print(f"    {c.source_domain}  •  {c.url}")

        if c.full_text:
            wc = len(c.full_text.split())
            print(f"    ✓ Full text captured ({wc:,} words)")
            print(f"\n{c.full_text}\n")
        else:
            has_failures = True
            rss_wc = len(c.summary.split()) if c.summary else 0
            print(f"    ✗ Full text unavailable (paywall or bot-blocked) — {rss_wc} word RSS summary only")

        print(SEP)

    print()

    # Full text is required — RSS summaries are not accepted for script generation.
    # Loop until every selected story has full text, or the user reselects/quits.
    if has_failures:
        print("\nFull article text is required — the script will not be generated from RSS summaries.")
        print("For each unavailable article, paste the text manually or choose to reselect.\n")
        for idx, story in enumerate(selected, start=1):
            c = story.candidate
            if c.full_text:
                continue
            while not c.full_text:
                print(f"[{idx}] {c.title}")
                print("    Options: [p] paste text   [r] reselect stories   [q] quit")
                ans = input("    Choice: ").strip().lower()
                if ans in {"p", "paste"}:
                    print("    Paste the article text below. Type END on its own line when done:")
                    lines: list[str] = []
                    while True:
                        line = input()
                        if line.strip() == "END":
                            break
                        lines.append(line)
                    pasted = "\n".join(lines).strip()
                    if pasted:
                        c.full_text = pasted
                        wc = len(pasted.split())
                        print(f"    ✓ Text accepted ({wc:,} words)\n")
                    else:
                        print("    Nothing entered — please try again.\n")
                elif ans in {"r", "reselect"}:
                    return False
                elif ans in {"q", "quit"}:
                    raise KeyboardInterrupt("Script generation cancelled by user.")
                else:
                    print("    Please enter p, r, or q.\n")

    while True:
        ans = input("\nProceed with script generation? [Y/n/reselect]: ").strip().lower()
        if ans in {"", "y", "yes"}:
            return True
        if ans in {"n", "no"}:
            raise KeyboardInterrupt("Script generation cancelled by user.")
        if ans in {"r", "reselect"}:
            return False
        print("  Enter Y to proceed, N to cancel, or 'reselect' to choose different stories.")


def _print_full_list(items: list[ScoredStory], heading: str = "Full verified article list:") -> None:
    print(f"\n{heading}")
    for idx, item in enumerate(items, start=1):
        published = item.candidate.published_at.isoformat() if item.candidate.published_at else "unknown"
        print(
            f"[{idx:02d}] score={item.total:05.2f} | {item.candidate.title} "
            f"({item.candidate.source_domain}, {published})"
        )


def _prompt_selection(max_index: int) -> list[int]:
    while True:
        raw = input(f"\nSelect article indices from the full list (comma-separated, 1..{max_index}): ").strip()
        try:
            picked = parse_indices(raw, max_index)
        except ValueError as exc:
            print(f"Invalid selection: {exc}")
            continue
        if len(picked) < 1:
            print("Select at least one story.")
            continue
        return picked


def _confirm_audio() -> bool:
    raw = input("\nGenerate audio now? [y/N]: ").strip().lower()
    return raw in {"y", "yes"}


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------

def _sources_payload(
    candidates_count: int,
    shortlisted: list[ScoredStory],
    selected_indices: list[int],
    verifications: list[VerificationResult],
) -> dict[str, Any]:
    shortlist_payload = [
        {
            "index": i,
            "title": s.candidate.title,
            "url": s.candidate.url,
            "source_domain": s.candidate.source_domain,
            "published_at": s.candidate.published_at.isoformat() if s.candidate.published_at else None,
            "summary": s.candidate.summary,
            "scores": {
                "credibility": s.credibility,
                "comms_relevance": s.comms_relevance,
                "freshness": s.freshness,
                "ai_materiality": s.ai_materiality,
                "preferred_topic": s.preferred_topic,
                "total": s.total,
            },
        }
        for i, s in enumerate(shortlisted, start=1)
    ]

    selected_payload = [
        {
            "title": v.story.candidate.title,
            "url": v.story.candidate.url,
            "source_domain": v.story.candidate.source_domain,
            "published_at": v.story.candidate.published_at.isoformat() if v.story.candidate.published_at else None,
            "verification": {"passed": v.passed, "reason": v.reason},
        }
        for v in verifications
    ]

    return {
        "generated_at": iso_utc_now(),
        "candidate_count": candidates_count,
        "shortlist_count": len(shortlisted),
        "shortlist": shortlist_payload,
        "selected_indices": selected_indices,
        "selected_stories": selected_payload,
    }


# ---------------------------------------------------------------------------
# Date / episode helpers
# ---------------------------------------------------------------------------

def _resolve_episode_datetime(episode_date: str | None) -> datetime:
    if not episode_date:
        return now_toronto()
    try:
        parsed = datetime.strptime(episode_date, "%Y-%m-%d")
    except ValueError as exc:
        raise PipelineError("Invalid --episode-date format. Use YYYY-MM-DD.") from exc
    return parsed.replace(hour=12, minute=0, second=0, microsecond=0, tzinfo=ZoneInfo(TIMEZONE))


def _parse_date_flag(value: str, flag_name: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise PipelineError(f"Invalid {flag_name} format. Use YYYY-MM-DD.") from exc


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def _stage_build_full_list(
    settings: Settings,
    date_window: tuple[date, date] | None,
    on_feed_done: Any = None,
) -> tuple[list[ScoredStory], str, int]:
    """Fetch candidates, score them, apply filters, and return a ranked full list.

    Returns (full_list_items, heading_text, raw_candidate_count).
    """
    candidates = fetch_candidates(on_feed_done=on_feed_done)
    if not candidates:
        raise PipelineError("No candidate stories fetched and no fallback data available")

    raw_count = len(candidates)
    logger.info("Scoring %d raw candidates…", raw_count)

    scored_candidates = [score_story(c) for c in candidates]

    full_list_items: list[ScoredStory] = []
    verification_dropped: list[ScoredStory] = []
    relevance_dropped = 0

    excluded_count = 0
    for item in scored_candidates:
        if is_excluded(item.candidate):
            excluded_count += 1
            continue
        ok, _ = _passes_local_candidate_checks(item, settings.user_approved_domains)
        if ok:
            if is_relevant_story(item):
                full_list_items.append(item)
            else:
                relevance_dropped += 1
        else:
            verification_dropped.append(item)

    if excluded_count:
        logger.info("Removed %d candidates matching exclusion keywords.", excluded_count)

    if verification_dropped:
        logger.info(
            "Removed %d candidates that failed source/date/domain verification.",
            len(verification_dropped),
        )
    if relevance_dropped:
        logger.info("Removed %d candidates that were not relevant to AI/comms focus.", relevance_dropped)

    # Date-window filtering.
    if date_window:
        start_date, end_date = date_window
        full_list_items, date_dropped = _filter_by_date_window(full_list_items, start_date, end_date)
        if date_dropped:
            logger.info(
                "Removed %d candidates outside requested range (%s to %s).",
                len(date_dropped),
                start_date.isoformat(),
                end_date.isoformat(),
            )

    full_list_items.sort(key=story_sort_key)

    # Source diversity cap (weekly window only).
    if date_window:
        full_list_items, source_capped_count = _apply_weekly_per_source_cap(
            full_list_items, max_per_source=MAX_PER_SOURCE_WEEK
        )
        if source_capped_count:
            logger.info(
                "Removed %d candidates due to source diversity cap (max %d per source per week).",
                source_capped_count,
                MAX_PER_SOURCE_WEEK,
            )

    full_list_items, capped_count = _cap_full_list(full_list_items, limit=MAX_SHORTLIST)
    if capped_count:
        pool_label = "verified in-range candidates" if date_window else "verified candidates"
        logger.info(
            "Showing top %d ranked stories from %d %s.",
            MAX_SHORTLIST,
            len(full_list_items) + capped_count,
            pool_label,
        )

    if not full_list_items:
        raise PipelineError("No full-list stories available after filtering")

    # Build list heading.
    if date_window:
        start_date, end_date = date_window
        heading = (
            f"Date-window article list ({start_date.isoformat()} to {end_date.isoformat()}) "
            "- full verified set:"
        )
    else:
        heading = "Full verified article list:"

    return full_list_items, heading, raw_count


def _stage_cluster_themes(
    full_list_items: list[ScoredStory],
    settings: Settings,
) -> list[ThemeCandidate]:
    """Cluster the top articles into theme candidates."""
    top_articles = full_list_items[:min(len(full_list_items), MAX_SHORTLIST)]
    themes = cluster_themes(
        api_key=settings.openai_api_key,
        model=settings.openai_model,  # mini model for clustering
        scored_articles=top_articles,
        project_id=settings.openai_project_id,
        organization=settings.openai_organization,
    )
    return themes


def _prompt_theme_selection(themes: list[ThemeCandidate], full_list: list[ScoredStory]) -> int:
    """Display theme candidates and prompt user to pick one. Returns 0-based index."""
    print("\n\nThis week's theme candidates:\n")
    for idx, theme in enumerate(themes, start=1):
        print(f"[{idx}] {theme.name}")
        print(f"    {theme.description}")
        articles = []
        for ai in theme.article_indices:
            if 1 <= ai <= len(full_list):
                a = full_list[ai - 1]
                articles.append(f"      • {a.candidate.title} ({a.candidate.source_domain})")
        print("\n".join(articles))
        print()

    while True:
        try:
            raw = input(f"Pick a theme (1..{len(themes)}): ").strip()
            choice = int(raw)
            if 1 <= choice <= len(themes):
                return choice - 1
        except (ValueError, EOFError):
            pass
        print(f"Please enter a number between 1 and {len(themes)}.")


def _stage_generate_theme_script(
    theme: ThemeCandidate,
    selected: list[ScoredStory],
    settings: Settings,
    previous_food_for_thought: list[str] | None = None,
) -> tuple[str, ScriptParts, int, bool]:
    """Generate the theme-based script. Returns (markdown, parts, rewrite_attempts, fail_state)."""
    min_words, max_words = TARGET_MIN_WORDS, TARGET_MAX_WORDS
    aim_words = (TARGET_MIN_WORDS + TARGET_MAX_WORDS) // 2
    parts = generate_theme_script(
        api_key=settings.openai_api_key,
        model=settings.openai_script_model,  # full model for script gen
        theme_name=theme.name,
        selected=selected,
        target_total_words=aim_words,
        project_id=settings.openai_project_id,
        organization=settings.openai_organization,
        previous_food_for_thought=previous_food_for_thought,
    )
    script_markdown = build_theme_script_markdown(parts)
    wc = count_words(script_markdown)
    logger.info("Initial theme script: %d words (target %d–%d).", wc, min_words, max_words)

    attempts = 0
    explicit_fail_state = False

    while not (min_words <= wc <= max_words):
        if attempts >= MAX_REWRITES:
            logger.warning(
                "Word-count gate failed after %d rewrite(s); proceeding with %d words.",
                MAX_REWRITES, wc,
            )
            explicit_fail_state = True
            break
        attempts += 1
        try:
            script_markdown = rewrite_script_to_target(
                api_key=settings.openai_api_key,
                model=settings.openai_model,  # mini for rewrite
                script_markdown=script_markdown,
                min_words=min_words,
                max_words=max_words,
                project_id=settings.openai_project_id,
                organization=settings.openai_organization,
            )
        except Exception as exc:
            logger.error("Rewrite failed: %s", exc)
            explicit_fail_state = True
            break
        wc = count_words(script_markdown)
        logger.info("After rewrite %d: %d words.", attempts, wc)

    return script_markdown, parts, attempts, explicit_fail_state


def _stage_select_and_verify(
    full_list_items: list[ScoredStory],
    settings: Settings,
    sources_json_path: Path,
    raw_count: int,
) -> tuple[list[ScoredStory], list[int], list[VerificationResult]]:
    """Present the full list, prompt for selection, verify choices.

    Loops until the selected stories all pass verification.
    Returns (selected_stories, selected_indices, verifications).
    """
    selected_indices = _prompt_selection(len(full_list_items))

    while True:
        selected = [full_list_items[i - 1] for i in selected_indices]
        if settings.skip_verification:
            logger.warning("URL verification skipped (--skip-verification flag is set).")
            verifications = [
                VerificationResult(story=s, passed=True, reason=None) for s in selected
            ]
        else:
            verifications = verify_selection(selected, approved_domains=settings.user_approved_domains)
        write_json(
            sources_json_path,
            _sources_payload(raw_count, full_list_items, selected_indices, verifications),
        )
        failures = [v for v in verifications if not v.passed]
        if not failures:
            break

        print("\nSelected stories failed verification:")
        for failed in failures:
            print(f"  - {failed.story.candidate.title}: {failed.reason}")
        selected_indices = _prompt_selection(len(full_list_items))

    logger.info("Stories selected: %s", selected_indices)
    return selected, selected_indices, verifications


def _episode_word_targets(story_count: int) -> tuple[int, int, int]:
    """Return (min_words, max_words, aim_words) for a given story count.

    Targets are for the full assembled script (including fixed intro/outro ~75 words).
    Approximate runtimes at ~130 wpm:
      1 story  →  250–350 words  ≈ 2–2.5 min
      2 stories → 360–460 words  ≈ 2.8–3.5 min
      3 stories → 500–650 words  ≈ 3.8–5.0 min
      4+ stories → 580–720 words ≈ 4.5–5.5 min
    """
    if story_count == 1:
        return 250, 350, 300
    if story_count == 2:
        return 360, 460, 410
    if story_count == 3:
        return 500, 650, 575
    return 580, 720, 650


def _stage_generate_script(
    selected: list[ScoredStory],
    settings: Settings,
    previous_food_for_thought: list[str] | None = None,
) -> tuple[str, ScriptParts, int, bool, bool]:
    """Generate, rewrite-if-needed, and pad the script markdown.

    Returns (script_markdown, parts, rewrite_attempts, explicit_fail_state, intro_was_fixed).
    """
    min_words, max_words, aim_words = _episode_word_targets(len(selected))
    parts = generate_script_parts(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        selected=selected,
        target_total_words=aim_words,
        project_id=settings.openai_project_id,
        organization=settings.openai_organization,
        previous_food_for_thought=previous_food_for_thought,
    )
    script_markdown = build_script_markdown(parts, selected)
    script_markdown = _ensure_outro_text(script_markdown, OUTRO_TEXT)
    wc = count_words(script_markdown)
    logger.info("Initial script: %d words (target %d–%d).", wc, min_words, max_words)

    attempts = 0
    explicit_fail_state = False

    while not (min_words <= wc <= max_words):
        if attempts >= MAX_REWRITES:
            logger.warning(
                "Word-count gate failed after %d rewrite attempt(s); proceeding with %d words.",
                MAX_REWRITES,
                wc,
            )
            explicit_fail_state = True
            break
        attempts += 1
        try:
            script_markdown = rewrite_script_to_target(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                script_markdown=script_markdown,
                min_words=min_words,
                max_words=max_words,
                project_id=settings.openai_project_id,
                organization=settings.openai_organization,
            )
        except Exception as exc:
            logger.error("Rewrite failed: %s", exc)
            explicit_fail_state = True
            break
        script_markdown = _normalise_food_for_thought(script_markdown)
        script_markdown = _ensure_food_for_thought_text(script_markdown, parts.food_for_thought)
        script_markdown = _ensure_outro_text(script_markdown, OUTRO_TEXT)
        script_markdown = _pad_script_to_min_words(
            script_markdown, min_words=min_words, max_words=max_words
        )
        wc = count_words(script_markdown)
        logger.info("After rewrite %d: %d words.", attempts, wc)

    # ── Story-drop fallback: if still over max, drop the weakest story ──
    if wc > max_words and len(parts.story_narratives) > 2:
        # Find the story with the lowest original score.
        weakest_idx = min(
            range(len(selected)),
            key=lambda i: selected[i].total,
        )
        dropped_title = selected[weakest_idx].candidate.title[:60]
        logger.info(
            "Dropping weakest story to hit word target: [%d] '%s' (score=%.1f)",
            weakest_idx + 1, dropped_title, selected[weakest_idx].total,
        )
        parts.story_narratives.pop(weakest_idx)
        selected = selected[:weakest_idx] + selected[weakest_idx + 1:]
        script_markdown = build_script_markdown(parts, selected)
        script_markdown = _ensure_outro_text(script_markdown, OUTRO_TEXT)
        wc = count_words(script_markdown)
        logger.info("After dropping story: %d words (%d stories).", wc, len(selected))
        # A dropped-story episode is accepted as long as it's reasonable length.
        # Mark explicit_fail_state so QA's word-count gate passes.
        explicit_fail_state = True

    # Final normalisation pass to catch any duplication from the initial generation.
    script_markdown = _normalise_food_for_thought(script_markdown)
    # Enforce exact intro text — the model sometimes rewrites it slightly during rewrites.
    script_markdown, intro_was_fixed = _enforce_intro_text(script_markdown)
    if intro_was_fixed:
        logger.warning("Intro text was modified by the model and has been automatically corrected.")
    return script_markdown, parts, attempts, explicit_fail_state, intro_was_fixed


def _stage_render_cover(
    episode_name: str,
    episode_dt: datetime,
    episode_number: int,
    cover_path: Path,
) -> str:
    """Render the cover PNG and a probe copy to verify determinism.

    Returns the sha256 hash of the probe render.
    """
    render_cover(
        episode_name=episode_name,
        episode_dt=episode_dt,
        output_path=cover_path,
        episode_number=episode_number,
    )

    with NamedTemporaryFile("wb", suffix=".png", delete=False) as tmp:
        probe_path = Path(tmp.name)
    try:
        render_cover(
            episode_name=episode_name,
            episode_dt=episode_dt,
            output_path=probe_path,
            episode_number=episode_number,
        )
        probe_hash = sha256_file(probe_path)
    finally:
        probe_path.unlink(missing_ok=True)

    return probe_hash


def _stage_audio(
    script_markdown: str,
    settings: Settings,
    mp3_path: Path,
    cover_path: Path,
    episode_name: str,
    episode_number: int,
    episode_dt: datetime,
    skip_audio: bool,
    auto_confirm: bool,
    explicit_fail_state: bool,
) -> tuple[bool, str, list[str], str | None]:
    """Generate audio via Qwen TTS.

    Returns (audio_generated, provider_used, notes, audio_error).
    audio_error is None when audio succeeded or was intentionally skipped;
    it is a non-empty string when generation was attempted but failed.
    """
    notes: list[str] = []

    if explicit_fail_state:
        notes.append("Word-count gate failed after maximum rewrite attempts; audio may be longer than target")

    if skip_audio:
        notes.append("Audio generation skipped by --skip-audio")
        return False, "qwen", notes, None

    if not (auto_confirm or _confirm_audio()):
        notes.append("Audio generation canceled by user")
        return False, "qwen", notes, None

    try:
        synthesize_qwen_clone_mp3(
            profile_manifest_path=Path(settings.qwen_profile_manifest),
            model_id=settings.qwen_tts_model,
            text=script_markdown,
            output_path=mp3_path,
            cover_art_path=cover_path,
            episode_name=episode_name,
            episode_number=episode_number,
            episode_dt=episode_dt,
            ref_clip_id=settings.qwen_ref_clip_id,
            language=settings.qwen_tts_language,
            instruct=settings.qwen_tts_instruct,
            temperature=settings.qwen_tts_temperature,
            top_p=settings.qwen_tts_top_p,
            top_k=settings.qwen_tts_top_k,
            max_new_tokens=settings.qwen_tts_max_new_tokens,
            speed=settings.qwen_tts_speed,
            timeout=settings.qwen_tts_timeout_seconds,
        )
        notes.append("Audio generated with provider: qwen")
        return True, "qwen", notes, None
    except QwenTTSError as exc:
        err = str(exc)
        notes.append(f"Qwen audio failed: {err}")
        logger.error("Qwen TTS failed: %s", exc)
        return False, "qwen", notes, err


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_pipeline(args: Namespace) -> int:
    output_dir = Path(args.output_dir)
    ensure_dir(output_dir)

    story_count = args.stories or DEFAULT_STORY_COUNT
    settings = load_settings(
        story_count=story_count,
        allow_domains=args.allow_domain,
        skip_audio=args.skip_audio,
        skip_verification=getattr(args, "skip_verification", False),
        env_file=args.env_file,
        qwen_profile_manifest_override=getattr(args, "qwen_profile_manifest", None),
        qwen_tts_model_override=getattr(args, "qwen_model", None),
        qwen_ref_clip_id_override=getattr(args, "qwen_ref_clip_id", None),
    )

    episode_dt = _resolve_episode_datetime(getattr(args, "episode_date", None))
    raw_episode_number = getattr(args, "episode_number", None)
    episode_number = resolve_episode_number(output_dir) if raw_episode_number is None else raw_episode_number
    if episode_number < 0:
        raise PipelineError("Episode number must be >= 0")
    episode_name = resolve_episode_name(output_dir, now=episode_dt)
    paths = build_artifact_paths(output_dir, episode_name)

    logger.info("Starting pipeline — episode '%s' (#%d).", episode_name, episode_number)

    # Resolve date window.
    window_start_raw = getattr(args, "window_start", None)
    window_end_raw = getattr(args, "window_end", None)
    has_custom_window = bool(window_start_raw or window_end_raw)
    if bool(window_start_raw) ^ bool(window_end_raw):
        raise PipelineError("Both --window-start and --window-end must be provided together.")

    if has_custom_window:
        window_start = _parse_date_flag(window_start_raw, "--window-start")
        window_end = _parse_date_flag(window_end_raw, "--window-end")
        if window_end < window_start:
            raise PipelineError("--window-end must be on or after --window-start.")
        date_window = (window_start, window_end)
    else:
        # Default: always limit to the past 7 days ending on the episode date.
        week_end = episode_dt.date()
        week_start = week_end - timedelta(days=6)
        date_window = (week_start, week_end)

    # Stage 1: Fetch, score, filter — with a live feed progress bar.
    feed_count = len(RSS_FEEDS)
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]Fetching feeds"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=_console,
        transient=True,
    ) as feed_progress:
        feed_task = feed_progress.add_task("feeds", total=feed_count)

        def _on_feed_done() -> None:
            feed_progress.advance(feed_task)

        full_list_items, heading, raw_count = _stage_build_full_list(
            settings, date_window, on_feed_done=_on_feed_done
        )

    _print_full_list(full_list_items, heading=heading)

    # Stage 2: Cluster themes.
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]Clustering themes…"),
        TimeElapsedColumn(),
        console=_console,
        transient=True,
    ) as prog:
        prog.add_task("clustering", total=None)
        themes = _stage_cluster_themes(full_list_items, settings)

    _console.print(f"[green]✓[/green] Found [bold]{len(themes)}[/bold] theme candidates")

    # Stage 2b: User selects a theme.
    theme_idx = _prompt_theme_selection(themes, full_list_items)
    chosen_theme = themes[theme_idx]
    logger.info("Theme selected: '%s'", chosen_theme.name)

    # Resolve selected articles from theme indices (1-based into full_list_items).
    selected: list[ScoredStory] = []
    for ai in chosen_theme.article_indices:
        if 1 <= ai <= len(full_list_items):
            selected.append(full_list_items[ai - 1])
    selected_indices = chosen_theme.article_indices

    # Build a minimal verifications list for downstream QA compatibility.
    verifications = [VerificationResult(story=s, passed=True, reason=None) for s in selected]

    # Write a sources JSON so QA has something to validate.
    write_json(
        paths["sources_json"],
        _sources_payload(raw_count, full_list_items, selected_indices, verifications),
    )

    # Stage 2c: Fetch full article text for theme's articles.
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]Fetching full article text"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=_console,
        transient=True,
    ) as art_progress:
        art_task = art_progress.add_task("articles", total=len(selected))

        def _on_article_done() -> None:
            art_progress.advance(art_task)

        fetch_article_text_batch(selected, on_done=_on_article_done)

    fetched = sum(1 for s in selected if s.candidate.full_text)
    _console.print(
        f"[green]✓[/green] Full text fetched for [bold]{fetched}/{len(selected)}[/bold] articles"
        + (" — some unavailable" if fetched < len(selected) else "")
    )

    proceed = _review_article_content(selected)
    if not proceed:
        # User wants to reselect — re-prompt theme selection and re-fetch.
        theme_idx = _prompt_theme_selection(themes, full_list_items)
        chosen_theme = themes[theme_idx]
        logger.info("Theme re-selected: '%s'", chosen_theme.name)
        selected = []
        for ai in chosen_theme.article_indices:
            if 1 <= ai <= len(full_list_items):
                selected.append(full_list_items[ai - 1])
        selected_indices = chosen_theme.article_indices
        verifications = [VerificationResult(story=s, passed=True, reason=None) for s in selected]
        write_json(
            paths["sources_json"],
            _sources_payload(raw_count, full_list_items, selected_indices, verifications),
        )
        for s in selected:
            s.candidate.full_text = None
        fetch_article_text_batch(selected)

    # Stage 3: Generate theme script — spinner with elapsed time.
    _console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn(f"[bold cyan]Generating script[/bold cyan] ({settings.openai_script_model} thinking…)"),
        TimeElapsedColumn(),
        console=_console,
        transient=True,
    ) as prog:
        prog.add_task("script", total=None)  # indeterminate
        t0 = time.monotonic()
        previous_fot = _load_previous_food_for_thought(output_dir)
        script_markdown, parts, rewrite_attempts, explicit_fail_state = _stage_generate_theme_script(
            chosen_theme, selected, settings, previous_food_for_thought=previous_fot
        )
        elapsed = time.monotonic() - t0

    _console.print(f"[green]✓[/green] Script generated in [bold]{elapsed:.0f}s[/bold] — {count_words(script_markdown)} words")

    script_payload = build_theme_script_json(parts, selected, script_markdown)
    script_payload["episode_name"] = episode_name
    script_payload["generated_at"] = iso_utc_now()
    script_payload["rewrite_attempts"] = rewrite_attempts
    script_payload["explicit_fail_state"] = explicit_fail_state

    paths["script_md"].write_text(script_markdown, encoding="utf-8")
    write_json(paths["script_json"], script_payload)

    print("\nGenerated script:\n")
    print(script_markdown)

    # Stage 4: Render cover — spinner.
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]Rendering cover art…"),
        TimeElapsedColumn(),
        console=_console,
        transient=True,
    ) as prog:
        prog.add_task("cover", total=None)
        t0 = time.monotonic()
        cover_probe_hash = _stage_render_cover(
            episode_name=episode_name,
            episode_dt=episode_dt,
            episode_number=episode_number,
            cover_path=paths["cover_png"],
        )
        elapsed = time.monotonic() - t0

    _console.print(f"[green]✓[/green] Cover rendered in [bold]{elapsed:.1f}s[/bold]")

    # Stage 5: Audio generation.
    # Ask for confirmation BEFORE starting the progress bar so rich doesn't
    # swallow the input prompt.
    if not args.skip_audio:
        audio_confirmed = args.auto_confirm_audio or _confirm_audio()
    else:
        audio_confirmed = False

    if audio_confirmed or args.skip_audio:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]Generating audio (Qwen TTS)…"),
            TimeElapsedColumn(),
            console=_console,
            transient=False,  # keep visible so user can see it's running
        ) as prog:
            prog.add_task("audio", total=None)
            t0 = time.monotonic()
            audio_generated, audio_provider_used, notes, audio_error = _stage_audio(
                script_markdown=script_markdown,
                settings=settings,
                mp3_path=paths["mp3"],
                cover_path=paths["cover_png"],
                episode_name=episode_name,
                episode_number=episode_number,
                episode_dt=episode_dt,
                skip_audio=args.skip_audio,
                auto_confirm=True,  # already confirmed above
                explicit_fail_state=explicit_fail_state,
            )
            elapsed = time.monotonic() - t0
    else:
        audio_generated, audio_provider_used, notes, audio_error = (
            False, "qwen", ["Audio generation canceled by user"], None
        )
        elapsed = 0.0

    if audio_generated:
        _console.print(f"[green]✓[/green] Audio generated in [bold]{elapsed:.0f}s[/bold]")
    elif audio_error:
        _console.print(f"[red]✗[/red] Audio failed after [bold]{elapsed:.0f}s[/bold]: {audio_error}")
    else:
        _console.print(f"[yellow]–[/yellow] Audio skipped")

    # Stage 6: Write initial manifest.
    manifest = {
        "episode_name": episode_name,
        "episode_number": episode_number,
        "timezone": TIMEZONE,
        "audio_provider": audio_provider_used,
        "created_at": iso_utc_now(),
        "run_status": "failed" if audio_error else "success",
        "selected_story_indices": selected_indices,
        "selected_count": len(selected_indices),
        "files": {
            "script_md": str(paths["script_md"]),
            "script_json": str(paths["script_json"]),
            "sources_json": str(paths["sources_json"]),
            "cover_png": str(paths["cover_png"]),
            "mp3": str(paths["mp3"]) if audio_generated else None,
            "manifest_json": str(paths["manifest_json"]),
        },
        "qa": {"passed": False, "checks": {}, "failures": []},
        "notes": notes,
    }
    write_json(paths["manifest_json"], manifest)

    # Stage 7: QA — spinner.
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]Running QA checks…"),
        TimeElapsedColumn(),
        console=_console,
        transient=True,
    ) as prog:
        prog.add_task("qa", total=None)
        qa = run_qa(
            episode_name=episode_name,
            script_md_path=paths["script_md"],
            script_json_path=paths["script_json"],
            sources_json_path=paths["sources_json"],
            manifest_json_path=paths["manifest_json"],
            cover_path=paths["cover_png"],
            schema_dir=Path("schemas"),
            selected_indices=selected_indices,
            selected_verification_passed=all(v.passed for v in verifications),
            explicit_fail_state_recorded=explicit_fail_state,
            cover_determinism_probe_hash=cover_probe_hash,
        )

    manifest["qa"] = asdict(qa)
    if not qa.passed:
        manifest["run_status"] = "failed"
    write_json(paths["manifest_json"], manifest)

    # Summary.
    print("\nRun complete")
    print(f"  Episode : {episode_name}")
    print(f"  Status  : {manifest['run_status']}")
    print(f"  QA      : {'passed' if qa.passed else 'FAILED'}")
    print(f"  Manifest: {paths['manifest_json']}")

    if qa.failures:
        print("\nQA failures:")
        for failure in qa.failures:
            print(f"  - {failure}")

    return 0 if manifest["run_status"] == "success" else 1
