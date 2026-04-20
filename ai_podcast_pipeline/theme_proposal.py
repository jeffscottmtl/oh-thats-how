"""Theme proposal module.

Loads the theme bank, filters eligible themes by cooldown, scans RSS headlines,
and asks the LLM to propose exactly 20 episode themes.
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
_MAX_WEB_HEADLINES = 30
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
# Web search for AI+comms headlines
# ---------------------------------------------------------------------------


def _web_search_headlines(api_key: str) -> list[str]:
    """Search the web for fresh AI + communications headlines.

    Uses the OpenAI Responses API with web_search_preview to find recent
    articles about AI tools for communications professionals.
    Returns a list of headline strings.
    """
    import requests as _requests

    search_prompt = (
        "Search the web for recent articles about AI tools and techniques for "
        "communications professionals — people who write, edit, present, and draft "
        "content at work. Find articles about:\n"
        "- AI for speechwriting and executive communications\n"
        "- AI for internal communications and employee messaging\n"
        "- AI for presentation building and slide design\n"
        "- AI for email writing and newsletters\n"
        "- AI for content creation and editing in the workplace\n"
        "- AI for brainstorming, summarizing, and research\n"
        "- ChatGPT, Claude, Copilot tips for corporate communicators\n"
        "- Gartner reports on AI and communications\n\n"
        "Return a JSON object with key \"headlines\" — an array of strings, each being "
        "an article title followed by the source in parentheses.\n"
        "Example: \"How AI is Changing Corporate Speechwriting (Harvard Business Review)\"\n\n"
        "Return 20-30 headlines. Only include real, recent articles. "
        "Spread across diverse sources — no more than 3 from any single domain."
    )

    try:
        resp = _requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4.1-mini",
                "tools": [{"type": "web_search_preview"}],
                "input": search_prompt,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        text_content = ""
        for item in data.get("output", []):
            if item.get("type") == "message":
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        text_content += c["text"]

        if not text_content:
            logger.warning("Web search for headlines returned no content.")
            return []

        from .llm import parse_json_response
        parsed = parse_json_response(text_content)
        headlines = parsed.get("headlines", [])
        logger.info("Web search found %d AI+comms headlines.", len(headlines))
        return [str(h) for h in headlines if isinstance(h, str)]

    except Exception as exc:
        logger.warning("Web search for headlines failed: %s", exc)
        return []


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
        "You are an editorial assistant for The Signal, a podcast for communicators at CN "
        "(a large Canadian railway company). The audience builds PowerPoint presentations "
        "for executives, drafts speeches, writes emails and newsletters, and manages digital "
        "signage content. They are NOT technologists.\n\n"
        "Your job is to propose exactly 20 episode themes that would resonate with this "
        "audience. Each theme should feel immediately practical and relevant to someone who "
        "drafts, edits, presents, or publishes content for a living.\n\n"
        "LANGUAGE RULES:\n"
        "- In the pitch, say 'at CN' or 'at work' — NEVER 'your company', "
        "'your organization', 'within your company', or 'here at CN'.\n"
        "- Keep theme names short and action-oriented.\n\n"
        "SOURCE PREVIEW RULES:\n"
        "- source_previews must contain 2-3 headlines from the lists below that are "
        "DIRECTLY relevant to the theme. Do NOT attach unrelated headlines just to fill the field.\n"
        "- If no headlines below genuinely match a theme, use an empty array [] — "
        "do not force irrelevant sources.\n\n"
        "Return ONLY a JSON object with this schema — no markdown, no explanation:\n"
        "{\n"
        '  "proposals": [\n'
        "    {\n"
        '      "name": "Short, punchy theme title",\n'
        '      "pitch": "One-sentence pitch — use \'at CN\' not \'your company\'",\n'
        '      "source_previews": ["Relevant headline 1", "Relevant headline 2"],\n'
        '      "bank_id": "theme-bank-id-or-null"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Propose exactly 20 themes.\n"
        "- If a theme maps to a theme bank entry, set bank_id to its id; otherwise null.\n"
        "- Avoid politics, layoffs, sports, and gadget reviews.\n"
        "- Prioritise themes that a communicator can act on."
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
        "Based on the above, propose exactly 20 episode themes for The Signal. "
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

    # Run web search for fresh AI+comms headlines if not supplied.
    if web_headlines is None:
        logger.info("Running web search for AI+comms headlines…")
        web_headlines = _web_search_headlines(api_key)

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
