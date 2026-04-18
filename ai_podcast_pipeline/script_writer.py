from __future__ import annotations

import logging
import re
from typing import Any

from .constants import ENDING_TOKEN, INTRO_TEXT, OUTRO_TEXT
from .llm import OpenAIError, chat_completion, parse_json_response
from .models import ScoredStory, ScriptParts
from .utils import count_words

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Delivery-cue validation helpers
# ---------------------------------------------------------------------------

def _count_em_dashes(text: str) -> int:
    return text.count("—")


def _count_questions(text: str) -> int:
    return text.count("?")


def _has_short_sentence(text: str, max_words: int = 5) -> bool:
    """Return True if text contains at least one sentence of max_words or fewer."""
    sentences = re.split(r'[.!?]+', text)
    return any(0 < len(s.strip().split()) <= max_words for s in sentences)


def _count_italic_emphasis(text: str) -> int:
    return len(re.findall(r'\*[^*]+\*', text))


def _validate_delivery_cues(narratives: list[str]) -> list[str]:
    """Return a list of issues found in the narratives' delivery cues."""
    issues: list[str] = []
    for i, n in enumerate(narratives, 1):
        dashes = _count_em_dashes(n)
        questions = _count_questions(n)
        short = _has_short_sentence(n)
        if dashes < 2:
            issues.append(f"Story {i}: only {dashes} em dashes (need ≥2)")
        if questions < 1:
            issues.append(f"Story {i}: no rhetorical questions (need ≥1)")
        if not short:
            issues.append(f"Story {i}: no short sentence (≤5 words)")
    all_text = " ".join(narratives)
    if _count_italic_emphasis(all_text) < 1:
        issues.append("No *italicized emphasis* found in any narrative (need ≥1)")
    return issues


def _validate_opening_diversity(narratives: list[str]) -> list[str]:
    """Return issues if the first sentence of any narrative contains a publication/company name."""
    pub_names = list(DOMAIN_TO_NAME.values())
    issues: list[str] = []
    for i, n in enumerate(narratives, 1):
        # Extract first sentence (up to first period, question mark, or exclamation).
        first_sentence = re.split(r'[.?!]', n, maxsplit=1)[0].lower()
        for pub in pub_names:
            pub_l = pub.lower()
            if pub_l in first_sentence:
                issues.append(
                    f"Story {i}: first sentence contains source name '{pub}' — "
                    "move attribution to sentence 2 or later"
                )
                break
    return issues

# Map raw source domains to proper publication names for natural attribution.
DOMAIN_TO_NAME: dict[str, str] = {
    "theglobeandmail.com": "The Globe and Mail",
    "nytimes.com": "The New York Times",
    "washingtonpost.com": "The Washington Post",
    "wsj.com": "The Wall Street Journal",
    "ft.com": "The Financial Times",
    "bbc.com": "the BBC",
    "bbc.co.uk": "the BBC",
    "theguardian.com": "The Guardian",
    "bloomberg.com": "Bloomberg",
    "reuters.com": "Reuters",
    "apnews.com": "the Associated Press",
    "cbc.ca": "the CBC",
    "ctvnews.ca": "CTV News",
    "techcrunch.com": "TechCrunch",
    "theverge.com": "The Verge",
    "wired.com": "Wired",
    "axios.com": "Axios",
    "hbr.org": "Harvard Business Review",
    "technologyreview.com": "MIT Technology Review",
    "sloanreview.mit.edu": "MIT Sloan Management Review",
    "venturebeat.com": "VentureBeat",
    "arstechnica.com": "Ars Technica",
    "zdnet.com": "ZDNet",
    "fastcompany.com": "Fast Company",
    "cnbc.com": "CNBC",
    "forbes.com": "Forbes",
    "businessinsider.com": "Business Insider",
    "npr.org": "NPR",
    "infoq.com": "InfoQ",
    "openai.com": "OpenAI",
    "anthropic.com": "Anthropic",
    "microsoft.com": "Microsoft",
    "blogs.microsoft.com": "Microsoft",
    "blog.google": "Google",
    "deepmind.google": "DeepMind",
    "prdaily.com": "PR Daily",
    "prweek.com": "PRWeek",
    "prmoment.com": "PR Moment",
    "meltwater.com": "Meltwater",
    "cision.com": "Cision",
    "engadget.com": "Engadget",
    "abcnews.go.com": "ABC News",
    "cnn.com": "CNN",
    "9to5mac.com": "9to5Mac",
    "macrumors.com": "MacRumors",
    "apple.com": "Apple",
    "simonwillison.net": "Simon Willison's Weblog",
    "jack-clark.net": "Import AI",
    "huggingface.co": "Hugging Face",
    "engineering.fb.com": "Meta Engineering",
    "ai.meta.com": "Meta AI",
    "ragan.com": "Ragan Communications",
    "spinsucks.com": "Spin Sucks",
    "stratechery.com": "Stratechery",
    "ben-evans.com": "Benedict Evans",
    "thedeepview.substack.com": "The Deep View",
    "therundown.substack.com": "The Rundown AI",
    "lastweekin.ai": "Last Week in AI",
}


