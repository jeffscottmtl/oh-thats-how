const $ = (sel) => document.querySelector(sel);
const $main = () => $("#main");

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

  async init() {
    await this.loadEpisodes();
    this.showResumeBanner();
  },

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
    document.querySelectorAll(".filter-btn").forEach(b => {
      b.classList.toggle("active", b.dataset.filter === filter);
    });
    this.renderEpisodeList();
  },

  filterEpisodes() {
    this.renderEpisodeList();
  },

  renderEpisodeList() {
    const list = $("#episode-list");
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

    list.innerHTML = eps.map(ep => {
      const state = ep.episode_state || "draft";
      const shortName = ep.name.replace("The Signal – ", "");
      const hasAudio = ep.has_audio ? "🎧" : "";
      const esc = ep.name.replace(/'/g, "\\'");
      return `
        <li onclick="app.viewEpisode('${esc}')">
          ${shortName}
          <button class="ep-delete" onclick="event.stopPropagation(); app.deleteEpisode('${esc}')" title="Delete">✕</button>
          <div class="ep-meta">
            <span class="ep-badge ${state}">${state}</span>
            <span class="ep-icons">${hasAudio}</span>
          </div>
        </li>`;
    }).join("");

    if (eps.length === 0) {
      list.innerHTML = `<li style="color:var(--text-dim); cursor:default; font-style:italic;">No episodes${filter !== 'all' ? ' in this filter' : ''}</li>`;
    }
  },

  showResumeBanner() {
    // Find the most recent draft episode.
    const draft = this._episodes.find(ep => (ep.episode_state || "draft") === "draft");
    if (!draft) return;
    const main = $main();
    const welcome = main.querySelector(".welcome");
    if (!welcome) return;
    const esc = draft.name.replace(/'/g, "\\'");
    const banner = document.createElement("div");
    banner.className = "continue-banner";
    banner.onclick = () => this.viewEpisode(draft.name);
    banner.innerHTML = `
      <h3>Continue working on:</h3>
      <p>${draft.name}</p>
    `;
    main.insertBefore(banner, welcome);
  },

  async deleteEpisode(name) {
    if (!confirm(`Delete "${name}" and all its files?`)) return;
    try {
      await fetch(`/api/episodes/${encodeURIComponent(name)}`, { method: "DELETE" });
      this._episodes = this._episodes.filter(ep => ep.name !== name);
      this.renderEpisodeList();
      // If we're viewing this episode, go back to welcome.
      if (this._viewName === name) {
        $main().innerHTML = `<div class="welcome"><h1>The Signal</h1><p>Create podcast episodes for communicators at CN.</p><button class="btn btn-primary" onclick="app.newEpisode()">+ New Episode</button></div>`;
      }
    } catch (e) {
      alert("Failed to delete: " + e.message);
    }
  },

  renderSteps(current, total = 5) {
    return `<div class="step-indicator">
      ${Array.from({length: total}, (_, i) =>
        `<div class="step-dot ${i < current ? 'done' : ''} ${i === current ? 'active' : ''}"></div>`
      ).join("")}
    </div>`;
  },

  // ── Step 1: Propose themes ──────────────────────────────────────────

  async newEpisode() {
    this.state = { step: 0, proposals: [], selectedTheme: null, bankId: null, sources: [], episodeName: null, script: null, teamsPost: null, tryThis: null };
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
        const cards = themes.map(t => {
          const used = t.times_used > 0;
          const badge = used
            ? `<span class="badge used">${t.times_used}x · last ${t.last_used || '?'}</span>`
            : `<span class="badge fresh">Available</span>`;
          return `
            <div class="card" onclick="app.selectBankTheme('${t.id}', '${t.name.replace(/'/g, "\\'")}')">
              <h3>${t.name}</h3>
              <p>${t.description}</p>
              ${badge}
            </div>`;
        }).join("");
        html += `<h2 style="margin-top:24px; margin-bottom:12px; font-size:16px; color:var(--text-dim);">${label}</h2><div class="card-grid">${cards}</div>`;
      }

      $main().innerHTML = `
        ${this.renderSteps(0)}
        <div class="step-header">
          <h1>Pick a Theme</h1>
          <p>Choose a theme or type your own topic.</p>
        </div>
        ${html}
        <input class="theme-input" id="custom-theme" placeholder="Or type your own topic here..." onkeydown="if(event.key==='Enter')app.selectCustomTheme()">
        <div class="actions">
          <button class="btn btn-secondary" onclick="app.selectCustomTheme()">Use Custom Topic</button>
        </div>
      `;
    } catch (e) {
      $main().innerHTML = `<p style="color:var(--danger)">Error loading themes: ${e.message}</p>`;
    }
  },

  selectBankTheme(bankId, name) {
    this.state.selectedTheme = name;
    this.state.bankId = bankId;
    this.startResearch();
  },

  renderProposals() {
    const cards = this.state.proposals.map((p, i) => {
      const used = p.times_used && p.times_used > 0;
      const badge = used
        ? `<span class="badge used">${p.times_used}x used · last ${p.last_used || '?'}</span>`
        : `<span class="badge fresh">New</span>`;
      return `
        <div class="card" onclick="app.selectTheme(${i})">
          <h3>${p.name}</h3>
          <p>${p.pitch}</p>
          ${badge}
          <div class="sources">
            ${(p.source_previews || []).map(s => `<span>&#8226; ${s}</span>`).join("")}
          </div>
        </div>`;
    }).join("");

    $main().innerHTML = `
      ${this.renderSteps(0)}
      <div class="step-header">
        <h1>Pick a Theme</h1>
        <p>Choose a theme, or type your own topic below.</p>
      </div>
      <div class="card-grid">${cards}</div>
      <input class="theme-input" id="custom-theme" placeholder="Or type your own topic here..." onkeydown="if(event.key==='Enter')app.selectCustomTheme()">
      <div class="actions">
        <button class="btn btn-secondary" onclick="app.selectCustomTheme()">Use Custom Topic</button>
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
    window.scrollTo({ top: 0, behavior: 'smooth' });
    $main().innerHTML = `
      ${this.renderSteps(1)}
      <div class="step-header">
        <h1>Researching: ${this.state.selectedTheme}</h1>
        <p>Searching for the best sources...</p>
      </div>
      <div class="loading-msg"><div class="spinner"></div> Searching the web and fetching full articles...</div>
    `;

    try {
      const res = await fetch("/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ theme_name: this.state.selectedTheme }),
      });
      const data = await res.json();
      this.state.sources = data.sources.map(s => ({ ...s, included: true }));
      this.renderSources();
    } catch (e) {
      $main().innerHTML = `<p style="color:var(--danger)">Error researching theme: ${e.message}</p>`;
    }
  },

  renderSources() {
    const cards = this.state.sources.map((s, i) => {
      const isGartner = s.requires_auth;
      const needsText = isGartner && !s.full_text;
      const badge = isGartner ? `<span class="ep-badge" style="background:rgba(139,92,246,0.15);color:#7c3aed;margin-left:8px">Gartner</span>` : '';

      const gartnerPanel = needsText ? `
        <div class="gartner-panel" style="margin-top:8px; padding:10px; background:rgba(139,92,246,0.05); border:1px dashed #7c3aed; border-radius:6px;">
          <p style="font-size:11px; color:var(--text-dim); margin-bottom:6px;">Log in to Gartner, copy the article text, and paste it below.</p>
          <a href="${s.url}" target="_blank" class="btn btn-sm btn-secondary" style="margin-bottom:8px;">Open in Gartner &rarr;</a>
          <textarea id="gartner-paste-${i}" class="theme-input" placeholder="Paste article text here after logging in..." style="margin-top:0; min-height:80px; resize:vertical;"></textarea>
          <button class="btn btn-sm btn-primary" style="margin-top:6px;" onclick="app.captureGartnerText(${i})">Save Text</button>
        </div>` : '';

      // Show summary first (has theme-relevant context from search), then fall back to full text excerpt.
      const previewText = s.summary || (s.full_text ? s.full_text.substring(0, 300) : (isGartner ? 'Requires Gartner login — click to open and paste content' : 'No text available'));

      return `
        <div class="source-card ${s.included ? '' : 'excluded'}">
          <div class="source-toggle">
            <input type="checkbox" ${s.included ? 'checked' : ''} onchange="app.toggleSource(${i})">
            <h4>${s.title}${badge}</h4>
          </div>
          <div class="meta">${s.source_domain} &middot; ${s.word_count || 0} words${s.published_at ? ' &middot; ' + s.published_at.split('T')[0] : ''}</div>
          <div class="preview" id="preview-${i}">${previewText.substring(0, 300)}${previewText.length > 300 ? '...' : ''}</div>
          ${!isGartner ? `<button id="toggle-btn-${i}" class="btn btn-sm btn-secondary" style="margin-top:8px" onclick="app.togglePreview(${i})">Show more</button>` : ''}
          ${gartnerPanel}
        </div>`;
    }).join("");

    const included = this.state.sources.filter(s => s.included).length;

    $main().innerHTML = `
      ${this.renderSteps(1)}
      <div class="step-header">
        <h1>Review Sources</h1>
        <p>${included} sources selected for "${this.state.selectedTheme}". Uncheck any you want to exclude.</p>
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
    `;
  },

  toggleSource(index) {
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
    window.scrollTo({ top: 0, behavior: 'smooth' });

    $main().innerHTML = `
      ${this.renderSteps(2)}
      <div class="step-header">
        <h1>Generating Script</h1>
        <p>Writing your episode on "${this.state.selectedTheme}"...</p>
      </div>
      <div class="loading-msg"><div class="spinner"></div> Writing the script. This may take a minute...</div>
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
      this.renderScript("script");
    } catch (e) {
      $main().innerHTML = `
        ${this.renderSteps(2)}
        <div class="step-header"><h1>Script Generation Failed</h1></div>
        <p style="color:var(--danger); margin-bottom:16px">${e.message}</p>
        <div class="actions">
          <button class="btn btn-secondary" onclick="app.newEpisode()">Start Over</button>
          <button class="btn btn-primary" onclick="app.generateScript()">Retry</button>
        </div>`;
    }
  },

  renderScript(activeTab = "script") {
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

    $main().innerHTML = `
      ${this.renderSteps(2)}
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
    window.scrollTo({ top: 0, behavior: 'smooth' });
    $main().innerHTML = `
      ${this.renderSteps(3)}
      <div class="step-header">
        <h1>Generating Audio</h1>
        <p>Converting your script to audio...</p>
      </div>
      <div class="loading-msg"><div class="spinner"></div> Generating audio. This may take a couple of minutes...</div>
    `;

    try {
      const res = await fetch("/api/audio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ episode_name: this.state.episodeName }),
      });
      const data = await res.json();

      if (data.error) {
        $main().innerHTML += `<p style="color:var(--danger); margin-top:16px">Audio error: ${data.error}</p>
          <div class="actions"><button class="btn btn-primary" onclick="app.finish()">Continue Without Audio</button></div>`;
        return;
      }

      this.state.audioUrl = data.audio_url;
      this.finish();
    } catch (e) {
      $main().innerHTML += `<p style="color:var(--danger); margin-top:16px">Audio error: ${e.message}</p>
        <div class="actions"><button class="btn btn-primary" onclick="app.finish()">Continue Without Audio</button></div>`;
    }
  },

  // ── Step 5: Done ────────────────────────────────────────────────────

  finish() {
    const name = this.state.episodeName;
    const audioHtml = this.state.audioUrl
      ? `<div class="audio-player">
          <strong>Episode Audio</strong>
          <audio controls src="${this.state.audioUrl}"></audio>
        </div>`
      : '';

    $main().innerHTML = `
      ${this.renderSteps(4)}
      <div class="step-header">
        <h1>Episode Complete</h1>
        <p>${name}</p>
      </div>
      <div class="summary-grid">
        <div class="summary-item"><div class="label">Words</div><div class="value">${this.state.wordCount || '—'}</div></div>
        <div class="summary-item"><div class="label">Sources</div><div class="value">${this.state.sources.filter(s => s.included).length}</div></div>
        <div class="summary-item"><div class="label">Theme</div><div class="value" style="font-size:14px">${this.state.selectedTheme}</div></div>
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
    `;

    this.loadEpisodes();
  },

  // ── View past episode ───────────────────────────────────────────────

  async viewEpisode(name) {
    $main().innerHTML = `<div class="loading-msg"><div class="spinner"></div> Loading episode...</div>`;

    try {
      const res = await fetch(`/api/episodes/${encodeURIComponent(name)}`);
      const data = await res.json();
      this._viewData = data;
      this._viewName = name;
      this.renderEpisodeView(data, name, "script");
    } catch (e) {
      $main().innerHTML = `<p style="color:var(--danger)">Error loading episode: ${e.message}</p>`;
    }
  },

  renderEpisodeView(data, name, activeTab = "script") {
    const state = data.episode_state || "draft";
    const stateLabel = { draft: "Draft", ready: "Ready", shared: "Shared" };
    const stateColor = { draft: "#ee9b00", ready: "#27ae60", shared: "#0a9396" };
    const isEditable = state !== "shared";

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
        <button class="btn btn-primary" onclick="app.setEpisodeState('${name.replace(/'/g, "\\'")}', 'shared')">Mark as Shared</button>`;
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

    $main().innerHTML = `
      <div class="step-header">
        <h1>${data.name}</h1>
        <p><span style="color:${stateColor[state]}; font-weight:600">${stateLabel[state]}</span></p>
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
    $main().innerHTML = `
      <div class="step-header"><h1>Regenerating Script</h1><p>${name}</p></div>
      <div class="loading-msg"><div class="spinner"></div> Writing a fresh take with the same sources...</div>
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
      $main().innerHTML = `
        <p style="color:var(--danger)">${e.message}</p>
        <div class="actions"><button class="btn btn-primary" onclick="app.viewEpisode('${name.replace(/'/g, "\\'")}')">Back to Episode</button></div>`;
    }
  },

  // ── Theme Bank ──────────────────────────────────────────────────────

  async showThemeBank() {
    $main().innerHTML = `<div class="loading-msg"><div class="spinner"></div> Loading theme bank...</div>`;
    try {
      const res = await fetch("/api/theme-bank");
      const themes = await res.json();
      this._themeBank = themes;
      this.renderThemeBank();
    } catch (e) {
      $main().innerHTML = `<p style="color:var(--danger)">Error loading theme bank: ${e.message}</p>`;
    }
  },

  renderThemeBank() {
    const themes = this._themeBank || [];
    const rows = themes.map(t => {
      const tags = (t.tags || []).join(", ");
      const used = t.times_used > 0
        ? `<span class="ep-badge used" style="font-size:10px">${t.times_used}x · ${t.last_used || '?'}</span>`
        : `<span class="ep-badge fresh" style="font-size:10px">Never used</span>`;
      const esc = t.id.replace(/'/g, "\\'");
      return `
        <div class="source-card" style="display:flex; gap:12px; align-items:flex-start;">
          <div style="flex:1;">
            <h4 id="name-display-${t.id}">${t.name}</h4>
            <div style="font-size:12px; color:var(--text-dim); margin:4px 0;">${t.description}</div>
            <div style="font-size:11px; color:var(--text-dim);">${tags ? 'Tags: ' + tags : ''}</div>
            ${used}
          </div>
          <div style="display:flex; gap:4px; flex-shrink:0;">
            <button class="btn btn-sm btn-secondary" onclick="app.editTheme('${esc}')">Edit</button>
            <button class="btn btn-sm btn-secondary" style="color:var(--danger);" onclick="app.deleteTheme('${esc}')">Delete</button>
          </div>
        </div>`;
    }).join("");

    $main().innerHTML = `
      <div class="step-header">
        <h1>Theme Bank</h1>
        <p>${themes.length} themes. Click Edit to modify, or add a new one below.</p>
      </div>
      ${rows}
      <div class="source-card" style="border-style:dashed;">
        <h4 style="margin-bottom:8px;">Add New Theme</h4>
        <input id="new-theme-name" class="theme-input" placeholder="Theme name" style="margin-top:0; margin-bottom:8px;">
        <input id="new-theme-desc" class="theme-input" placeholder="Description — one sentence about what this theme covers" style="margin-top:0; margin-bottom:8px;">
        <input id="new-theme-tags" class="theme-input" placeholder="Tags (comma-separated)" style="margin-top:0; margin-bottom:8px;">
        <button class="btn btn-sm btn-primary" onclick="app.addTheme()">Add Theme</button>
      </div>
    `;
  },

  async editTheme(themeId) {
    const theme = (this._themeBank || []).find(t => t.id === themeId);
    if (!theme) return;
    const name = prompt("Theme name:", theme.name);
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
    if (!confirm("Delete this theme from the bank?")) return;
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
    if (!name) { alert("Theme name is required."); return; }
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
    $main().innerHTML = `
      <div class="step-header"><h1>Generating Audio</h1><p>${name}</p></div>
      <div class="loading-msg"><div class="spinner"></div> Converting script to audio...</div>
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
      $main().innerHTML = `
        <p style="color:var(--danger)">Audio error: ${e.message}</p>
        <div class="actions"><button class="btn btn-primary" onclick="app.viewEpisode('${name.replace(/'/g, "\\'")}')">Back to Episode</button></div>`;
    }
  },
};

// Boot.
document.addEventListener("DOMContentLoaded", () => app.init());
