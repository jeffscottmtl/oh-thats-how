# AI Playbook — Single-File Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build "The AI Playbook" as a single, self-contained HTML file with tabbed navigation — shared via Teams, opened in a browser, no server required.

**Architecture:** One HTML file with inline CSS and JS. Five tabs (Start Here, Guides, Learn, Your Tools, Poster). Each tab swaps visible content. Guide/literacy content is embedded as hidden sections and shown on selection. All images base64-encoded. All fonts loaded from Google Fonts CDN (the only external dependency).

**Tech Stack:** HTML5, CSS3 (custom properties, grid, flexbox), vanilla JavaScript. No build tools, no frameworks, no npm.

**Source reference:** The existing design system lives in `/Users/jeffscott/Downloads/Oh, That's How/Claude.ai tool design references/index.html` (573 lines). This is the canonical design — colors, typography, spacing, components. The existing guide HTML files in `guides/` and `literacy/` contain the body content to migrate.

---

## File Structure

- **Create:** `/Users/jeffscott/Downloads/Oh, That's How/the-ai-playbook.html` — the single deliverable file
- **Reference (read-only):**
  - `Claude.ai tool design references/index.html` — design system, hero, grid layout
  - `Claude.ai tool design references/guides/*.html` — 13 guide content sources (remove interview-prep)
  - `Claude.ai tool design references/literacy/*.html` — 7 literacy content sources
  - `Claude.ai tool design references/confidentiality.html` — confidentiality page content
  - `Claude.ai tool design references/poster.html` — poster content
  - `Claude.ai tool design references/shared/styles.css` — shared component CSS
  - `Claude.ai tool design references/shared/guide.css` — guide-specific CSS
  - `Claude.ai tool design references/SSR self-service AI info-handoff/ssr-self-service-ai-info/project/guides/*.html` — base64-embedded versions (for screenshots)
  - `Custom GPTs as of Apr 22 2026.docx` — GPT names and descriptions for "Your Tools" tab

---

## Content Inventory

### Guides (13 — removed interview-prep and press-release per user decision)
1. Email (feature guide)
2. Proofread
3. Speechwriting
4. Letters
5. Presentations
6. Media Q&A
7. Crisis
8. Summarize
9. Stakeholder map
10. Tone shift
11. Internal memo
12. Meeting brief
13. Social posts

### Literacy (7 + confidentiality = 8)
1. Four Questions — in depth
2. Hallucinations
3. What NOT to paste (confidentiality)
4. When NOT to use AI
5. Iterating
6. Which tool for which job (models)
7. Custom GPTs
8. CN house rules

### Your Tools (GPT inventory — 15 GPTs)
Map each GPT to the task it handles, with a link to chat.com.

### Poster
Printable one-page cheat sheet section with print-specific CSS.

---

## Design Decisions

1. **Tabs, not pages.** Five tabs in the topbar: Start Here | Guides | Learn | Your Tools | Poster. Only one tab's content is visible at a time. Tab state managed via JS class toggling.

2. **Guide content is inline.** Each guide's full content is embedded in a `<section>` with `display:none` by default. Clicking a guide card in the grid shows that section and hides the grid. A back button returns to the grid.

3. **No prompt builder tool.** The Prompt Builder GPT link goes to chat.com. The "Your Tools" tab handles all GPT references.

4. **Existing design system preserved.** Same CSS custom properties, same fonts, same component classes. No redesign — this is a structural change, not a visual one.

5. **Content is explanatory.** Guides teach the thinking behind each task type. They reference the relevant GPT by name but don't build prompts inline.

6. **Self-contained.** All CSS inline in `<style>` tags. All JS inline in `<script>` tags. Base64 screenshots embedded where needed. Only external dependency: Google Fonts CDN.

7. **Print support.** Poster tab has `@media print` CSS that hides everything except the poster content when printed.

---

### Task 1: Scaffold the HTML shell with tab navigation