def _pub_name(domain: str) -> str:
    """Return a proper publication name for a domain, e.g. 'The Globe and Mail'."""
    return DOMAIN_TO_NAME.get(domain, domain)


def _narrative_word_range(story_count: int) -> tuple[int, int]:
    if story_count <= 2:
        return (230, 290)
    if story_count == 3:
        return (170, 220)
    if story_count == 4:
        return (140, 185)
    if story_count == 5:
        return (120, 160)
    return (105, 145)


_OPENING_ARCHETYPES = ["insight", "tension", "question", "implication", "scene"]

_ARCHETYPE_GUIDANCE: dict[str, str] = {
    "insight":     "State the surprising finding or conclusion first — not who found it. The source comes after.",
    "tension":     "Open with what's counterintuitive, contradictory, or went wrong. No source name in sentence 1.",
    "question":    "Pose the question the article answers. The source is introduced when you start answering it.",
    "implication": "Start with what this means for the listener's work, then back into the story. Source is context, not the lead.",
    "scene":       "Pick one vivid, specific detail or moment from the article and use it as the entry point. Source follows the scene.",
}


def _stories_prompt_blob(selected: list[ScoredStory]) -> str:
    rows: list[str] = []
    for idx, story in enumerate(selected, start=1):
        c = story.candidate
        published = c.published_at.isoformat() if c.published_at else "unknown"
        if not c.full_text:
            raise ValueError(
                f"Story {idx} '{c.title}' has no full text. "
                "RSS summaries are not accepted for script generation."
            )
        archetype = _OPENING_ARCHETYPES[(idx - 1) % len(_OPENING_ARCHETYPES)]
        archetype_guide = _ARCHETYPE_GUIDANCE[archetype]
        rows.append(
            f"{idx}. title={c.title}\n"
            f"   url={c.url}\n"
            f"   source={_pub_name(c.source_domain)}\n"
            f"   published_at={published}\n"
            f"   suggested_opening_approach={archetype} — {archetype_guide}\n"
            f"   full_article_text={c.full_text}"
        )
    return "\n\n".join(rows)


# Transition openers by position in the episode.
# These are sentence starters only — the GPT narrative follows directly.
_STARTERS = ["To start,", "First up,", "Kicking things off,", "Starting this week,"]
_CLOSERS  = ["And finally,", "Before we wrap,", "To close,", "One last story —"]
_MIDS     = ["Next,", "Also this week,", "Moving on,", "Here's another one:"]


def _story_lead(index: int, total: int) -> str:
    """Return a short transition opener for story `index` of `total`."""
    if total <= 1:
        return "This week,"
    if index == 1:
        return _STARTERS[(index - 1) % len(_STARTERS)]
    if index == total:
        return _CLOSERS[(index - 1) % len(_CLOSERS)]
    return _MIDS[(index - 1) % len(_MIDS)]


def _lc_first(text: str) -> str:
    """Lowercase the first character of text unless it's a standalone 'I'."""
    if not text:
        return text
    first_word = text.split()[0] if text.split() else ""
    if first_word in {"I", "I've", "I'm", "I'll", "I'd", "I'd"}:
        return text
    return text[0].lower() + text[1:]


def _fallback_parts(selected: list[ScoredStory]) -> ScriptParts:
    """Return a minimal script when the LLM call fails."""
    logger.warning("Using fallback script parts for %d stories.", len(selected))
    narratives = []
    for story in selected:
        c = story.candidate
        pub = _pub_name(c.source_domain)
        summary = c.summary.strip()
        summary_part = summary[:320] if summary else "there are practical implications for how communications teams approach their work."
        narratives.append(
            f"there's a story from {pub} that's worth knowing about. "
            f"{summary_part} "
            "For communications and strategy professionals, the value here isn't just novelty — "
            "the meaningful takeaway is how this can reduce repetitive work, improve message quality, "
            "and create more time for judgment-heavy decisions that still require human context."
        )
    food = (
        "The pattern across these stories is practical, not theoretical: teams that pair AI speed with "
        "human judgment communicate faster and more clearly. The opportunity now is to pick the right "
        "workflows for automation while protecting tone, trust, and accountability."
    )
    return ScriptParts(story_narratives=narratives, cn_relevance=None, food_for_thought=food)


def _build_fot_history_block(previous_fot: list[str] | None) -> str:
    """Return a prompt block listing previous Food for Thought topics to avoid repeats."""
    if not previous_fot:
        return ""
    items = "\n".join(f"  - {fot[:200]}" for fot in previous_fot[-10:])
    return f"""
IMPORTANT — Previous Food for Thought topics (DO NOT repeat or closely paraphrase any of these):
{items}
Your food_for_thought MUST be original — a genuinely new topic, angle, or idea that does not overlap with any of the above.
"""


