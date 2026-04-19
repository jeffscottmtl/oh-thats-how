"""Theme proposal module.

Loads the theme bank, filters eligible themes by cooldown, scans RSS headlines,
and asks the LLM to propose exactly 10 episode themes.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Callable

from .constants import THEME_COOLDOWN_DAYS, THEME_BANK_PATH
from .ingest import fetch_candidates
from .llm import OpenAIError, chat_completion, parse_json_response
from .models import CandidateStory, ThemeBankEntry, ThemeProposal

logger = logging.getLogger(__name__)

# Caps applied when building the LLM prompt.
_MAX_RSS_HEADLINES = 40
_MAX_WEB_HEADLINES = 20
# How many RSS candidates to pull for headline extraction.
_RSS_SCAN_LIMIT = 60


# ---------------------------------------------------------------------------
# Bank I/O
# ---------------------------------------------------------------------------


def load_theme_bank(path: Path) -> list[ThemeBankEntry]:
    """Load theme bank entries from a JSON file.

    Returns an empty list if the file does not exist.
    """
    if not path.exists():
        logger.debug("Theme bank not found at %s — returning empty list.", path)
        return []

    with path.open(encoding="utf-8") as fh:
        raw = json.load(fh)

    entries: list[ThemeBankEntry] = []
    for item in raw:
        entries.append(
            ThemeBankEntry(
                id=item["id"],
                name=item["name"],
                description=item["description"],
                tags=item.get("tags", []),
                last_used=item.get("last_used"),
                times_used=item.get("times_used", 0),
            )
        )
    logger.debug("Loaded %d theme bank entries from %s.", len(entries), path)
    return entries


def save_theme_bank(path: Path, entries: list[ThemeBankEntry]) -> None:
    """Write theme bank entries back to a JSON file.

    Creates parent directories if they do not exist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "id": e.id,
            "name": e.name,
            "description": e.description,
            "tags": e.tags,
            "last_used": e.last_used,
            "times_used": e.times_used,
        }
        for e in entries
    ]
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    logger.debug("Saved %d theme bank entries to %s.", len(entries), path)


# ---------------------------------------------------------------------------
# Bank helpers
# ---------------------------------------------------------------------------


def mark_theme_used(entries: list[ThemeBankEntry], theme_id: str) -> None:
    """Set last_used to today (ISO format) and increment times_used in-place.

    Does nothing if theme_id is not found in entries.
    """
    today = date.today().isoformat()
    for entry in entries:
        if entry.id == theme_id:
            entry.last_used = today
            entry.times_used += 1
            logger.debug("Marked theme '%s' as used on %s.", theme_id, today)
            return
    logger.warning("mark_theme_used: theme id '%s' not found in bank.", theme_id)


def get_eligible_themes(
    entries: list[ThemeBankEntry],
    cooldown_days: int = THEME_COOLDOWN_DAYS,
) -> list[ThemeBankEntry]:
    """Return themes not used within the cooldown window.

    Themes with last_used=None (never used) are always eligible.
    """
    today = date.today()
    eligible: list[ThemeBankEntry] = []
    for entry in entries:
        if entry.last_used is None:
            eligible.append(entry)
            continue
        try:
            last = date.fromisoformat(entry.last_used)
        except ValueError:
            logger.warning("Invalid last_used date '%s' for theme '%s' — treating as eligible.", entry.last_used, entry.id)
            eligible.append(entry)
            continue
        days_since = (today - last).days
        if days_since >= cooldown_days:
            eligible.append(entry)
    logger.debug(
        "Eligible themes: %d of %d (cooldown=%d days).",
        len(eligible), len(entries), cooldown_days,
    )
    return eligible


# ---------------------------------------------------------------------------
# RSS headline scan
# ---------------------------------------------------------------------------