**Files:**
- Create: `/Users/jeffscott/Downloads/Oh, That's How/the-ai-playbook.html`
- Reference: `Claude.ai tool design references/index.html` (lines 1-41 for CSS variables, lines 63-109 for topbar/button styles)

- [ ] **Step 1: Create the HTML file with head, fonts, and CSS variables**

Create the file with the doctype, meta tags, Google Fonts link, and the full CSS custom properties block from the existing design system. Include the shared component styles (topbar, buttons, cards, callouts, prompts, etc.) from the reference `index.html` lines 10-162.

- [ ] **Step 2: Add the topbar with tab buttons**

Replace the existing `<nav>` links with tab buttons. The topbar structure:
```html
<div class="topbar">
  <div class="brand">
    <span class="cn-mark"><span class="c">CN</span></span>
    <span>The AI Playbook</span>
  </div>
  <nav class="tabs">
    <button class="tab active" data-tab="start">Start Here</button>
    <button class="tab" data-tab="guides">Guides</button>
    <button class="tab" data-tab="learn">Learn</button>
    <button class="tab" data-tab="tools">Your Tools</button>
    <button class="tab" data-tab="poster">Poster</button>
  </nav>
</div>
```

Style tabs using the existing `.topbar nav` styles (mono font, 11px, uppercase, letter-spacing). Active tab gets `border-bottom-color: var(--cn-red)`.

- [ ] **Step 3: Add five empty tab content containers**

```html
<main>
  <div class="tab-content active" id="tab-start"><!-- Start Here --></div>
  <div class="tab-content" id="tab-guides"><!-- Guides --></div>
  <div class="tab-content" id="tab-learn"><!-- Learn --></div>
  <div class="tab-content" id="tab-tools"><!-- Your Tools --></div>
  <div class="tab-content" id="tab-poster"><!-- Poster --></div>
</main>
```

CSS: `.tab-content { display: none; }` and `.tab-content.active { display: block; }`.

- [ ] **Step 4: Add tab-switching JavaScript**

```javascript
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    window.scrollTo(0, 0);
  });
});
```

- [ ] **Step 5: Add footer**

Reuse the existing footer from `index.html` line 553-556. Update version to v2.0.

- [ ] **Step 6: Verify the shell works**

Open `the-ai-playbook.html` in a browser. Confirm: topbar renders with CN mark and five tabs, clicking tabs swaps visible content, footer shows at bottom. Each tab should show empty space for now.

- [ ] **Step 7: Commit**

```bash
git add "the-ai-playbook.html"
git commit -m "feat: scaffold single-file AI Playbook with tab navigation"
```

---

### Task 2: Build the "Start Here" tab

**Files:**
- Modify: `/Users/jeffscott/Downloads/Oh, That's How/the-ai-playbook.html`
- Reference: `Claude.ai tool design references/index.html` (lines 282-356 for hero, Four Questions, audiences)

This tab contains: hero, Four Questions grid, Six Audiences grid. It's the confidence-building entry point.

- [ ] **Step 1: Add hero section**

Migrate the hero from `index.html` lines 282-295. Update the lede to remove the em dash (use a comma or period instead). Update the meta stats to reflect the current count: 13 Task guides, 8 Literacy notes. Remove "1 Prompt builder" — replace with the GPT count or remove.

- [ ] **Step 2: Add the Four Questions section**

Migrate from `index.html` lines 298-336. This is the `.fourq` grid with four `.fq` cards. Keep the content exactly as-is — it's well-written. Remove the "Read the full explainer" link (the explainer now lives in the Learn tab, accessible via tab navigation). Replace it with a note: "See the Learn tab for the full explainer."

- [ ] **Step 3: Add the Six Audiences section**

Migrate from `index.html` lines 339-356. The `.audiences` grid with six `.aud` cards. Content unchanged.

- [ ] **Step 4: Add a "quickbar" CTA strip at bottom of Start Here**

A dark strip encouraging the user to explore: "Ready to try it? Pick a guide from the Guides tab, or explore your custom GPTs in Your Tools."

