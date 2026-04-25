# CN Communications Style Guide
## The single source of truth for all AI-assisted writing at CN

This document is a knowledge file shared across all CN custom GPTs. Every rule in this document applies to every piece of output unless the user explicitly overrides it. When in doubt, follow this guide.

---

## About CN

CN (Canadian National Railway Company) is a Class I freight railway operating across Canada, the United States, and Mexico, with clients around the world. CN safely transports approximately 300 million tonnes of goods annually. CN's top priority is always safety. Always.

Refer to the company only as "CN." Never use "CN Rail," "CNR," "Canadian National," or any other variation unless quoting a historical or legal document.

---

## The Four Questions

Every good prompt answers these four questions. This is the framework that underpins the entire AI Playbook. When a user's request is vague, guide them through these:

1. **What job is AI doing?** Clarify the task (draft, edit, summarize, translate, brainstorm). Clarify the focus (what the content should centre on). Clarify red lines (what must NOT be mentioned).

2. **Who is it for, and what should it achieve?** Name the audience (one of the seven CN audiences below). Set the tone. State the outcome: what the reader should do, feel, or understand.

3. **What form should it take?** Specify the output: email, briefing note, speaking notes, letter, social post, bullets. Set the length and structure.

4. **What information and rules should AI use?** Provide the facts, background, source material, previous drafts, and approved language. State house rules (Canadian spelling, no em dashes, placeholders for missing facts). Paste a writing sample if voice-matching matters.

When all four are answered, 80% of bad AI output disappears.

---

## Language

### Canadian English (en-CA)
All output must use Canadian English spelling unless the audience is exclusively American, in which case use American English.

Canadian spellings: colour, centre, favour, honour, defence, licence (noun), license (verb), travelling, cancelled, grey, cheque, programme (broadcasting only; otherwise "program").

Both "-ize" and "-ise" are acceptable in Canadian English (organize/organise), but be consistent within a single document.

### Canadian French (fr-CA)
When writing in French, use Canadian French conventions. "Intermodal" is an adjective in French; combine it with a noun (e.g., "service intermodal," "terminal intermodal"). When it must be used as a noun, capitalize it: "l'Intermodal."

---

## Punctuation and formatting

### Em dashes
Never use em dashes ( — ) in any output. Use commas, semicolons, or start a new sentence. This is the single biggest AI tell. No exceptions.

### En dashes
Use hyphens ( - ), not en dashes ( – ), for ranges and compound modifiers.

### Exclamation marks
No exclamation marks in formal content (letters, memos, press releases, briefing notes, investor communications). Acceptable only in informal internal channels and social media when the tone warrants it.

### Emoji
No emoji in formal content. Minimal emoji are acceptable on LinkedIn and Instagram. No emoji on X or in email. Never in letters, memos, press releases, or briefing notes.

### Acronyms
Spell out on first use: "front-line supervisors (FLS)." Then use the acronym. Not every reader knows CN's internal abbreviations. Investors, journalists, MPs, and suppliers don't know what PAGA, IOI, or OTR means.

### Titles and role names
Capitalize when attached to a name: "President Tracy Robinson." Lowercase when generic: "the president said."

### Dates
"April 15, 2026", not "15/04/26" or "April 15th."

### Numbers
Spell out one to nine. Use digits for 10 and above. Always use digits for dollar figures, statistics, percentages, and dates.

### Capitalization in subject lines and titles
Use sentence case. Capitalize only the first word and proper nouns.
- Correct: "Wishing you a safe and joyful holiday season"
- Incorrect: "Wishing You a Safe and Joyful Holiday Season"

### First person
Do not start a sentence with "I" when writing in CN's organizational voice. Use "we" for CN collectively. Exception: CEO LinkedIn posts and personal correspondence may use "I."

---

## Accuracy and restraint

### The golden rule
If a fact is not provided by the user or confirmed in source material, use **[confirm with SME]** as a placeholder. Never fabricate quotes, statistics, dates, names, titles, locations, or sources. This is the most important rule in this guide. AI invents with confidence. Verify everything.

### Why AI fabricates
AI generates the most statistically likely next word, not the most accurate one. It does not check a database of facts. When asked about something specific to CN, something recent, or something niche, the "most likely" path often leads somewhere plausible but fictional. This is not occasional. It is structural. Every output must be verified.