def _scan_rss_headlines(
    on_feed_done: Callable[[], None] | None = None,
) -> list[CandidateStory]:
    """Fetch RSS candidates and return the first _RSS_SCAN_LIMIT stories."""
    candidates = fetch_candidates(
        max_candidates=_RSS_SCAN_LIMIT,
        on_feed_done=on_feed_done,
    )
    return candidates[:_RSS_SCAN_LIMIT]


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def _build_prompt(
    eligible: list[ThemeBankEntry],
    rss_stories: list[CandidateStory],
    web_headlines: list[str] | None,
) -> str:
    """Build the system + user messages for the LLM."""
    # ---- system message ----
    system = (
        "You are an editorial assistant for The Signal, a weekly AI podcast aimed at "
        "communicators at a large Canadian railway company (CN). The audience is made up "
        "of people who write the stories, build the presentations, draft the speeches, and "
        "send the emails — non-technical professionals who care about how AI can make their "
        "daily writing and communications work better, faster, and smarter.\n\n"
        "Your job is to propose exactly 10 episode themes that would resonate with this "
        "audience. Each theme should feel immediately practical and relevant to someone who "
        "drafts, edits, presents, or publishes content for a living.\n\n"
        "Return ONLY a JSON object with this schema — no markdown, no explanation:\n"
        "{\n"
        '  "proposals": [\n'
        "    {\n"
        '      "name": "Short, punchy theme title",\n'
        '      "pitch": "One-sentence pitch the host would say on air",\n'
        '      "source_previews": ["Headline or URL 1", "Headline or URL 2"],\n'
        '      "bank_id": "theme-bank-id-or-null"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Propose exactly 10 themes.\n"
        "- source_previews must contain 2-3 items drawn from the headlines below.\n"
        "- If a theme maps to a theme bank entry, set bank_id to its id; otherwise null.\n"
        "- Avoid politics, layoffs, sports, and gadget reviews.\n"
        "- Prioritise themes that a communicator can act on this week."
    )

    # ---- user message: bank themes ----
    if eligible:
        bank_lines = "\n".join(
            f"  [{e.id}] {e.name} — {e.description}" for e in eligible
        )
        bank_section = f"## Eligible theme bank entries\n{bank_lines}\n\n"
    else:
        bank_section = "## Eligible theme bank entries\n(none — all themes are on cooldown)\n\n"

    # ---- user message: RSS headlines ----
    rss_slice = rss_stories[:_MAX_RSS_HEADLINES]
    if rss_slice:
        rss_lines = "\n".join(
            f"  - {s.title} ({s.source_domain})" for s in rss_slice
        )
        rss_section = f"## RSS headlines (last scan)\n{rss_lines}\n\n"
    else:
        rss_section = "## RSS headlines (last scan)\n(none available)\n\n"

    # ---- user message: web headlines ----
    if web_headlines:
        web_slice = web_headlines[:_MAX_WEB_HEADLINES]
        web_lines = "\n".join(f"  - {h}" for h in web_slice)
        web_section = f"## Web search headlines\n{web_lines}\n\n"
    else:
        web_section = ""

    user = (
        f"{bank_section}"
        f"{rss_section}"
        f"{web_section}"
        "Based on the above, propose exactly 10 episode themes for The Signal. "
        "Return the JSON object described in the system prompt."
    )

    return system, user


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def propose_themes(
    api_key: str,
    model: str,
    theme_bank_path: Path | str = THEME_BANK_PATH,
    rss_headlines: list[CandidateStory] | None = None,
    web_headlines: list[str] | None = None,
    project_id: str | None = None,
    organization: str | None = None,
    on_feed_done: Callable[[], None] | None = None,
) -> tuple[list[ThemeProposal], list[ThemeBankEntry]]:
    """Propose 5 episode themes for The Signal.

    1. Loads the theme bank from theme_bank_path.
    2. Filters to eligible themes (outside cooldown window).
    3. Fetches RSS headlines if rss_headlines is not provided.
    4. Builds a prompt and calls the LLM at temperature 0.4.
    5. Parses the response into ThemeProposal objects.

    Returns (proposals, bank_entries) so the caller can update the bank later
    (e.g. by calling mark_theme_used and save_theme_bank).
    """
    bank_path = Path(theme_bank_path)
    bank_entries = load_theme_bank(bank_path)
    eligible = get_eligible_themes(bank_entries)

    # Fetch RSS headlines if not supplied by the caller.
    if rss_headlines is None:
        logger.info("Scanning RSS feeds for theme proposal headlines…")
        rss_stories = _scan_rss_headlines(on_feed_done=on_feed_done)
    else:
        rss_stories = list(rss_headlines)

    system_msg, user_msg = _build_prompt(eligible, rss_stories, web_headlines)

    logger.info(
        "Calling LLM (%s) to propose themes — %d bank entries eligible, "
        "%d RSS stories, %d web headlines.",
        model,
        len(eligible),
        len(rss_stories[:_MAX_RSS_HEADLINES]),
        len((web_headlines or [])[:_MAX_WEB_HEADLINES]),
    )

    raw = chat_completion(
        api_key=api_key,
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        project_id=project_id,
        organization=organization,
        temperature=0.4,
    )

    data = parse_json_response(raw)
    raw_proposals = data.get("proposals", [])

    proposals: list[ThemeProposal] = []
    for item in raw_proposals:
        proposals.append(
            ThemeProposal(
                name=item.get("name", ""),
                pitch=item.get("pitch", ""),
                source_previews=item.get("source_previews", []),
                bank_id=item.get("bank_id") or None,
            )
        )

    logger.info("LLM proposed %d themes.", len(proposals))
    return proposals, bank_entries