- [ ] **Step 5: Verify Start Here tab**

Open in browser. Confirm: hero renders with correct headline, Four Questions grid shows 4 cards, audiences grid shows 6 cards, responsive at 1000px breakpoint.

- [ ] **Step 6: Commit**

```bash
git add "the-ai-playbook.html"
git commit -m "feat: add Start Here tab with hero, Four Questions, audiences"
```

---

### Task 3: Build the Guides tab — grid view

**Files:**
- Modify: `/Users/jeffscott/Downloads/Oh, That's How/the-ai-playbook.html`
- Reference: `Claude.ai tool design references/index.html` (lines 358-470 for guide grid and filter chips)

- [ ] **Step 1: Add the guide grid section header**

Migrate the section header from `index.html` lines 359-367. Use roman numeral removed — this is now a tab, not a scroll section.

- [ ] **Step 2: Add filter chips**

Migrate from `index.html` lines 369-377. Update category labels if needed. Remove "All 15" — change to "All 13" (interview-prep and press-release removed).

- [ ] **Step 3: Add guide cards**

Migrate all 13 guide cards from `index.html` lines 379-469. Remove interview-prep (guide 14) and renumber. Change `href` attributes to `onclick` handlers that show the guide content inline:

```html
<div class="guide feature" data-cat="writing editing" onclick="showGuide('email')">
```

Remove the `<a>` wrapper — use `<div>` with `cursor: pointer` since these are now in-page actions, not links.

- [ ] **Step 4: Add filter JavaScript**

Migrate the filter JS from `index.html` lines 558-569. Adjust selectors to target `#tab-guides .guide`.

- [ ] **Step 5: Add the guide detail view container**

Below the grid, add a hidden container for guide content:

```html
<div id="guide-detail" style="display:none;">
  <div class="guide-back" onclick="hideGuide()">
    <span class="label">&larr; Back to guides</span>
  </div>
  <div id="guide-detail-content"></div>
</div>
```

- [ ] **Step 6: Add show/hide guide JavaScript**

```javascript
function showGuide(id) {
  document.getElementById('guide-grid').style.display = 'none';
  document.getElementById('guide-detail').style.display = 'block';
  document.querySelectorAll('.guide-page').forEach(p => p.style.display = 'none');
  document.getElementById('guide-' + id).style.display = 'block';
  window.scrollTo(0, 0);
}
function hideGuide() {
  document.getElementById('guide-grid').style.display = '';
  document.getElementById('guide-detail').style.display = 'none';
}
```

- [ ] **Step 7: Verify guide grid**

Open in browser. Confirm: grid renders with 13 cards, filter chips work, clicking a card hides the grid and shows the detail container (empty for now), back button returns to grid.

- [ ] **Step 8: Commit**

```bash
git add "the-ai-playbook.html"
git commit -m "feat: add Guides tab with filterable grid and detail navigation"
```

---

### Task 4: Migrate guide content (13 guides)

**Files:**
- Modify: `/Users/jeffscott/Downloads/Oh, That's How/the-ai-playbook.html`
- Reference: Each guide HTML file in `Claude.ai tool design references/guides/` and `SSR.../project/guides/`

This is the largest task. For each of the 13 guides, extract the body content from the existing HTML file and embed it as a `<section class="guide-page" id="guide-{slug}">` inside the guide detail container.

- [ ] **Step 1: Read each guide HTML file and extract body content**

For each guide, the content lives between the guide hero and the next-prev footer. The structure is:
- `.guide-hero` (title, lede, meta tags)
- Multiple `.two-col` sections (sidebar label + main content)
- Various components: `.prompt`, `.ba`, `.dual`, `.steps`, `.check`, `.callout`

Extract everything from the guide hero through the last `.two-col` section. Skip the topbar (we have our own), skip the next-prev footer (not needed in single-file), skip the `<head>` and shared CSS (already included).