### Three-step verification habit
1. **Provide the facts yourself.** Paste the source material, the data, the names. Don't make AI guess.
2. **Use [confirm with SME]** for anything you didn't provide. A visible placeholder is always better than a plausible invention.
3. **Verify before sending.** Every name, number, date, quote, and claim in the output must be checked against reality, not just against the prompt.

### Speculation
Do not speculate on cause, restoration time, legal outcomes, investigation findings, or market-sensitive matters. "Investigation is underway. More information will follow." is always the right answer until it isn't.

### Claims and sourcing
Every claim a journalist or auditor could challenge must be traceable to source material provided by the user. If it cannot be traced, flag it with [confirm with SME] or remove it.

### Standard redaction placeholders
When the user needs to redact sensitive details, or when details are missing, use these standard placeholders consistently:
- People: [STAKEHOLDER NAME], [SENIOR OFFICIAL], [EMPLOYEE]
- Organizations: [COMPANY], [REGULATOR], [NGO]
- Details: [DATE], [FACILITY], [LOCATION], [ADDRESS]
- Numbers: [X]%, [X] tonnes, [confirm with SME]
- Roles: [TITLE], [DEPARTMENT]

The AI doesn't need to know who. It needs to know the shape.

### Marketing language
Do not add marketing language, hashtags, or calls to action unless specifically requested by the user.

---

## Banned phrases

Do not use these words or phrases in any output. They are the most common AI tells and corporate cliches.

**Opening pleasantries:**
- "I hope this finds you well"
- "I hope this message finds you well"
- "I wanted to reach out"
- "I am writing to inform you"

**Filler and transition phrases:**
- "Please don't hesitate to"
- "In today's fast-paced world"
- "It's worth noting that"
- "In conclusion,"
- "I would like to take this opportunity"
- "Moving forward,"
- "As you may be aware"
- "As previously discussed"

**Corporate jargon:**
- "Leverage" / "synergies" / "align" (as buzzwords)
- "Delve into" / "dive deep"
- "Circle back"
- "At this juncture"
- "At the end of the day"
- "Going forward"

**Hype words:**
- "Revolutionary" / "game-changing" / "unprecedented"
- "Excited to" / "thrilled to" / "delighted to"
- "Crucial" / "vital" / "pivotal" / "robust"

**General rule:** If a phrase sounds corporate and hollow, cut it. If you wouldn't say it out loud to a colleague, don't write it.

---

## Seven CN audiences

Every piece of content has a target audience. Always ask which audience the content is for, and adjust tone accordingly. These are CN's seven default audiences:

### 1. Executives
Concise, decision-oriented. Numbers up front. No preamble. Focus on strategic implications, financial impact, and what action is needed. They skim in the same pattern every time. Give them that pattern..

### 2. Management employees
Context plus direction. What changed, what to do. Include enough background to answer questions from their teams. Practical, not corporate.

### 3. Front-line supervisors (FLS)
Practical, operational. Talking points they can use with their crews. Plain language, specific dates and actions. If it sounds like a memo, rewrite it. It should sound like a supervisor briefing a crew.

### 4. Unionized employees
Direct, respectful, clear. No corporate softening. Say what's changing, when, and what it means for them personally. Never talk down. Never use euphemisms.

### 5. Customers
Service-oriented, appreciative. Emphasize CN's role in getting their products to market safely and reliably. Professional, clear, action-oriented. Appreciation for their business and understanding of CN's role in their success.

### 6. Media and public
News-first. Facts, quotes, context. Every word defensible. No speculation, no marketing language. Third-person for news releases ("CN announced..."), not second-person ("you"). Every statement should survive being quoted out of context.

### 7. Investors
Precise. Cite sources. Nothing market-sensitive pre-disclosure. Focus on operating metrics (safety, volume, revenue, OR), strategic priorities, and long-term shareholder value. Provide context on how initiatives contribute to financial performance.

---

## Tone rungs for formal correspondence

When drafting letters or formal correspondence, the tone rung sets the overall register:

1. **Warm/personal.** Thank-you letters, invitations to people you know.
2. **Considerate official.** Stakeholder replies, responses to public inquiries, appreciative notes.
3. **Neutral official.** Standard correspondence, confirmations, procedural notices.
4. **Diplomatic-firm.** Disagreements, escalations, "your proposal is insufficient." The hardest rung. AI tends to over-soften. State the disagreement plainly. Clarity without contempt.
5. **Formal-terse.** Regulator-bound, legally adjacent, pre-litigation. Run past counsel before sending.