def generate_script_parts(
    api_key: str,
    model: str,
    selected: list[ScoredStory],
    target_total_words: int,
    project_id: str | None = None,
    organization: str | None = None,
    previous_food_for_thought: list[str] | None = None,
) -> ScriptParts:
    story_blob = _stories_prompt_blob(selected)
    fot_history = _build_fot_history_block(previous_food_for_thought)

    prompt = f"""
You are the host of a friendly, upbeat weekly podcast called The Signal. Your audience is your colleagues — communications professionals working across a large enterprise that handles both internal and external communications. Internal communications include updates and messaging to senior management and unionized frontline employees. External communications reach customers, potential customers, potential employees, First Nations communities, media, government officials, regulators, and the general public.

━━━ OPENING RULE — READ THIS BEFORE WRITING ANYTHING ━━━
Every story narrative must open with the substance of the story — NOT the source.
This is the single most important constraint in this entire prompt.

NEVER start a narrative with any of these patterns:
  ✗ "[Publication] reports/argues/says that..."
  ✗ "According to [Publication]..."
  ✗ "A new [Publication] piece says/looks at..."
  ✗ "[Company] announced/launched/released..."
  ✗ "[Company]'s new [thing] shows/represents..."

ALWAYS lead with the finding, tension, question, implication, or scene:
  ✓ "Enterprise AI might have less to do with the model and more to do with everything around it..."
  ✓ "There's a fault line in how most teams are rolling out AI — and it's not the technology."
  ✓ "What does it actually take to make AI useful inside a large organization?"
  ✓ "Lawyers are getting a warning they didn't expect — and it's coming from a federal court."
  ✓ "The anxiety employees feel about AI at work doesn't go away just because you run a training session."

Attribution goes INSIDE the narrative — mid-sentence, parenthetical, or toward the end.
The first sentence of every narrative must contain ZERO publication or company names.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Voice and tone:
- You're an enthusiastic colleague who genuinely loves this stuff and can't wait to share what you found. Conversational, warm, plain language — not corporate-speak, not consulting-speak.
- Use contractions naturally throughout: "it's", "you'll", "I've", "couldn't", "didn't", "that's", "here's". Avoid stiff constructions like "it is" or "I could not" where a contraction sounds more natural in speech.
- Never read articles verbatim or near-verbatim. Synthesize, interpret, and put everything in your own words.
- Strip out any redundant, repetitive, or boilerplate phrasing pulled from the source material (e.g., "In a world where…", "It's more important than ever…", "As we navigate…"). Cut anything that sounds like filler.

Delivery and pacing — THIS IS MANDATORY, not optional styling:
This script is read aloud by a text-to-speech engine. The formatting below directly controls vocal expressiveness. Scripts that lack these elements sound flat and robotic. You MUST include all of the following in every narrative:

1. Em dashes (—) for mid-sentence pivots, asides, and dramatic pauses. Use at least 2–3 per story narrative.
   FLAT: "The report found that most teams are not ready for this shift. The implications are significant."
   EXPRESSIVE: "The report found that most teams — even the ones that think they're ready — are nowhere close. And the implications? Significant."

2. Rhetorical questions to create natural vocal inflection. Use at least 1 per story narrative.
   FLAT: "This matters because communications teams will need to adapt quickly."
   EXPRESSIVE: "So what does that actually mean for comms teams? It means adapting — and fast."

3. Varied sentence length — short punchy sentences after longer ones. Every narrative must have at least one sentence of 5 words or fewer for impact.
   FLAT: "The author argues that organizations need to rethink their approach to internal messaging when deploying AI tools."
   EXPRESSIVE: "The author's argument is clear — organizations need to completely rethink internal messaging when they roll out AI tools. And most haven't even started."

4. Italicized emphasis (*word*) to signal vocal stress on a key word. Use at least 1–2 per story narrative.
   FLAT: "The issue isn't whether AI will change the workflow, it's how fast."
   EXPRESSIVE: "The issue isn't *whether* AI will change the workflow — it's *how fast*."

5. Isolated impact sentences — when a point deserves emphasis, give it its own short sentence.
   FLAT: "This is a significant development that teams should pay attention to."
   EXPRESSIVE: "That's a big deal."

6. Ellipses sparingly for genuine trailing-off moments: "and that's where it gets interesting…"

7. Front-loaded energy for surprise or excitement: "Remarkable, really — they cut turnaround time by 60 percent."

8. Natural breathing points — if a sentence runs past 30 words, break it up.

Perspective rules — this is critical:
- When covering a story, you are the narrator summarizing an article for your listeners. Always write in third person about the article, its author, and its subject matter. Use attribution: "the author argues", "she describes", "they found", "the piece explains", "according to the report". Never slip into the article author's voice.
- First person ("I", "I've", "I found") is ONLY for: (a) your own editorial reaction to a story ("I found this one really striking"), (b) the intro, (c) the food for thought segment, and (d) the outro. It is never used to describe what an article says or what someone in an article experienced.
- Bad: "I was a newcomer, negotiating all of the usual classroom difficulties." (this is the article author's voice, not yours)
- Good: "The author describes being a complete newcomer — navigating all the usual classroom challenges while also trying to figure out what to do about the AI in every student's pocket."
- Bad: "I couldn't believe how quickly things changed." (ambiguous — whose experience?)
- Good: "What struck me reading this is how quickly the author's skepticism shifted once she was actually in the room." (narrator's reaction, clearly attributed)

Return ONLY valid JSON with exactly these keys:
- story_narratives: array of exactly {len(selected)} strings, one per story, in the exact order provided
- cn_relevance: string or null
- food_for_thought: string

Story narrative guidelines:
- Write {len(selected)} narratives. Each narrative should naturally cover:
  1) What the article is about — the subject and context
  2) What changed or what's new, if applicable (skip if there's no meaningful "before" state)
  3) Why it matters right now
  4) What it means practically for communications professionals in a large enterprise like ours — internal messaging, stakeholder engagement, media relations, or public communications
- Mention the source outlet naturally within the narrative, using its proper publication name exactly as provided in the source field (e.g. "according to The Globe and Mail", "a piece in The Guardian", "Bloomberg reports"). Never use the raw domain name (e.g. never "theglobeandmail.com" or "bloomberg.com") — always the publication name from the source field.
- No bullet points, no headers, no numbered labels like "Story 1". Flowing paragraphs only.
- Do NOT use or paraphrase any RSS summary text — narratives must be based solely on the full article content provided.
- DO NOT open the narrative with a transition phrase like "To start," or "Next," or "Finally," — those are added automatically. Begin directly with the substance.
- THE FIRST SENTENCE OF EVERY NARRATIVE MUST NOT CONTAIN THE PUBLICATION NAME OR SOURCE.
  This is a hard constraint. Attribution goes inside the narrative — mid-sentence, parenthetical, or near the end. Never as the opening clause.

  WRONG — every one of these will be rejected:
    "MIT Technology Review argues that enterprise AI success depends on..."
    "CNBC reports that Anthropic is making a deliberate tradeoff..."
    "According to The Guardian, a federal court in Australia is warning..."
    "A new MIT Sloan piece says AI adoption often gets stuck at..."
    "Google's AI Forum shows how far the conversation has moved..."
    "Anthropic's new model represents a shift in..."

  RIGHT — lead with the substance, let attribution follow:
    "Enterprise AI success might have less to do with the model and more to do with everything wrapped around it — MIT Technology Review makes that case this week."
    "There's a deliberate design choice built into the latest model — and understanding why it was made tells you a lot about where safety research is heading. CNBC has the details."
    "A federal court in Australia is warning lawyers about something that should concern every professional who uses AI to draft documents."
    "AI adoption keeps stalling at the same point — and it's not the technology. A piece in MIT Sloan traces the bottleneck to a much more human problem."
    "The conversation about AI's economic impact has moved somewhere most people haven't caught up to yet."

- VARY the opening structure across stories. Use a different approach for each story — rotate among these:
  * INSIGHT: state the surprising finding or conclusion first, then explain the source.
  * TENSION: open with what's counterintuitive, what went wrong, or what two ideas collide.
  * QUESTION: pose the question the article answers, then walk through what it found.
  * IMPLICATION: start with what this means for the listener's work, then back into the story.
  * SCENE: pick one vivid, specific detail from the article and use it as the entry point.
  No two consecutive stories should use the same opening approach.
- NEVER lead with or echo the article headline. Open with the actual substance — what the story is really about, in plain human terms. Bad: "The Globe and Mail reports that when it comes to AI adoption, training isn't nearly enough." Good: "A Globe and Mail piece makes a compelling case that the anxiety people feel about AI at work doesn't go away just because you run a training session." The headline is source material, not your opening line.
- Never adopt the article author's voice. You are paraphrasing their work in third person — "the author argues", "she describes", "the report found", "he writes". The only first-person voice in a story narrative is your own brief editorial reaction ("what struck me about this", "I think this one's worth sitting with"), clearly distinct from the article content.
- Never repeat the same information twice in consecutive sentences. If you've just said what a story is about, don't restate it in the next sentence with slightly different words.

EXAMPLE NARRATIVES — study the opening of each one carefully.
Rule: the source NEVER appears in the first sentence. Notice how each example opens.
Do not copy these; use them as structural models only.

Example A — INSIGHT opening (surprising conclusion first, source mid-sentence):
"Most AI adoption failures have nothing to do with the technology. That's the blunt conclusion of a piece in Harvard Business Review this week — and the evidence is uncomfortable. Teams that had a tool dropped on them with no context were *three times* more likely to abandon it within a month. Not because the tool was bad. Because nobody explained what it replaced, what it didn't, and why this team was chosen to go first. For comms teams, that last part is the whole job — and it's exactly the kind of framing most rollouts skip."

Example B — TENSION opening (counterintuitive collision, source late):
"Here's something that shouldn't make sense but does: the companies moving fastest on AI are putting *more* humans in the loop, not fewer. The pattern shows up in customer service, in content review, even in code deployment. Why? Because speed gains only hold if someone catches the errors before they reach the customer. A sharp analysis from Wired backs this up — and it lines up with what a lot of enterprise teams are quietly finding. The practical takeaway for comms: don't promise AI will reduce headcount. Promise it'll reduce the *boring parts*."

Example C — QUESTION opening (source early-middle, after the question is posed):
"What happens when your AI tool gets smarter every time your team uses it — but nobody told the team? MIT Technology Review walks through exactly that scenario in a recent piece. Workflow data feeds back into the model, improving outputs — but employees had no idea their decisions were training the system. The comms gap is obvious. If people don't know how the tool learns, they can't trust it. And if they can't trust it? They won't use it honestly."

Example D — IMPLICATION opening (lead with what it means for the listener, source parenthetical):
"If you're building AI literacy programs for your team, one finding should give you pause — the anxiety people feel about AI at work doesn't go away just because you run a training session. It can actually get worse. A Globe and Mail piece this week digs into the psychology behind this, and the author's prescription is specific: training needs to be paired with agency — people need to actually *do* something with the tool, on real work, before the anxiety shifts. For large enterprise comms teams, that's a deployment design problem, not a content problem."

cn_relevance guidelines:
- Optional. Include only when there's a genuinely specific angle that applies to large-enterprise communications — internal messaging, unionized employee communications, Indigenous community relations, regulatory communications, media response, or public-facing content.
- Write in first person. Keep it to 2–3 sentences max.
- Skip it if the connection is generic or obvious.

food_for_thought guidelines:
- This is a standalone closing segment — it doesn't need to connect to the week's stories at all.
- Topic: something about AI, communications, or strategy that's novel, curious, funny, insightful, or practically useful — something the listener probably hasn't heard before.
- Begin the string with exactly the words "Here's some food for thought." followed by a space, then straight into the content. Do NOT add a "Food for Thought" heading or label before or after — just start with those words. Never start with "Across these stories" or any callback to the stories above.
- It can be a surprising fact, a counterintuitive idea, a workflow tip, a thought experiment, a bit of history, or something genuinely funny — as long as it earns the listener's attention.
- Write in first person. Aim for 3–5 sentences. No filler, no generic observations.
{fot_history}
Length and pacing:
- The full assembled episode (including the fixed intro and outro) should run about {round(target_total_words / 130)} minutes when read aloud at a natural pace — roughly {target_total_words} words total.
- The intro and outro together account for about 70 words, so aim for your generated content (story_narratives + cn_relevance + food_for_thought combined) to total around {target_total_words - 70} words.
- Prioritize quality and natural flow over hitting an exact count. If a story needs a bit more room to land properly, take it.

Self-validation (check BEFORE returning JSON):
- OPENING CHECK (do this first): Read the first sentence of each story narrative. Does any of them contain a publication name, company name, or source attribution? If yes, rewrite that narrative's opening — move the attribution to mid-sentence or later, and lead with the substance instead. This check must pass before you run any other validation.
- Verify story_narratives has exactly {len(selected)} entries — one per story, same order as provided.
- Verify food_for_thought starts with exactly "Here's some food for thought." (including the period and trailing space before the content).
- Verify no raw domain names appear anywhere (e.g. "nytimes.com") — only proper publication names.
- Verify none of these banned phrases appear: "subscribe", "newsletter", "sign up", "continue reading", "in your inbox", "read more", "click here", "this story originally appeared", "Source:", "What happened:", "Why this matters:".
- Verify no 4+ word phrase is repeated within 30 words of itself.
- Verify the total word count of story_narratives + cn_relevance + food_for_thought is roughly {target_total_words - 70} words (between {round((target_total_words - 70) * 0.9)} and {round((target_total_words - 70) * 1.1)}).
- DELIVERY CUE CHECKS (mandatory — rewrite any narrative that fails):
  * Each story narrative must contain at least 2 em dashes (—). Count them.
  * Each story narrative must contain at least 1 rhetorical question (sentence ending with ?).
  * Each story narrative must contain at least 1 sentence of 5 words or fewer.
  * The full output (all narratives combined) must contain at least 1 instance of *italicized emphasis*.
  * If any narrative fails these checks, rewrite it to include the missing elements before returning.
- If any check fails, fix it before returning.

Selected stories (full article text provided for each).
Each story includes a suggested_opening_approach — use it as a starting point for how to open that narrative, but adapt naturally:
{story_blob}
""".strip()

    messages = [
        {"role": "system", "content": (
            "You are a natural, confident podcast host who tells stories the way you'd share "
            "something fascinating with a colleague over coffee. You never sound like you're "
            "reading a news brief or summarizing an article — you sound like you genuinely "
            "understand the material and can't wait to explain why it matters.\n\n"
            "CARDINAL RULE — enforced before all others: Never open a story narrative with "
            "a publication name, company name, or source attribution. The first sentence of "
            "every narrative must lead with a finding, tension, question, implication, or "
            "scene. Attribution belongs mid-sentence or later. A story that opens with "
            "'MIT Technology Review argues...' or 'CNBC reports...' or 'According to "
            "Bloomberg...' is categorically wrong — rewrite it before returning.\n\n"
            "You must output strict JSON only."
        )},
        {"role": "user", "content": prompt},
    ]

    logger.info("Generating script parts for %d stories via %s…", len(selected), model)
    try:
        content = chat_completion(
            api_key=api_key,
            model=model,
            messages=messages,
            project_id=project_id,
            organization=organization,
            temperature=0.5,
        )
        data = parse_json_response(content)
        narratives = data.get("story_narratives", [])
        cn_relevance = data.get("cn_relevance")
        food = data.get("food_for_thought", "")

        if not isinstance(narratives, list) or len(narratives) != len(selected):
            raise OpenAIError(
                f"story_narratives length mismatch: expected {len(selected)}, got {len(narratives)}"
            )
        if not all(isinstance(x, str) and x.strip() for x in narratives):
            raise OpenAIError("story_narratives must contain non-empty strings")
        if cn_relevance is not None and not isinstance(cn_relevance, str):
            raise OpenAIError("cn_relevance must be string or null")
        if not isinstance(food, str) or not food.strip():
            raise OpenAIError("food_for_thought must be non-empty string")

        # Clean FoT immediately — don't trust GPT's formatting
        food = _clean_food_for_thought(food)

        narratives = [n.strip() for n in narratives]

        # ── Programmatic delivery-cue enforcement ──────────────────────
        # ChatGPT's self-validation is unreliable, so we check in Python
        # and send a targeted fix-up request if cues are missing.
        cue_issues = _validate_delivery_cues(narratives)
        if cue_issues:
            logger.warning(
                "Delivery cue issues found (%d). Requesting fix-up…",
                len(cue_issues),
            )
            fix_prompt = (
                "The following story narratives are missing required delivery cues "
                "for text-to-speech expressiveness. Fix ONLY the issues listed — "
                "do not change anything else. Return the same JSON structure.\n\n"
                "Issues:\n" + "\n".join(f"- {iss}" for iss in cue_issues) + "\n\n"
                "Requirements:\n"
                "- Each story narrative MUST have at least 2 em dashes (—) for mid-sentence pauses\n"
                "- Each story narrative MUST have at least 1 rhetorical question ending with ?\n"
                "- Each story narrative MUST have at least 1 sentence of 5 words or fewer\n"
                "- At least 1 narrative must use *italicized emphasis* on a key word\n\n"
                "Current narratives:\n"
                + "\n\n".join(f"Story {i+1}:\n{n}" for i, n in enumerate(narratives))
                + "\n\nReturn JSON with key story_narratives (array of strings, same order)."
            )
            try:
                fix_content = chat_completion(
                    api_key=api_key,
                    model=model,
                    messages=[
                        {"role": "system", "content": "Output strict JSON only."},
                        {"role": "user", "content": fix_prompt},
                    ],
                    project_id=project_id,
                    organization=organization,
                    temperature=0.25,
                )
                fix_data = parse_json_response(fix_content)
                fixed = fix_data.get("story_narratives", [])
                if isinstance(fixed, list) and len(fixed) == len(narratives):
                    fixed = [f.strip() for f in fixed if isinstance(f, str)]
                    if len(fixed) == len(narratives):
                        remaining = _validate_delivery_cues(fixed)
                        if len(remaining) < len(cue_issues):
                            narratives = fixed
                            logger.info(
                                "Fix-up improved delivery cues: %d → %d issues.",
                                len(cue_issues), len(remaining),
                            )
                        else:
                            logger.warning("Fix-up didn't improve cues; keeping originals.")
                    else:
                        logger.warning("Fix-up returned wrong count; keeping originals.")
                else:
                    logger.warning("Fix-up response invalid; keeping originals.")
            except Exception as fix_exc:
                logger.warning("Delivery cue fix-up failed: %s — keeping originals.", fix_exc)

        # ── Opening-diversity enforcement ─────────────────────────────
        # Catch narratives that lead with the publication name and ask
        # the model to rewrite just the openings.
        opening_issues = _validate_opening_diversity(narratives)
        if opening_issues:
            logger.warning(
                "Opening diversity issues found (%d). Requesting fix-up…",
                len(opening_issues),
            )
            opening_fix_prompt = (
                "The following story narratives open with the publication name, which sounds "
                "repetitive and formulaic. Rewrite ONLY the opening of each flagged story so "
                "it leads with the insight, tension, question, or implication — not the source "
                "name. Move the attribution to mid-sentence or later. Keep everything else "
                "identical. Do NOT change unflagged stories.\n\n"
                "Flagged issues:\n" + "\n".join(f"- {iss}" for iss in opening_issues) + "\n\n"
                "Current narratives:\n"
                + "\n\n".join(f"Story {i+1}:\n{n}" for i, n in enumerate(narratives))
                + "\n\nReturn JSON with key story_narratives (array of strings, same order)."
            )
            try:
                fix_content = chat_completion(
                    api_key=api_key,
                    model=model,
                    messages=[
                        {"role": "system", "content": "Output strict JSON only."},
                        {"role": "user", "content": opening_fix_prompt},
                    ],
                    project_id=project_id,
                    organization=organization,
                    temperature=0.25,
                )
                fix_data = parse_json_response(fix_content)
                fixed = fix_data.get("story_narratives", [])
                if isinstance(fixed, list) and len(fixed) == len(narratives):
                    fixed = [f.strip() for f in fixed if isinstance(f, str)]
                    if len(fixed) == len(narratives):
                        remaining = _validate_opening_diversity(fixed)
                        if len(remaining) < len(opening_issues):
                            narratives = fixed
                            logger.info(
                                "Fix-up improved opening diversity: %d → %d issues.",
                                len(opening_issues), len(remaining),
                            )
                        else:
                            logger.warning("Opening fix-up didn't improve; keeping originals.")
                    else:
                        logger.warning("Opening fix-up returned wrong count; keeping originals.")
                else:
                    logger.warning("Opening fix-up response invalid; keeping originals.")
            except Exception as fix_exc:
                logger.warning("Opening diversity fix-up failed: %s — keeping originals.", fix_exc)

        parts = ScriptParts(
            story_narratives=narratives,
            cn_relevance=cn_relevance.strip() if isinstance(cn_relevance, str) and cn_relevance.strip() else None,
            food_for_thought=food.strip(),
        )
        logger.info("Script parts generated successfully.")
        return parts

    except OpenAIError as exc:
        logger.error("Script generation failed: %s — using fallback.", exc)
        return _fallback_parts(selected)