The existing guide files use shared CSS loaded via `<link>`. That CSS needs to be included in our file's `<style>` block (done in Task 1 from `shared/guide.css`).

- [ ] **Step 2: Add guide-page CSS**

Read `Claude.ai tool design references/shared/guide.css` and add its styles to the main `<style>` block. Also add the two-column layout styles from the guide files (`.two-col`, `.guide-hero`, `.guide-sidebar`, etc.).

- [ ] **Step 3: Embed each guide as a hidden section**

For each of the 13 guides, add:
```html
<section class="guide-page" id="guide-email" style="display:none;">
  <!-- migrated content from guides/email.html -->
</section>
```

Process all 13 guides:
1. email
2. proofread
3. speechwriting
4. letters
5. presentations
6. media-qa
7. crisis
8. summarize
9. stakeholder-map
10. tone-shift
11. internal-memo
12. meeting-brief
13. social

- [ ] **Step 4: Update internal links**

Any guide content that links to other guides (e.g., "see the email guide") should become `onclick="showGuide('email')"` instead of `href="guides/email.html"`. Any links to literacy pages should switch tabs: `onclick="switchToLearn('four-questions')"`.

- [ ] **Step 5: Update guide content to reference GPTs**

Where guides currently teach prompt-building, add a callout pointing to the relevant GPT:

```html
<div class="callout info">
  <span class="label">Your tool</span>
  <p>The <strong>Prompt builder</strong> GPT walks you through these four questions interactively. 
  <a href="https://chat.com/g/..." target="_blank">Open it in ChatGPT &rarr;</a></p>
</div>
```

Map guides to GPTs:
- Email → Prompt builder, Review revise and adapt
- Crisis → PAGA GPT
- Speechwriting → Speaking notes generator
- Letters → Stakeholder letters
- Meeting brief → Briefing note generator
- Social → Exec LinkedIn shares, Review revise and adapt
- Summarize → Summarize CN news clippings (if applicable)

- [ ] **Step 6: Add copy-button JavaScript**

Add the copy-to-clipboard handler for `.copy-btn` elements inside `.prompt` blocks:

```javascript
document.addEventListener('click', e => {
  if (e.target.classList.contains('copy-btn')) {
    const prompt = e.target.closest('.prompt');
    const text = prompt.textContent.replace(/Copy|Copied/, '').trim();
    navigator.clipboard.writeText(text);
    e.target.textContent = 'Copied';
    setTimeout(() => e.target.textContent = 'Copy', 2000);
  }
});
```

- [ ] **Step 7: Verify guide content renders**

Open in browser. Click through at least 3 guides (email, crisis, tone-shift). Confirm: two-column layout works, prompt blocks render with dark background, copy buttons work, callouts show in correct colors, back button returns to grid.

- [ ] **Step 8: Commit**

```bash
git add "the-ai-playbook.html"
git commit -m "feat: embed all 13 guide contents in Guides tab"
```

---

### Task 5: Build the Learn tab (literacy + confidentiality)

**Files:**
- Modify: `/Users/jeffscott/Downloads/Oh, That's How/the-ai-playbook.html`
- Reference: `Claude.ai tool design references/literacy/*.html`, `Claude.ai tool design references/confidentiality.html`

Same pattern as Guides tab: grid of cards → click to expand inline.

- [ ] **Step 1: Add Learn tab grid with 8 literacy cards**

Migrate the literacy grid from `index.html` lines 474-532. Remove the `href` attributes, replace with `onclick="showLearn('slug')"`. Update numbering: confidentiality is now literacy item 03.

- [ ] **Step 2: Add learn detail container**

Same pattern as guide detail: hidden container with back button, individual `.learn-page` sections.

- [ ] **Step 3: Embed all 8 literacy/confidentiality page contents**

Extract body content from each literacy HTML file and the confidentiality page. Embed as hidden sections. Same process as Task 4 but for 8 pages.