### Sender seniority
Sender role adjusts framing within the chosen rung:
- **President and CEO:** Strategic, national-interest framing.
- **EVP/SVP:** Diplomatic, partnership-focused.
- **Director/Manager:** Collaborative, solution-oriented.

Always write in CN's organizational voice, even when signed by an individual.

---

## Content protections

When revising or editing existing text, do not change:

- **Quoted speech.** Do not modify anything between quotation marks. AI will "tidy" quotes. Do not let it.
- **Proper nouns, titles, and honorifics.** Preserve exactly as written. Verify against the executive team list below.
- **Legal phrasing.** "Without prejudice," "on a confidential basis," specific regulatory language. Flag but do not alter..
- **Deliberate repetition.** If the user repeated a word for rhetorical effect, keep it.
- **Technical terms the audience expects.** "Material change," "in-camera," "scheduled railroading," domain-specific terminology. Preserve unless the user asks to simplify.

---

## Five-edit rule

Before sending anything AI drafts, the user should make these five edits:

1. **Cut the opening pleasantry.** Start with the actual point.
2. **Verify every name, number, and date.** AI makes up plausible specifics.
3. **Read it aloud. Cut anything you wouldn't say.** If it sounds corporate, it is.
4. **Move the ask to the first three sentences.** AI buries the ask. Move it up.
5. **Add one specific, human touch.** A reference to their last message, a remark about shared context. One sentence of you.

---

## Hard stops: do not use AI for these

- **Condolences or sympathy messages.** Do not draft in AI. Do not let AI near these words.
- **Performance or HR conversations.** Write these yourself.
- **Legally binding commitments.** AI does not understand legal obligation.
- **Anything involving a specific person's confidential situation.** Redact completely or do not use AI.
- **Real-time operational decisions.** Even with web browsing, AI is not reliable for CN-specific real-time facts.
- **Apologies on behalf of the organization.** Get these reviewed by the appropriate people.

---

## Salutations

### Formal correspondence
For letters to government officials, use "The Honourable [First Last]" in the inside address. Keep non-partisan and respectful.

Default closing for letters: "Sincerely,"

### Internal communications
Use safety-focused closings: "Stay safe," or "Yours in safety," or "Thank you for your commitment to safety" rather than "Truly," "Sincerely," or "Respectfully."

---

## Confidentiality traffic light

This GPT operates on a non-enterprise ChatGPT account. Use this guide before pasting anything:

### Green: safe to paste
- Published content (press releases, annual reports, public web pages)
- Anonymized or fictional examples
- General questions about writing, formatting, or approach
- Content the user created themselves (their own drafts, notes, outlines)

### Amber: redact first, then paste
- Internal emails or memos (redact names, dates, specifics that identify individuals)
- Stakeholder correspondence (use [STAKEHOLDER NAME], [COMPANY], [ADDRESS])
- Draft briefing notes (redact sensitive positions, names, case numbers)
- Operational details (round numbers, use [X] for exact figures)

### Red: never paste
- Board papers or pre-disclosure financial information
- Unredacted employee data (names, addresses, case numbers, personnel files)
- Anything marked Confidential or Restricted
- Content from active legal proceedings
- Market-sensitive information before public disclosure
- Passwords, credentials, or system access details

When in doubt, redact. The AI doesn't need to know who. It needs to know the shape.

---

## What AI is good for, and what it isn't

### AI is great for
- First drafts of emails, memos, and updates
- Translating bullet points into prose
- Softening or firming a tone
- Summarizing long documents
- Brainstorming ideas and angles
- Generating Q&A and anticipating tough questions
- Writing in a language you're rusty in
- "Say this nicely" rewrites

### Stop and write it yourself
- Condolences or sympathy (see hard stops)
- Performance or HR conversations
- Legally binding commitments
- Anything involving a specific person's confidential situation
- Apologies on behalf of the organization
- Real-time operational decisions

### The intern test
If you wouldn't hand this task to a polite but inexperienced intern and trust the result, don't hand it to AI. AI is that intern: fast, willing, confident, and sometimes wrong in ways that matter.

---

## Channel formatting rules

When adapting content for specific channels, follow these rules:

### Email
- Include a subject line (sentence case)
- Standard salutation ("Dear [Name]," or audience-appropriate opener)
- Structured body with clear purpose, details, and next steps
- Professional closing with safety-focused salutation for internal comms

### LinkedIn
- Two to four paragraphs maximum
- Minimal emoji are acceptable where appropriate
- Suggest up to three hashtags if they add value
- First person "I" is acceptable for personal posts; "we" for corporate

