const $ = (sel) => document.querySelector(sel);
const $stage = () => {
  const el = $("#stage-body");
  if (el) el.scrollTo({ top: 0, behavior: 'smooth' });
  return el;
};

const STAGES = [
  { key: 'topic', label: 'Topic' },
  { key: 'articles', label: 'Articles' },
  { key: 'script', label: 'Script' },
  { key: 'check', label: 'Check' },
  { key: 'audio', label: 'Audio' },
  { key: 'publish', label: 'Publish' },
];

const app = {
  state: {
    step: 0,
    proposals: [],
    selectedTheme: null,
    bankId: null,
    sources: [],
    episodeName: null,
    script: null,
    teamsPost: null,
    tryThis: null,
  },

  _episodes: [],
  _filter: "all",
  _currentStage: null,

  async init() {
    await this.loadEpisodes();
    this.showResumeBanner();
  },

  // ── Stage rail ─────────────────────────────────────────────────────

  renderStageRail(activeIndex, doneUpTo = -1) {
    const rail = $("#stage-rail");
    if (!rail) return;
    rail.innerHTML = STAGES.map((s, i) => {
      let cls = 'stage-step';
      if (i === activeIndex) cls += ' active';
      else if (i <= doneUpTo) cls += ' done';
      return `<button class="${cls}" onclick="app.onStageClick(${i})">
        <span class="num">${i + 1}</span>${s.label}
      </button>`;
    }).join('');
    this._currentStage = activeIndex;
  },

  onStageClick(index) {
    // Stage rail clicks are informational for now — stages advance through the pipeline flow.
    // Could add navigation logic here later.
  },

  clearStageRail() {
    const rail = $("#stage-rail");
    if (rail) rail.innerHTML = '';
  },

  // ── Breadcrumbs & status ───────────────────────────────────────────

  updateBreadcrumbs(epName, stageName) {
    const el = $("#breadcrumbs");
    if (!el) return;
    if (!epName) {
      el.innerHTML = '<span>Studio</span>';
      return;
    }
    const short = epName.replace("The Signal – ", "");
    el.innerHTML = `<span>Studio</span><span class="sep">/</span><span class="ep-name">${short}</span>` +
      (stageName ? `<span class="sep">/</span><span>${stageName}</span>` : '');
  },

  updateStatusPill(state) {
    const pill = $("#status-pill");
    const label = $("#status-label");
    if (!pill || !label) return;
    pill.className = 'status-pill ' + (state || 'draft');
    const labels = { draft: 'Draft', ready: 'Ready', shared: 'Published', review: 'Review' };
    label.textContent = labels[state] || 'Draft';
  },

  // ── Episodes ───────────────────────────────────────────────────────

  async loadEpisodes() {
    try {
      const res = await fetch("/api/episodes");
      this._episodes = await res.json();
      this.renderEpisodeList();
    } catch (e) {
      console.error("Failed to load episodes:", e);
    }
  },

  setFilter(filter) {
    this._filter = filter;
    document.querySelectorAll(".sidebar-tab").forEach(b => {
      b.classList.toggle("active", b.dataset.filter === filter);
    });
    this.renderEpisodeList();
  },

  filterEpisodes() {
    this.renderEpisodeList();
  },

  renderEpisodeList() {
    const list = $("#episode-list");
    if (!list) return;
    const search = ($("#ep-search")?.value || "").toLowerCase();
    const filter = this._filter;

    let eps = this._episodes;
    if (filter !== "all") {
      eps = eps.filter(ep => (ep.episode_state || "draft") === filter);
    }
    if (search) {
      eps = eps.filter(ep => ep.name.toLowerCase().includes(search));
    }

    // Sort: drafts first, then ready, then shared. Within each group, newest first.
    const order = { draft: 0, ready: 1, shared: 2 };
    eps.sort((a, b) => {
      const sa = order[a.episode_state || "draft"] ?? 3;
      const sb = order[b.episode_state || "draft"] ?? 3;
      if (sa !== sb) return sa - sb;
      return (b.created_at || "").localeCompare(a.created_at || "");
    });

    list.innerHTML = eps.map((ep, idx) => {
      const state = ep.episode_state || "draft";
      const shortName = ep.name.replace("The Signal – ", "");
      const hasAudio = ep.has_audio ? "&#9835;" : "";
      const esc = ep.name.replace(/'/g, "\\'");
      const isActive = this._viewName === ep.name ? ' active' : '';
      const epNum = ep.number || (eps.length - idx);
      const dateStr = ep.created_at ? ep.created_at.split('T')[0] : '';

      return `
        <div class="ep-row${isActive}" onclick="app.viewEpisode('${esc}')">
          <div class="ep-thumb">${String(epNum).padStart(2, '0')}</div>
          <div class="ep-meta">
            <div class="title">${shortName}</div>
            <div class="sub">
              ${dateStr ? `<span>${dateStr}</span>` : ''}
              ${hasAudio ? `<span class="dot"></span><span>${hasAudio}</span>` : ''}
            </div>
          </div>
          <span class="ep-state-chip ${state}">${state}</span>
          <button class="ep-delete" onclick="event.stopPropagation(); app.deleteEpisode('${esc}')" title="Delete">&#10005;</button>
        </div>`;
    }).join("");

    if (eps.length === 0) {
      list.innerHTML = `<div style="color:var(--ink-500); padding:16px; font-style:italic; font-size:13px;">No episodes${filter !== 'all' ? ' in this filter' : ''}</div>`;
    }
  },

  showResumeBanner() {
    // Find the most recent draft episode.
    const draft = this._episodes.find(ep => (ep.episode_state || "draft") === "draft");
    if (!draft) return;
    const stage = $stage();
    const welcome = stage?.querySelector(".welcome");
    if (!welcome) return;
    const banner = document.createElement("div");
    banner.className = "continue-banner";
    banner.onclick = () => this.viewEpisode(draft.name);
    banner.innerHTML = `
      <h3>Continue working on:</h3>
      <p>${draft.name}</p>
    `;
    welcome.parentElement.insertBefore(banner, welcome.parentElement.firstChild);
  },

  async deleteEpisode(name) {
    if (!confirm(`Delete "${name}" and all its files?`)) return;
    try {
      await fetch(`/api/episodes/${encodeURIComponent(name)}`, { method: "DELETE" });
      this._episodes = this._episodes.filter(ep => ep.name !== name);
      this.renderEpisodeList();
      // If we're viewing this episode, go back to welcome.
      if (this._viewName === name) {
        this.showWelcome();
      }
    } catch (e) {
      alert("Failed to delete: " + e.message);
    }
  },

  showWelcome() {
    this._viewName = null;
    this.clearStageRail();
    this.updateBreadcrumbs(null);
    this.updateStatusPill('draft');
    $stage().innerHTML = `<div class="panel-pad"><div class="welcome">
      <h1>The Signal</h1>
      <p>Create podcast episodes for communicators at CN.</p>
      <button class="btn btn-primary btn-lg" onclick="app.newEpisode()">+ New Episode</button>
      <div style="margin-top:12px"><button class="btn btn-secondary" onclick="app.showThemeBank()">Edit Topics</button></div>
    </div></div>`;
  },

  // ── Step 1: Propose themes ──────────────────────────────────────────

  async newEpisode() {
    this.state = { step: 0, proposals: [], selectedTheme: null, bankId: null, sources: [], episodeName: null, script: null, teamsPost: null, tryThis: null };
    this._viewName = null;
    this.renderStageRail(0);
    this.updateBreadcrumbs(null, 'Topic');
    this.updateStatusPill('draft');

    try {
      const res = await fetch("/api/theme-bank");
      const bank = await res.json();

      // Group themes by first tag
      const groups = {};
      for (const t of bank) {
        const group = (t.tags && t.tags[0]) || "other";
        if (!groups[group]) groups[group] = [];
        groups[group].push(t);
      }

      let html = '';
      for (const [group, themes] of Object.entries(groups)) {
        const label = group.charAt(0).toUpperCase() + group.slice(1);
        html += `<div style="margin-top:20px; margin-bottom:8px; font-size:11px; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:var(--ink-500);">${label}</div>`;
        html += '<div class="theme-grid">';
        html += themes.map(t => {
          const used = t.times_used > 0;
          const tagClass = used ? 'used' : 'fresh';
          const tagText = used ? `${t.times_used}x used` : 'Available';
          return `
            <div class="theme-card" onclick="app.selectBankTheme('${t.id}', '${t.name.replace(/'/g, "\\'")}', '${(t.description || '').replace(/'/g, "\\'")}')">
              <div class="tc-head">
                <span class="tc-tag ${tagClass}">${tagText}</span>
              </div>
              <h3>${t.name}</h3>
              <div class="pitch">${t.description || ''}</div>
            </div>`;
        }).join("");
        html += '</div>';
      }

      $stage().innerHTML = `
        <div class="panel-pad">
          <div class="hello-head">
            <div>
              <h1>Pick a Topic</h1>
              <div class="sub">Choose a topic from the bank or type your own below.</div>
            </div>
          </div>
          ${html}
          <div class="theme-custom">
            <label>Custom topic</label>
            <input id="custom-theme" placeholder="Type your own topic here..." onkeydown="if(event.key==='Enter')app.selectCustomTheme()">
            <button class="btn btn-secondary" onclick="app.selectCustomTheme()">Use</button>
          </div>
        </div>
      `;
    } catch (e) {
      $stage().innerHTML = `<div class="panel-pad"><p style="color:var(--danger)">Error loading themes: ${e.message}</p></div>`;
    }
  },

  selectBankTheme(bankId, name, description) {
    this.state.selectedTheme = name;
    this.state.themeDescription = description || '';
    this.state.bankId = bankId;
    this.startResearch();
  },

  renderProposals() {
    this.renderStageRail(0);
    const cards = this.state.proposals.map((p, i) => {
      const used = p.times_used && p.times_used > 0;
      const tagClass = used ? 'used' : 'fresh';
      const tagText = used ? `${p.times_used}x used` : 'New';
      return `
        <div class="theme-card" onclick="app.selectTheme(${i})">
          <div class="tc-head">
            <span class="tc-tag ${tagClass}">${tagText}</span>
          </div>
          <h3>${p.name}</h3>
          <div class="pitch">${p.pitch}</div>
          <div class="preview-sources">
            ${(p.source_previews || []).map(s => `<span>${s}</span>`).join("")}
          </div>
        </div>`;
    }).join("");

    $stage().innerHTML = `
      <div class="panel-pad">
        <div class="hello-head">
          <div>
            <h1>Pick a Topic</h1>
            <div class="sub">Choose a topic, or type your own below.</div>
          </div>
        </div>
        <div class="theme-grid">${cards}</div>
        <div class="theme-custom">
          <label>Custom topic</label>
          <input id="custom-theme" placeholder="Type your own topic here..." onkeydown="if(event.key==='Enter')app.selectCustomTheme()">
          <button class="btn btn-secondary" onclick="app.selectCustomTheme()">Use</button>
        </div>
      </div>
    `;
  },

  selectTheme(index) {
    const p = this.state.proposals[index];
    this.state.selectedTheme = p.name;
    this.state.bankId = p.bank_id;
    this.startResearch();
  },

  selectCustomTheme() {
    const input = $("#custom-theme");
    if (input && input.value.trim().length > 5) {
      this.state.selectedTheme = input.value.trim();
      this.state.bankId = null;
      this.startResearch();
    }
  },

  // ── Step 2: Research ────────────────────────────────────────────────

  async startResearch() {
    this.renderStageRail(1, 0);
    this.updateBreadcrumbs(null, 'Articles');
    $stage().innerHTML = `
      <div class="panel-pad">
        <div class="step-header">
          <h1>Researching: ${this.state.selectedTheme}</h1>
          <p>Searching for the best sources...</p>
        </div>
        <div class="loading-msg"><div class="spinner"></div> Searching the web and fetching full articles...</div>
      </div>
    `;

    try {
      const res = await fetch("/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ theme_name: this.state.selectedTheme, theme_description: this.state.themeDescription || '' }),
      });
      const data = await res.json();
      this.state.sources = data.sources.map(s => ({ ...s, included: false }));
      this.renderSources();
    } catch (e) {
      $stage().innerHTML = `<div class="panel-pad"><p style="color:var(--danger)">Error researching theme: ${e.message}</p></div>`;
    }
  },

  renderSources() {
    this.renderStageRail(1, 0);
    const cards = this.state.sources.map((s, i) => {
      const isGartner = s.requires_auth;
      const needsText = isGartner && !s.full_text;
      const badge = isGartner ? `<span class="tc-tag bank" style="margin-left:8px">Gartner</span>` : '';

      const gartnerPanel = needsText ? `
        <div style="margin-top:8px; padding:10px; background:var(--ink-50); border:1px dashed var(--ink-400); border-radius:var(--r-sm);">
          <p style="font-size:11px; color:var(--ink-600); margin-bottom:6px;">Log in to Gartner, copy the article text, and paste it below.</p>
          <a href="${s.url}" target="_blank" class="btn btn-sm btn-secondary" style="margin-bottom:8px;">Open in Gartner &rarr;</a>
          <textarea id="gartner-paste-${i}" class="theme-input" placeholder="Paste article text here after logging in..." style="margin-top:0; min-height:80px; resize:vertical;"></textarea>
          <button class="btn btn-sm btn-primary" style="margin-top:6px;" onclick="app.captureGartnerText(${i})">Save Text</button>
        </div>` : '';

      // Show summary first (has theme-relevant context from search), then fall back to full text excerpt.
      const previewText = s.summary || (s.full_text ? s.full_text.substring(0, 300) : (isGartner ? 'Requires Gartner login -- click to open and paste content' : 'No text available'));

      return `
        <div class="source-card ${s.included ? 'included' : ''}" onclick="app.toggleSource(${i}, event)">
          <div class="source-toggle">
            <input type="checkbox" ${s.included ? 'checked' : ''}>
            <h4>${s.title}${badge}</h4>
          </div>
          <div class="meta">${s.source_domain} &middot; ${s.word_count || 0} words${s.published_at ? ' &middot; ' + s.published_at.split('T')[0] : ''}${s.relevance_score ? ` &middot; <span style="color:${s.relevance_score >= 8 ? 'var(--forest)' : s.relevance_score >= 5 ? 'var(--amber)' : 'var(--cn-red)'}; font-weight:600">relevance ${s.relevance_score}/10</span>` : ''}</div>
          <div class="preview" id="preview-${i}">${previewText.substring(0, 300)}${previewText.length > 300 ? '...' : ''}</div>
          ${!isGartner ? `<button id="toggle-btn-${i}" class="btn btn-sm btn-secondary" style="margin-top:8px" onclick="app.togglePreview(${i})">Show more</button>` : ''}
          ${gartnerPanel}
        </div>`;
    }).join("");

    const included = this.state.sources.filter(s => s.included).length;

    $stage().innerHTML = `
      <div class="panel-pad">
        <div class="step-header">
          <h1>Review Sources</h1>
          <p>${this.state.sources.length} sources found for "${this.state.selectedTheme}". Select the ones you want to use (${included} selected).</p>
        </div>
        ${cards}
        <div class="source-card" style="border-style:dashed; text-align:center; padding:16px;">
          <button class="btn btn-sm btn-secondary" onclick="app.showAddSource()">+ Add Source (Gartner, paywalled, or other)</button>
          <div id="add-source-form" style="display:none; text-align:left; margin-top:12px;">
            <input id="add-src-title" class="theme-input" placeholder="Article title" style="margin-top:0; margin-bottom:8px;">
            <input id="add-src-url" class="theme-input" placeholder="URL" style="margin-top:0; margin-bottom:8px;">
            <input id="add-src-domain" class="theme-input" placeholder="Source (e.g. gartner.com)" style="margin-top:0; margin-bottom:8px;">
            <textarea id="add-src-text" class="theme-input" placeholder="Paste article text here (for paywalled content like Gartner)" style="margin-top:0; min-height:100px; resize:vertical;"></textarea>
            <div class="actions" style="margin-top:8px;">
              <button class="btn btn-sm btn-primary" onclick="app.addManualSource()">Add</button>
            </div>
          </div>
        </div>
        <div class="actions">
          <button class="btn btn-secondary" onclick="app.newEpisode()">Start Over</button>
          <button class="btn btn-primary" onclick="app.generateScript()" ${included < 1 ? 'disabled' : ''}>Generate Script</button>
        </div>
      </div>
    `;
  },

  toggleSource(index, event) {
    // Don't toggle when clicking Show more/less button or Gartner controls
    if (event && (event.target.tagName === 'BUTTON' || event.target.tagName === 'TEXTAREA' || event.target.tagName === 'A')) return;
    this.state.sources[index].included = !this.state.sources[index].included;
    this.renderSources();
  },

  captureGartnerText(index) {
    const textarea = document.getElementById(`gartner-paste-${index}`);
    if (!textarea || !textarea.value.trim()) { alert("Please paste the article text first."); return; }
    const text = textarea.value.trim();
    this.state.sources[index].full_text = text;
    this.state.sources[index].word_count = text.split(/\s+/).length;
    this.renderSources();
  },

  showAddSource() {
    const form = document.getElementById("add-source-form");
    if (form) form.style.display = form.style.display === "none" ? "block" : "none";
  },

  addManualSource() {
    const title = (document.getElementById("add-src-title")?.value || "").trim();
    const url = (document.getElementById("add-src-url")?.value || "").trim();
    const domain = (document.getElementById("add-src-domain")?.value || "").trim();
    const text = (document.getElementById("add-src-text")?.value || "").trim();
    if (!title) { alert("Title is required."); return; }
    this.state.sources.push({
      title, url: url || "#manual", source_domain: domain || "manual",
      published_at: null, summary: text ? text.substring(0, 200) : "",
      full_text: text || null, word_count: text ? text.split(/\s+/).length : 0,
      included: true,
    });
    this.renderSources();
  },

  _formatPreviewText(text) {
    if (!text) return '<p>No text available</p>';
    const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    // Split on double-newlines first; if none, split long text into ~sentence-based paragraphs
    const paragraphs = escaped.split(/\n\s*\n/).filter(p => p.trim());
    if (paragraphs.length > 1) {
      return paragraphs.map(para => `<p>${para.replace(/\n/g, '<br>')}</p>`).join('');
    }
    // No paragraph breaks — break every ~3-4 sentences for readability
    const sentences = escaped.split(/(?<=[.!?])\s+/);
    const chunks = [];
    for (let i = 0; i < sentences.length; i += 4) {
      chunks.push(`<p>${sentences.slice(i, i + 4).join(' ')}</p>`);
    }
    return chunks.join('');
  },

  togglePreview(index) {
    const el = document.getElementById(`preview-${index}`);
    const btn = document.getElementById(`toggle-btn-${index}`);
    if (el) {
      el.classList.toggle("expanded");
      const s = this.state.sources[index];
      if (el.classList.contains("expanded")) {
        el.innerHTML = this._formatPreviewText(s.full_text || s.summary);
        if (btn) btn.textContent = "Show less";
      } else {
        el.textContent = (s.full_text || s.summary || "No text available").substring(0, 300) + "...";
        if (btn) btn.textContent = "Show more";
      }
    }
  },

  // ── Step 3: Generate script ─────────────────────────────────────────

  async generateScript() {
    const includedSources = this.state.sources.filter(s => s.included);
    this.renderStageRail(2, 1);
    this.updateBreadcrumbs(null, 'Script');

    $stage().innerHTML = `
      <div class="panel-pad">
        <div class="step-header">
          <h1>Generating Script</h1>
          <p>Writing your episode on "${this.state.selectedTheme}"...</p>
        </div>
        <div class="loading-msg"><div class="spinner"></div> Writing the script. This may take a minute...</div>
      </div>
    `;

    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          theme_name: this.state.selectedTheme,
          sources: includedSources,
          bank_id: this.state.bankId,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        throw new Error(data.error || `Server error (${res.status})`);
      }
      this.state.episodeName = data.episode_name;
      this.state.script = data.script;
      this.state.teamsPost = data.teams_post;
      this.state.tryThis = data.try_this;
      this.state.coverUrl = data.cover_url;
      this.state.wordCount = data.word_count;
      this.updateBreadcrumbs(data.episode_name, 'Script');
      this.renderScript("script");
    } catch (e) {
      $stage().innerHTML = `
        <div class="panel-pad">
          <div class="step-header"><h1>Script Generation Failed</h1></div>
          <p style="color:var(--danger); margin-bottom:16px">${e.message}</p>
          <div class="actions">
            <button class="btn btn-secondary" onclick="app.newEpisode()">Start Over</button>
            <button class="btn btn-primary" onclick="app.generateScript()">Retry</button>
          </div>
        </div>`;
    }
  },

  renderScript(activeTab = "script") {
    this.renderStageRail(2, 1);
    // Save editor content if switching away from script tab.
    const editor = document.getElementById("script-editor");
    if (editor) {
      this.state.script = editor.value;
    }

    const content = {
      script: this.state.script,
      teams: this.state.teamsPost,
      trythis: this.state.tryThis,
    };

    $stage().innerHTML = `
      <div class="panel-pad">
        <div class="step-header">
          <h1>${this.state.episodeName}</h1>
          <p>${this.state.wordCount} words &middot; ~${Math.round(this.state.wordCount / 130)} minutes</p>
        </div>
        <div class="tabs">
          <button class="tab ${activeTab === 'script' ? 'active' : ''}" onclick="app.renderScript('script')">Script</button>
          <button class="tab ${activeTab === 'teams' ? 'active' : ''}" onclick="app.renderScript('teams')">Teams Post</button>
          <button class="tab ${activeTab === 'trythis' ? 'active' : ''}" onclick="app.renderScript('trythis')">Try This</button>
        </div>
        <textarea class="script-display" id="script-editor" style="width:100%;min-height:400px;resize:vertical;${activeTab === 'script' ? '' : 'display:none;'}">${this.state.script || ''}</textarea>
        <div class="script-display" id="script-readonly" style="${activeTab !== 'script' ? '' : 'display:none;'}">${content[activeTab] || '(empty)'}</div>
        <div class="actions">
          <button class="btn btn-secondary" onclick="app.finish()">Skip Audio & Finish</button>
          <button class="btn btn-primary" onclick="app.saveAndGenerateAudio()">Generate Audio</button>
        </div>
      </div>
    `;
  },

  async saveAndGenerateAudio() {
    // Save any edits from the script editor before generating audio.
    const editor = document.getElementById("script-editor");
    if (editor) {
      this.state.script = editor.value;
      // Persist edits to the server so TTS uses the edited version.
      try {
        await fetch(`/api/files/${encodeURIComponent(this.state.episodeName)} - Script.md`, {
          method: "PUT",
          headers: { "Content-Type": "text/plain" },
          body: this.state.script,
        });
      } catch (e) {
        console.warn("Could not save script edits:", e);
      }
    }
    this.generateAudio();
  },

  // ── Step 4: Audio ───────────────────────────────────────────────────

  async generateAudio() {
    this.renderStageRail(4, 2);
    this.updateBreadcrumbs(this.state.episodeName, 'Audio');

    $stage().innerHTML = `
      <div class="panel-pad">
        <div class="step-header">
          <h1>Generating Audio</h1>
          <p>Converting your script to audio...</p>
        </div>
        <div class="loading-msg"><div class="spinner"></div> Generating audio. This may take a couple of minutes...</div>
      </div>
    `;

    try {
      const res = await fetch("/api/audio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ episode_name: this.state.episodeName }),
      });
      const data = await res.json();

      if (data.error) {
        $stage().innerHTML += `<div class="panel-pad"><p style="color:var(--danger); margin-top:16px">Audio error: ${data.error}</p>
          <div class="actions"><button class="btn btn-primary" onclick="app.finish()">Continue Without Audio</button></div></div>`;
        return;
      }

      this.state.audioUrl = data.audio_url;
      this.finish();
    } catch (e) {
      $stage().innerHTML += `<div class="panel-pad"><p style="color:var(--danger); margin-top:16px">Audio error: ${e.message}</p>
        <div class="actions"><button class="btn btn-primary" onclick="app.finish()">Continue Without Audio</button></div></div>`;
    }
  },

  // ── Step 5: Done ────────────────────────────────────────────────────

  finish() {
    const name = this.state.episodeName;
    this.renderStageRail(5, 4);
    this.updateBreadcrumbs(name, 'Publish');

    const audioHtml = this.state.audioUrl
      ? `<div class="audio-player">
          <strong>Episode Audio</strong>
          <audio controls src="${this.state.audioUrl}"></audio>
        </div>`
      : '';

    $stage().innerHTML = `
      <div class="panel-pad">
        <div class="step-header">
          <h1>Episode Complete</h1>
          <p>${name}</p>
        </div>
        <div class="summary-grid">
          <div class="summary-item"><div class="label">Words</div><div class="value">${this.state.wordCount || '---'}</div></div>
          <div class="summary-item"><div class="label">Sources</div><div class="value">${this.state.sources.filter(s => s.included).length}</div></div>
          <div class="summary-item"><div class="label">Topic</div><div class="value" style="font-size:14px">${this.state.selectedTheme}</div></div>
          <div class="summary-item"><div class="label">Audio</div><div class="value">${this.state.audioUrl ? 'Yes' : 'Skipped'}</div></div>
        </div>
        ${audioHtml}
        <h3 style="margin-top:24px; margin-bottom:8px;">Download Files</h3>
        <ul class="download-list">
          <li><a href="/api/files/${encodeURIComponent(name)} - Script.md" download>Script (Markdown)</a></li>
          <li><a href="/api/files/${encodeURIComponent(name)} - Teams Post.md" download>Teams Post</a></li>
          <li><a href="/api/files/${encodeURIComponent(name)} - Try This.md" download>Try This</a></li>
          <li><a href="/api/files/${encodeURIComponent(name)} - Cover.png" download>Cover Art</a></li>
          ${this.state.audioUrl ? `<li><a href="${this.state.audioUrl}" download>Audio (MP3)</a></li>` : ''}
          <li><a href="/api/files/${encodeURIComponent(name)} - Manifest.json" download>Manifest (JSON)</a></li>
        </ul>
        <div class="actions" style="margin-top:24px">
          <button class="btn btn-primary" onclick="app.newEpisode()">+ New Episode</button>
        </div>
      </div>
    `;

    this.loadEpisodes();
  },

  // ── View past episode ───────────────────────────────────────────────

  async viewEpisode(name) {
    this._viewName = name;
    this.renderEpisodeList(); // Update active highlight
    $stage().innerHTML = `<div class="panel-pad"><div class="loading-msg"><div class="spinner"></div> Loading episode...</div></div>`;

    try {
      const res = await fetch(`/api/episodes/${encodeURIComponent(name)}`);
      const data = await res.json();
      this._viewData = data;
      this.renderEpisodeView(data, name, "script");
    } catch (e) {
      $stage().innerHTML = `<div class="panel-pad"><p style="color:var(--danger)">Error loading episode: ${e.message}</p></div>`;
    }
  },

  renderEpisodeView(data, name, activeTab = "script") {
    const state = data.episode_state || "draft";
    const stateLabel = { draft: "Draft", ready: "Ready", shared: "Published" };
    const isEditable = state !== "shared";

    // Update chrome
    this.updateBreadcrumbs(name, 'Script');
    this.updateStatusPill(state);
    // Show stage rail in context - script stage when viewing
    this.renderStageRail(2, state === 'shared' ? 5 : state === 'ready' ? 3 : 2);

    const audioHtml = data.has_audio
      ? `<div class="audio-player">
          <strong>Episode Audio</strong>
          <audio controls src="${data.audio_url}"></audio>
        </div>`
      : '';

    // State actions based on current state.
    let stateButtons = '';
    if (state === "draft") {
      stateButtons = `
        <button class="btn btn-secondary" onclick="app.regenerateScript('${name.replace(/'/g, "\\'")}')">Regenerate Script</button>
        <button class="btn btn-secondary" onclick="app.generateAudioForEpisode('${name.replace(/'/g, "\\'")}')">Generate Audio</button>
        <button class="btn btn-primary" onclick="app.setEpisodeState('${name.replace(/'/g, "\\'")}', 'ready')">Mark as Ready</button>`;
    } else if (state === "ready") {
      stateButtons = `
        <button class="btn btn-secondary" onclick="app.setEpisodeState('${name.replace(/'/g, "\\'")}', 'draft')">Back to Draft</button>
        <button class="btn btn-secondary" onclick="app.regenerateScript('${name.replace(/'/g, "\\'")}')">Regenerate Script</button>
        <button class="btn btn-secondary" onclick="app.generateAudioForEpisode('${name.replace(/'/g, "\\'")}')">Regenerate Audio</button>
        <button class="btn btn-primary" onclick="app.setEpisodeState('${name.replace(/'/g, "\\'")}', 'shared')">Mark as Published</button>`;
    } else {
      stateButtons = `<button class="btn btn-secondary" onclick="app.setEpisodeState('${name.replace(/'/g, "\\'")}', 'ready')">Back to Ready</button>`;
    }

    // Script tab: editable textarea if not shared, readonly otherwise.
    const scriptContent = activeTab === "script"
      ? (isEditable
        ? `<textarea class="script-display" id="episode-editor" style="width:100%;min-height:400px;resize:vertical;">${data.script || ''}</textarea>
           <div class="actions" style="margin-top:8px"><button class="btn btn-sm btn-secondary" onclick="app.saveEpisodeScript('${name.replace(/'/g, "\\'")}')">Save Edits</button></div>`
        : `<div class="script-display">${data.script || '(No script)'}</div>`)
      : `<div class="script-display" id="view-content">${activeTab === 'teams' ? (data.teams_post || '(empty)') : (data.try_this || '(empty)')}</div>`;

    $stage().innerHTML = `
      <div class="panel-pad">
        <div class="step-header">
          <h1>${data.name}</h1>
          <p><span class="ep-state-chip ${state}">${stateLabel[state]}</span></p>
        </div>
        <div class="tabs">
          <button class="tab ${activeTab === 'script' ? 'active' : ''}" onclick="app.renderEpisodeView(app._viewData, app._viewName, 'script')">Script</button>
          <button class="tab ${activeTab === 'teams' ? 'active' : ''}" onclick="app.renderEpisodeView(app._viewData, app._viewName, 'teams')">Teams Post</button>
          <button class="tab ${activeTab === 'trythis' ? 'active' : ''}" onclick="app.renderEpisodeView(app._viewData, app._viewName, 'trythis')">Try This</button>
        </div>
        ${scriptContent}
        ${audioHtml}
        <h3 style="margin-top:24px; margin-bottom:8px;">Downloads</h3>
        <ul class="download-list">
          <li><a href="/api/files/${encodeURIComponent(name)} - Script.md" download>Script</a></li>
          <li><a href="/api/files/${encodeURIComponent(name)} - Teams Post.md" download>Teams Post</a></li>
          <li><a href="/api/files/${encodeURIComponent(name)} - Try This.md" download>Try This</a></li>
          <li><a href="/api/files/${encodeURIComponent(name)} - Cover.png" download>Cover Art</a></li>
          ${data.has_audio ? `<li><a href="${data.audio_url}" download>Audio (MP3)</a></li>` : ''}
        </ul>
        <div class="actions" style="margin-top:16px">
          ${stateButtons}
        </div>
      </div>
    `;
  },

  async setEpisodeState(name, state) {
    try {
      await fetch(`/api/episodes/${encodeURIComponent(name)}/state`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ state }),
      });
      this._viewData.episode_state = state;
      this.renderEpisodeView(this._viewData, name, "script");
      this.loadEpisodes();
    } catch (e) {
      alert("Failed to update state: " + e.message);
    }
  },

  async saveEpisodeScript(name) {
    const editor = document.getElementById("episode-editor");
    if (!editor) return;
    try {
      await fetch(`/api/files/${encodeURIComponent(name)} - Script.md`, {
        method: "PUT",
        headers: { "Content-Type": "text/plain" },
        body: editor.value,
      });
      this._viewData.script = editor.value;
      // Brief visual feedback.
      const btn = editor.parentElement.querySelector(".btn");
      if (btn) { btn.textContent = "Saved!"; setTimeout(() => btn.textContent = "Save Edits", 1500); }
    } catch (e) {
      alert("Failed to save: " + e.message);
    }
  },

  async regenerateScript(name) {
    this.renderStageRail(2, 1);
    $stage().innerHTML = `
      <div class="panel-pad">
        <div class="step-header"><h1>Regenerating Script</h1><p>${name}</p></div>
        <div class="loading-msg"><div class="spinner"></div> Writing a fresh take with the same sources...</div>
      </div>
    `;
    try {
      const res = await fetch("/api/regenerate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ episode_name: name }),
      });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || "Regeneration failed");
      // Reload the episode view with the new script.
      this.viewEpisode(data.episode_name || name);
    } catch (e) {
      $stage().innerHTML = `
        <div class="panel-pad">
          <p style="color:var(--danger)">${e.message}</p>
          <div class="actions"><button class="btn btn-primary" onclick="app.viewEpisode('${name.replace(/'/g, "\\'")}')">Back to Episode</button></div>
        </div>`;
    }
  },

  // ── Theme Bank ──────────────────────────────────────────────────────

  async showThemeBank() {
    this.clearStageRail();
    this.updateBreadcrumbs(null, 'Edit Topics');
    $stage().innerHTML = `<div class="panel-pad"><div class="loading-msg"><div class="spinner"></div> Loading topics...</div></div>`;
    try {
      const res = await fetch("/api/theme-bank");
      const themes = await res.json();
      this._themeBank = themes;
      this.renderThemeBank();
    } catch (e) {
      $stage().innerHTML = `<div class="panel-pad"><p style="color:var(--danger)">Error loading theme bank: ${e.message}</p></div>`;
    }
  },

  renderThemeBank() {
    const themes = this._themeBank || [];
    const rows = themes.map(t => {
      const tags = (t.tags || []).join(", ");
      const used = t.times_used > 0;
      const tagClass = used ? 'used' : 'fresh';
      const tagText = used ? `${t.times_used}x used` : 'Never used';
      const esc = t.id.replace(/'/g, "\\'");
      return `
        <div class="source-card" style="display:flex; gap:12px; align-items:flex-start;">
          <div style="flex:1;">
            <h4 id="name-display-${t.id}">${t.name}</h4>
            <div style="font-size:12px; color:var(--ink-600); margin:4px 0;">${t.description}</div>
            <div style="font-size:11px; color:var(--ink-500);">${tags ? 'Tags: ' + tags : ''}</div>
            <span class="tc-tag ${tagClass}" style="margin-top:6px">${tagText}</span>
          </div>
          <div style="display:flex; gap:4px; flex-shrink:0;">
            <button class="btn btn-sm btn-secondary" onclick="app.editTheme('${esc}')">Edit</button>
            <button class="btn btn-sm danger-ghost" onclick="app.deleteTheme('${esc}')">Delete</button>
          </div>
        </div>`;
    }).join("");

    $stage().innerHTML = `
      <div class="panel-pad">
        <div class="step-header">
          <h1>Edit Topics</h1>
          <p>${themes.length} topics. Click Edit to modify, or add a new one below.</p>
        </div>
        ${rows}
        <div class="source-card" style="border-style:dashed;">
          <h4 style="margin-bottom:8px;">Add New Topic</h4>
          <input id="new-theme-name" class="theme-input" placeholder="Topic name" style="margin-top:0; margin-bottom:8px;">
          <input id="new-theme-desc" class="theme-input" placeholder="Description --- one sentence about what this topic covers" style="margin-top:0; margin-bottom:8px;">
          <input id="new-theme-tags" class="theme-input" placeholder="Tags (comma-separated)" style="margin-top:0; margin-bottom:8px;">
          <button class="btn btn-sm btn-primary" onclick="app.addTheme()">Add Topic</button>
        </div>
      </div>
    `;
  },

  async editTheme(themeId) {
    const theme = (this._themeBank || []).find(t => t.id === themeId);
    if (!theme) return;
    const name = prompt("Topic name:", theme.name);
    if (name === null) return;
    const desc = prompt("Description:", theme.description);
    if (desc === null) return;
    const tagsStr = prompt("Tags (comma-separated):", (theme.tags || []).join(", "));
    if (tagsStr === null) return;
    const tags = tagsStr.split(",").map(t => t.trim()).filter(Boolean);
    try {
      await fetch(`/api/theme-bank/${encodeURIComponent(themeId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description: desc, tags }),
      });
      this.showThemeBank();
    } catch (e) {
      alert("Failed to update: " + e.message);
    }
  },

  async deleteTheme(themeId) {
    if (!confirm("Delete this topic?")) return;
    try {
      await fetch(`/api/theme-bank/${encodeURIComponent(themeId)}`, { method: "DELETE" });
      this.showThemeBank();
    } catch (e) {
      alert("Failed to delete: " + e.message);
    }
  },

  async addTheme() {
    const name = (document.getElementById("new-theme-name")?.value || "").trim();
    const desc = (document.getElementById("new-theme-desc")?.value || "").trim();
    const tagsStr = (document.getElementById("new-theme-tags")?.value || "").trim();
    if (!name) { alert("Topic name is required."); return; }
    const tags = tagsStr ? tagsStr.split(",").map(t => t.trim()).filter(Boolean) : [];
    try {
      const res = await fetch("/api/theme-bank", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description: desc, tags }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      this.showThemeBank();
    } catch (e) {
      alert("Failed to add: " + e.message);
    }
  },

  async generateAudioForEpisode(name) {
    this.renderStageRail(4, 2);
    this.updateBreadcrumbs(name, 'Audio');
    $stage().innerHTML = `
      <div class="panel-pad">
        <div class="step-header"><h1>Generating Audio</h1><p>${name}</p></div>
        <div class="loading-msg"><div class="spinner"></div> Converting script to audio...</div>
      </div>
    `;
    try {
      const res = await fetch("/api/audio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ episode_name: name }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      this.viewEpisode(name);
    } catch (e) {
      $stage().innerHTML = `
        <div class="panel-pad">
          <p style="color:var(--danger)">Audio error: ${e.message}</p>
          <div class="actions"><button class="btn btn-primary" onclick="app.viewEpisode('${name.replace(/'/g, "\\'")}')">Back to Episode</button></div>
        </div>`;
    }
  },
};

// Boot.
document.addEventListener("DOMContentLoaded", () => app.init());