Pages:
1. four-questions
2. hallucinations
3. confidentiality (from confidentiality.html)
4. when-not-to
5. iterating
6. models
7. custom-gpts
8. house-rules

- [ ] **Step 4: Add show/hide learn JavaScript**

Same pattern as `showGuide`/`hideGuide` but for learn pages.

- [ ] **Step 5: Verify Learn tab**

Open in browser. Click through at least 2 literacy pages. Confirm content renders, back button works, traffic-light system in confidentiality page displays correctly.

- [ ] **Step 6: Commit**

```bash
git add "the-ai-playbook.html"
git commit -m "feat: add Learn tab with 8 literacy pages"
```

---

### Task 6: Build the "Your Tools" tab

**Files:**
- Modify: `/Users/jeffscott/Downloads/Oh, That's How/the-ai-playbook.html`
- Reference: `Custom GPTs as of Apr 22 2026.docx` (for GPT names and descriptions)

This tab maps GPTs to tasks and links to chat.com.

- [ ] **Step 1: Add section header**

```html
<div class="section-head">
  <div class="num"><em>V</em></div>
  <div>
    <div class="eyebrow">Your custom GPTs</div>
    <h2>Pick a tool. Start working.</h2>
    <p>These custom GPTs live in your CN ChatGPT account. Each one is built for a specific job. Open the one that matches your task.</p>
  </div>
</div>
```

- [ ] **Step 2: Add the GPT card grid**

Create a grid of GPT cards, organized by function. Each card shows:
- GPT name
- One-line description
- "When to use" hint
- Link to chat.com

Group into categories:
- **Drafting & writing:** Prompt builder, Speaking notes generator, Stakeholder letters, Briefing note generator, CN Magazine Editorial Partner, CN customer comms
- **CEO & executive comms:** Tracy Robinson comms, Exec LinkedIn shares
- **Review & adaptation:** Review revise and adapt, Summarize CN news clippings
- **Specialized:** PAGA GPT, RSW GPT, CN Alt Text Generator, CN translator and glossary, CN Strategy Insights

Card HTML:
```html
<div class="tool-card">
  <div class="label">Drafting</div>
  <h4>Prompt builder</h4>
  <p>Walks you through the Four Questions to build a ready-to-use prompt.</p>
  <a href="https://chat.com/g/..." target="_blank" class="btn ghost">Open in ChatGPT &rarr;</a>
</div>
```

- [ ] **Step 3: Add tool-card CSS**

Style `.tool-card` using the existing `.card` base with additions:
```css
.tool-card {
  background: var(--card);
  border: 1px solid var(--ink);
  border-radius: var(--r-md);
  padding: 24px;
}
.tool-card h4 {
  font-family: var(--serif);
  font-weight: 400;
  font-size: 22px;
  margin: 8px 0;
}
.tool-card p {
  font-size: 14px;
  color: var(--ink-2);
  margin: 0 0 16px;
}
```

Grid: `.tool-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; padding: 0 36px; }`

- [ ] **Step 4: Add a "How to access" callout**

Above the grid, add:
```html
<div class="callout info" style="margin: 0 36px 24px;">
  <span class="label">How to access</span>
  <p>Go to <a href="https://chat.com" target="_blank">chat.com</a> and sign in with your CN account. Your custom GPTs appear in the sidebar. Click one to start.</p>
</div>
```

- [ ] **Step 5: Verify Your Tools tab**

Open in browser. Confirm: section header renders, GPT cards display in 3-column grid, links open in new tab, callout displays correctly, responsive at 1000px.

- [ ] **Step 6: Commit**

```bash
git add "the-ai-playbook.html"
git commit -m "feat: add Your Tools tab with GPT inventory"
```

---

### Task 7: Build the Poster tab

**Files:**
- Modify: `/Users/jeffscott/Downloads/Oh, That's How/the-ai-playbook.html`
- Reference: `Claude.ai tool design references/poster.html`

- [ ] **Step 1: Migrate poster content**