def _clean_food_for_thought(text: str) -> str:
    """Aggressively clean food_for_thought text to ensure it starts with the
    canonical opener and has no stray headings, regardless of how GPT formats it.

    This is called immediately after receiving the value from ChatGPT AND
    again in build_script_markdown as a safety net.
    """
    # Step 1: Flatten to single string, collapse all whitespace/newlines
    # This kills any heading-on-its-own-line pattern regardless of format
    flat = " ".join(text.split())

    # Step 2: Remove any occurrence of "Food for Thought" as a standalone phrase
    # that GPT injects as a heading (with or without punctuation after it)
    flat = re.sub(r'\bFood\s+for\s+Thought[:\-—.]?\s*', '', flat, flags=re.IGNORECASE)

    # Step 3: Now find the actual content start.
    # The canonical opener is "Here's some food for thought."
    # GPT might write "Here's some ..." (with "Food for Thought" now removed)
    # or it might start directly with content.
    flat = flat.strip()

    # Step 4: Check if it starts with "Here's some food for thought" (it won't,
    # because we removed "Food for Thought" above). Rebuild the opener.
    # Look for a leftover "Here's some" fragment
    leftover = re.match(r"^Here'?s\s+some\s*", flat, re.IGNORECASE)
    if leftover:
        # Remove the fragment and prepend the clean canonical opener
        content = flat[leftover.end():].strip()
        # Remove leading punctuation that was between "some" and content
        content = re.sub(r'^[.,:;\-—]+\s*', '', content)
    else:
        content = flat

    # Step 5: Ensure first letter of content is capitalized
    if content and content[0].islower():
        content = content[0].upper() + content[1:]

    return f"Here's some food for thought. {content}"


