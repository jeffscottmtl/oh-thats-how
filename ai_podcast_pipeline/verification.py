from __future__ import annotations

import logging

import requests

from .models import ScoredStory, VerificationResult

logger = logging.getLogger(__name__)


def _is_reachable_status(status_code: int) -> bool:
    # Some trusted publishers (e.g., OpenAI, NYT) block bot user-agents with 403/401
    # while the page remains valid. 429 means rate-limited but content exists.
    return status_code < 400 or status_code in {401, 403, 429}


def verify_story(
    story: ScoredStory,
    approved_domains: set[str],
    timeout: int = 8,
) -> VerificationResult:
    domain = story.candidate.source_domain
    if domain not in approved_domains:
        return VerificationResult(story=story, passed=False, reason="Domain not approved by policy")

    if story.candidate.published_at is None:
        return VerificationResult(story=story, passed=False, reason="Publication date missing or unparseable")

    url = story.candidate.url
    reachable = False

    # Try HEAD first (lightweight); fall back to GET if HEAD fails or returns an error.
    try:
        resp = requests.head(
            url, timeout=timeout, allow_redirects=True, headers={"User-Agent": "TheSignalBot/1.0"}
        )
        reachable = _is_reachable_status(resp.status_code)
        logger.debug("HEAD %s → HTTP %d (reachable=%s)", url, resp.status_code, reachable)
    except requests.RequestException as exc:
        logger.debug("HEAD failed for %s: %s", url, exc)
        reachable = False

    if not reachable:
        try:
            resp = requests.get(
                url, timeout=timeout, allow_redirects=True, headers={"User-Agent": "TheSignalBot/1.0"}
            )
            reachable = _is_reachable_status(resp.status_code)
            logger.debug("GET %s → HTTP %d (reachable=%s)", url, resp.status_code, reachable)
        except requests.RequestException as exc:
            logger.debug("GET failed for %s: %s", url, exc)
            reachable = False

    if not reachable:
        return VerificationResult(story=story, passed=False, reason="Source URL is not reachable")

    return VerificationResult(story=story, passed=True, reason=None)


def verify_selection(
    selected: list[ScoredStory],
    approved_domains: set[str],
) -> list[VerificationResult]:
    results = [verify_story(item, approved_domains=approved_domains) for item in selected]
    passed = sum(1 for r in results if r.passed)
    logger.info(
        "Verification complete: %d/%d stories passed.", passed, len(results)
    )
    return results