Extract the body content from `poster.html` — the printable cheat sheet layout. Embed it in `#tab-poster`. Keep the poster's internal CSS (the grid layout, the traffic-light system, the red-flag phrases).

- [ ] **Step 2: Add print button**

At the top of the poster tab, add:
```html
<div style="padding: 24px 36px;" class="no-print">
  <button class="btn" onclick="window.print()">Print this page &rarr;</button>
  <span style="margin-left:12px; font-size:13px; color:var(--ink-soft);">Prints as a clean A4 cheat sheet</span>
</div>
```

- [ ] **Step 3: Add print-specific CSS**

```css
@media print {
  .topbar, .footer, .no-print { display: none !important; }
  .tab-content { display: none !important; }
  #tab-poster { display: block !important; }
  body { background: #fff; }
  @page { margin: 1cm; }
}
```

This ensures only the poster prints, regardless of which tab is active.

- [ ] **Step 4: Verify poster tab and print**

Open in browser. Confirm poster content renders. Use Cmd+P to verify print preview shows only the poster content on a clean A4 page.

- [ ] **Step 5: Commit**

```bash
git add "the-ai-playbook.html"
git commit -m "feat: add Poster tab with print support"
```

---

### Task 8: Polish, responsive, and final QA

**Files:**
- Modify: `/Users/jeffscott/Downloads/Oh, That's How/the-ai-playbook.html`

- [ ] **Step 1: Add responsive CSS for mobile**

Ensure all tab content works at common breakpoints:
- 1000px: guide grid goes single-column, audiences grid goes 3-column, tool grid goes 2-column
- 768px: Four Questions goes single-column, tool grid goes single-column
- 480px: topbar tabs wrap or become a dropdown

- [ ] **Step 2: Add smooth transitions**

Tab content should fade in when switched:
```css
.tab-content { opacity: 0; transition: opacity 0.2s ease; }
.tab-content.active { opacity: 1; }
```

Guide detail should slide in:
```css
#guide-detail { animation: slideIn 0.2s ease; }
@keyframes slideIn { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
```

- [ ] **Step 3: Verify all tabs end-to-end**

Walk through every tab:
1. Start Here: hero, Four Questions, audiences
2. Guides: grid, filters, click 3 guides, verify content, back button
3. Learn: grid, click 2 literacy pages, verify content, back button
4. Your Tools: GPT cards with links
5. Poster: content + print

- [ ] **Step 4: Check file size**

Run `wc -c the-ai-playbook.html`. Ensure it's reasonable for a Teams share (under 5MB). If over, check for unnecessary base64 images or redundant CSS.

- [ ] **Step 5: Commit**

```bash
git add "the-ai-playbook.html"
git commit -m "feat: polish responsive layout, transitions, and final QA"
```

---

## Notes for the implementer

1. **Content migration is the bulk of the work.** Tasks 4 and 5 involve reading 21 HTML files and extracting their body content. The CSS framework is already defined — it's copy/adapt work, not design work.

2. **The existing guide content is high quality.** Do not rewrite it. Migrate as-is, then add GPT callouts where relevant.

3. **Base64 images:** The `SSR.../project/guides/` folder has versions with embedded screenshots. Use those as the source for any guides that include ChatGPT UI screenshots. The `_latest/` versions are lean (no images) — do not use those.

4. **GPT links:** Use `https://chat.com/g/{gpt-id}` format. The user will need to provide the actual GPT IDs for each custom GPT. Use placeholder URLs initially: `https://chat.com/g/PLACEHOLDER-{gpt-name}`.

5. **Em dash rule:** The Playbook content itself should follow CN's "no em dashes" rule. The existing `index.html` has em dashes in the lede (line 286) — fix those during migration.

6. **Interview prep guide:** Removed per user decision. Do not include `interview-prep.html` content.

7. **Prompt builder tool:** Do not embed the interactive prompt builder. The Prompt Builder GPT on chat.com handles this. Reference it in the Your Tools tab.