def build_script_markdown(parts: ScriptParts, selected: list[ScoredStory]) -> str:
    lines: list[str] = [INTRO_TEXT, ""]
    for idx, (story, narrative) in enumerate(zip(selected, parts.story_narratives), start=1):
        lead = _story_lead(idx, len(selected))
        body = _lc_first(narrative.strip())
        lines.append(f"{lead} {body}")
        lines.append("")

    if parts.cn_relevance:
        lines.append(parts.cn_relevance.strip())
        lines.append("")

    fot = _clean_food_for_thought(parts.food_for_thought.strip())
    lines.append(fot)
    lines.append("")
    lines.append(OUTRO_TEXT)
    return "\n".join(lines).strip() + "\n"


def build_script_json(parts: ScriptParts, selected: list[ScoredStory], script_markdown: str) -> dict[str, Any]:
    stories = []
    for idx, (story, narrative) in enumerate(zip(selected, parts.story_narratives), start=1):
        stories.append(
            {
                "index": idx,
                "title": story.candidate.title,
                "source_domain": story.candidate.source_domain,
                "source_url": story.candidate.url,
                "published_at": story.candidate.published_at.isoformat() if story.candidate.published_at else None,
                "narrative": narrative.strip(),
            }
        )

    return {
        "intro": INTRO_TEXT,
        "stories": stories,
        "cn_relevance": parts.cn_relevance,
        "ending_segment": ENDING_TOKEN,
        "food_for_thought": parts.food_for_thought.strip(),
        "word_count": count_words(script_markdown),
        "script_markdown": script_markdown,
    }