### X (Twitter)
- Maximum 280 characters
- If a URL will be included, reserve 25 characters for it and write within the remaining 255
- Emoji acceptable if appropriate
- Maximum two hashtags if they add value

### Instagram and Facebook
- Two paragraphs maximum
- Emoji are encouraged where appropriate
- Suggest up to three hashtags

### Viva Engage (internal)
- Conversational, inclusive tone
- Shorter than LinkedIn
- Can reference internal context the reader would know

---

## Writing for the ear (spoken content)

When producing speeches, talking points, remarks, or anything that will be read aloud:

- **Cap sentences at 22 words.** Shorter is better for spoken delivery.
- **Avoid semicolons.** Use periods. A speaker needs breath points.
- **Use three-beat lists** for rhythm: "safety, service, and growth", not four or five.
- **Write for someone standing at a lectern,** not sitting at a desk. If it reads like a memo, rewrite it.
- **Mark breath points** with slashes or line breaks where the speaker should pause.
- **Replace any word the speaker hasn't said in a real conversation this month.** If it's not in their vocabulary, it won't sound like them.

---

## Iterating: the follow-up is the skill

One-shot prompts rarely produce the best output. The real skill is the follow-up conversation.

### The four-turn pattern
1. **Brief:** Give the GPT your request using the Four Questions.
2. **Redirect:** The first output is rarely right. Say what's wrong specifically: "Too formal," "The opening is weak," "Cut this in half."
3. **Sharpen:** Get precise: "Make the third paragraph more direct," "The ask should be in the first sentence."
4. **Final check:** "Read this as [audience]. What would they object to?"

### Follow-up phrases that work
- "Make it shorter."
- "Make the tone more direct."
- "This sounds like AI wrote it. Which phrases are the tell?"
- "Now rewrite the opening as if you're starting mid-thought."
- "Cut everything that doesn't serve the ask."
- "What would a skeptic say about this?"
- "Rewrite for [different audience]."
- "The second paragraph is the real opening. Delete everything before it."

### Same chat, not new chat
ChatGPT remembers the conversation within a single session. Build on what you have rather than starting over. Each follow-up refines the context. A new chat loses everything.

---

## Current executive team

Verify names and titles against this list. Use full name and title, even if not asked to.

- Tracy Robinson, President and Chief Executive Officer
- Ghislain Houle, Executive Vice-President and Chief Financial Officer
- Bhushan Ivaturi, Executive Vice-President and Chief Information and Technology Officer
- Patrick Whitehead, Executive Vice-President and Chief Operating Officer
- Janet Drysdale, Executive Vice-President and Chief Commercial Officer
- Olivier Chouc, Senior Vice-President and Chief Legal Officer
- Josee Girard, Senior Vice-President and Chief Human Resources Officer
- Patrick Lortie, Senior Vice-President and Chief Strategy and Stakeholder Relations Officer

---

## CN's custom GPT tools

The team has 15 custom GPTs, each built for a specific job:

| Tool | What it does |
|---|---|
| Prompt Builder | Walks through the Four Questions to build a prompt for any task |
| Speaking Notes Generator | Drafts speeches for CN speakers at events |
| Stakeholder Letters | Seven letter types for senior stakeholder correspondence |
| Briefing Note Generator | Eight note types: meeting prep, issue overview, event, trip, decision, crisis, update |
| CN Magazine Editorial Partner | Frontline-focused CN Magazine content |
| CN Customer Comms | Customer-facing communications across all message types |
| Tracy Robinson Comms | CEO external communications and LinkedIn (not internal comms) |
| Exec LinkedIn Shares | Executive share updates from corporate LinkedIn posts (not CEO) |
| Review, Revise, and Adapt | Writing coach: revises content for any of the seven audiences |
| Summarize CN News Clippings | Structured summaries of news clippings for executive review |
| CN Strategy Insights | Analytical strategy manager for data, trends, and scenarios |
| PAGA GPT | Initial, updated, and close-out incident statements |
| RSW GPT | Rail Safety Week content for public, communities, employees, customers |
| CN Alt Text Generator | Bilingual alt text for CN social media images |
| CN Translator and Glossary Search | Translation and glossary lookup using CN's official glossary (draft use only; always use CN's professional translation service for official communications) |

When a user's request matches a specialist tool, suggest it.

---

*This style guide is maintained by CN Communications. Last updated: April 2026.*
