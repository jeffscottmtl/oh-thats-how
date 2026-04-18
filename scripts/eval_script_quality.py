#!/usr/bin/env python3
"""Evaluate podcast script quality for A/B testing prompt variants.

Usage:
    python3 scripts/eval_script_quality.py output/The\ Signal\ –\ April\ 17,\ 2026\ 6\ -\ Script.json
    python3 scripts/eval_script_quality.py --compare output/*Script.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

# Add project root to path so we can import pipeline modules.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_podcast_pipeline.script_writer import (
    DOMAIN_TO_NAME,
    _validate_delivery_cues,
    _validate_opening_diversity,
)


def _word_position_of_first_pub_mention(narrative: str) -> int | None:
    """Return the word index (0-based) of the first publication name mention, or None."""
    words = narrative.split()
    lower_text_cumulative = ""
    for idx, word in enumerate(words):
        lower_text_cumulative += " " + word.lower()
        for pub in DOMAIN_TO_NAME.values():
            if pub.lower() in lower_text_cumulative:
                return idx
    return None


def _opening_pattern(narrative: str) -> str:
    """Classify the opening pattern of a narrative."""
    import re as _re
    first_sentence = _re.split(r'[.?!]', narrative, maxsplit=1)[0].lower()
    # Check for source-first
    for pub in DOMAIN_TO_NAME.values():
        if pub.lower() in first_sentence:
            return "source-in-first-sentence"
    if "?" in narrative.split(".")[0]:
        return "question"
    if any(w in first_sentence for w in ["counterintuitive", "surprising", "here's something", "here's the thing", "shouldn't make sense"]):
        return "tension"
    if any(w in first_sentence for w in ["what happens", "what does", "how do", "why do", "who gets"]):
        return "question"
    if any(w in first_sentence for w in ["for comms", "for communications", "for enterprise", "if you're building", "if your team"]):
        return "implication"
    if any(w in first_sentence for w in ["one detail", "picture this", "imagine"]):
        return "scene"
    return "insight"


def evaluate_script(script_json: dict) -> dict:
    """Score a script on multiple quality dimensions."""
    stories = script_json.get("stories", [])
    if stories and isinstance(stories[0], dict):
        narratives = [s.get("narrative", "") for s in stories]
    elif stories and isinstance(stories[0], str):
        narratives = stories
    else:
        narratives = script_json.get("story_narratives", [])

    if not narratives:
        return {"error": "No narratives found in script JSON"}

    # 1. Opening diversity
    opening_issues = _validate_opening_diversity(narratives)
    source_first_count = len(opening_issues)

    # 2. Attribution placement (average word position of first pub mention)
    positions = []
    for n in narratives:
        pos = _word_position_of_first_pub_mention(n)
        if pos is not None:
            positions.append(pos)
    avg_attribution_position = round(sum(positions) / len(positions), 1) if positions else None

    # 3. Opening patterns
    patterns = [_opening_pattern(n) for n in narratives]
    unique_patterns = len(set(patterns))

    # 4. Delivery cues
    cue_issues = _validate_delivery_cues(narratives)

    # 5. Word count
    total_words = sum(len(n.split()) for n in narratives)

    return {
        "narrative_count": len(narratives),
        "total_words": total_words,
        "source_first_openings": source_first_count,
        "avg_attribution_word_position": avg_attribution_position,
        "opening_patterns": patterns,
        "unique_opening_patterns": unique_patterns,
        "delivery_cue_issues": len(cue_issues),
        "delivery_cue_details": cue_issues if cue_issues else None,
    }


def print_report(filepath: str, scores: dict) -> None:
    """Print a formatted evaluation report."""
    print(f"\n{'=' * 60}")
    print(f"  {os.path.basename(filepath)}")
    print(f"{'=' * 60}")

    if "error" in scores:
        print(f"  ERROR: {scores['error']}")
        return

    print(f"  Narratives:              {scores['narrative_count']}")
    print(f"  Total words:             {scores['total_words']}")
    print()

    # Opening diversity
    src_first = scores["source_first_openings"]
    icon = "PASS" if src_first == 0 else "FAIL"
    print(f"  Source-first openings:    {src_first}/{scores['narrative_count']}  [{icon}]")
    print(f"  Avg attribution position: word {scores['avg_attribution_word_position']}")
    print(f"  Opening patterns:         {scores['opening_patterns']}")
    print(f"  Unique patterns:          {scores['unique_opening_patterns']}/{scores['narrative_count']}")
    print()

    # Delivery cues
    cue_count = scores["delivery_cue_issues"]
    icon = "PASS" if cue_count == 0 else f"FAIL ({cue_count})"
    print(f"  Delivery cues:            [{icon}]")
    if scores.get("delivery_cue_details"):
        for d in scores["delivery_cue_details"]:
            print(f"    - {d}")

    print()


def main():
    parser = argparse.ArgumentParser(description="Evaluate podcast script quality")
    parser.add_argument("files", nargs="+", help="Script.json files to evaluate")
    parser.add_argument("--compare", action="store_true", help="Side-by-side comparison mode")
    args = parser.parse_args()

    results = []
    for filepath in args.files:
        with open(filepath) as f:
            data = json.load(f)
        scores = evaluate_script(data)
        results.append((filepath, scores))
        print_report(filepath, scores)

    if args.compare and len(results) > 1:
        print(f"\n{'=' * 60}")
        print("  COMPARISON SUMMARY")
        print(f"{'=' * 60}")
        for filepath, scores in results:
            name = os.path.basename(filepath)[:40]
            src = scores.get("source_first_openings", "?")
            pos = scores.get("avg_attribution_word_position", "?")
            uniq = scores.get("unique_opening_patterns", "?")
            cues = scores.get("delivery_cue_issues", "?")
            print(f"  {name:<42} src-first={src}  attr-pos={pos}  patterns={uniq}  cue-issues={cues}")


if __name__ == "__main__":
    main()