def rewrite_script_to_target(
    api_key: str,
    model: str,
    script_markdown: str,
    min_words: int,
    max_words: int,
    project_id: str | None = None,
    organization: str | None = None,
) -> str:
    prompt = f"""
Rewrite this podcast script so the generated content (everything except the fixed intro and outro) totals roughly {min_words}–{max_words} words.

Rules:
- Keep every fact accurate and unchanged.
- Keep the exact intro sentence unchanged.
- The food for thought segment must begin with exactly "Here's some food for thought." — no heading or label before it, never "Across these stories" or any callback to the stories. Do not add a "Food for Thought" heading anywhere in the script.
- Keep the exact closing outro paragraph unchanged:
  {OUTRO_TEXT}
- No bullet points, no story labels like "Story 1:".
- Use contractions naturally — "it's", "you'll", "I've", "couldn't", "didn't". Avoid stiff constructions like "it is" or "I could not".
- Never reproduce article text verbatim. Strip any redundant or boilerplate phrasing ("In a world where…", "It's more important than ever…", "As we navigate…").
- Perspective: story narratives are always in third person about the article and its subject — "the author argues", "she describes", "the report found". First person ("I", "I've") is only for the narrator's own reactions and commentary, the intro, food for thought, and the outro. Never let the narrator speak in the voice of the article author.
- CRITICAL: The first sentence of every story narrative must NOT contain any publication name, company name, or source attribution. Lead with the substance — the finding, tension, question, or implication. Attribution goes mid-sentence or later, never in the opening clause.
  Bad: "MIT Technology Review argues that enterprise AI depends on..." / "CNBC reports that Anthropic is..."
  Good: "Enterprise AI success might depend less on the model and more on everything wrapped around it — that's the case MIT Technology Review makes this week."
- Never lead a story with or echo the article headline.
- Never use raw domain names when attributing sources (e.g. never "theglobeandmail.com") — always use the proper publication name (e.g. "The Globe and Mail").
- Never repeat the same information twice in consecutive sentences.
- If trimming: cut repetition and over-explanation first; keep the interesting parts and the practical "so what".
- If expanding: add concrete context, a real-world example, or an extra implication for large-enterprise communications teams — don't pad with filler.
- Preserve and STRENGTHEN delivery cues — these are mandatory for text-to-speech expressiveness:
  * Em dashes (—) for mid-sentence pivots and pauses — at least 2–3 per story narrative.
  * Rhetorical questions for natural vocal inflection — at least 1 per story narrative.
  * Short impact sentences (5 words or fewer) after longer buildups.
  * *Italicized emphasis* for vocal stress on key words — at least 1–2 per story narrative.
  * If the rewrite reduces any of these, add them back. If it feels flat, add more.

Self-validation before returning:
- OPENING CHECK (do this first): Read the first sentence of each story section. If any contains a publication name or source attribution, rewrite that opening — lead with the substance and move attribution to mid-sentence or later.
- Verify the script starts with the exact intro text (unchanged).
- Verify food for thought starts with exactly "Here's some food for thought." — no heading before it.
- Verify no raw domain names (e.g. "nytimes.com") — only publication names.
- Verify none of these appear: "subscribe", "newsletter", "sign up", "continue reading", "in your inbox", "read more", "click here", "this story originally appeared", "Source:", "What happened:", "Why this matters:".
- Verify no 4+ word phrase repeats within 30 words of itself.
- DELIVERY CUE CHECKS (mandatory — rewrite any section that fails):
  * Each story section must contain at least 2 em dashes (—).
  * Each story section must contain at least 1 rhetorical question (?).
  * Each story section must contain at least 1 sentence of 5 words or fewer.
  * The full script must contain at least 1 instance of *italicized emphasis*.
- If any check fails, fix it before returning.

Return JSON with a single key `script_markdown`.

Script:
{script_markdown}
""".strip()

    messages = [
        {"role": "system", "content": "Output strict JSON only."},
        {"role": "user", "content": prompt},
    ]

    logger.info("Rewriting script to target %d-%d words…", min_words, max_words)
    content = chat_completion(
        api_key=api_key,
        model=model,
        messages=messages,
        project_id=project_id,
        organization=organization,
        temperature=0.2,
    )
    data = parse_json_response(content)
    rewritten = data.get("script_markdown", "")
    if not isinstance(rewritten, str) or not rewritten.strip():
        raise OpenAIError("rewrite response missing script_markdown")
    return rewritten.strip() + "\n"
