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

  async init() {
    await this.loadEpisodes();
  },

  async loadEpisodes() {
    try {
      const res = await fetch("/api/episodes");
      const episodes = await res.json();
      const list = $("#episode-list");
      list.innerHTML = episodes.map(ep => `
        <li onclick="app.viewEpisode('${ep.name.replace(/'/g, "\\'")}')">
          ${ep.name.replace("The Signal – ", "")}
          <span class="ep-date">${ep.status === "success" ? "Completed" : ep.status}</span>
        </li>
      `).join("");
    } catch (e) {
      console.error("Failed to load episodes:", e);
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
    $main().innerHTML = `
      ${this.renderSteps(0)}
      <div class="step-header">
        <h1>Proposing Themes</h1>
        <p>Scanning RSS feeds and theme bank...</p>
      </div>
      <div class="loading-msg"><div class="spinner"></div> Scanning sources and generating theme proposals. This takes about 15 seconds.</div>
    `;

    try {
      const res = await fetch("/api/propose", { method: "POST" });
      const proposals = await res.json();
      this.state.proposals = proposals;
      this.renderProposals();
    } catch (e) {
      $main().innerHTML = `<p style="color:var(--danger)">Error proposing themes: ${e.message}</p>`;
    }
  },

  renderProposals() {
    const cards = this.state.proposals.map((p, i) => `
      <div class="card" onclick="app.selectTheme(${i})">
        <h3>${p.name}</h3>
        <p>${p.pitch}</p>
        <div class="sources">
          ${(p.source_previews || []).map(s => `<span>&#8226; ${s}</span>`).join("")}
        </div>
      </div>
    `).join("");

    $main().innerHTML = `
      ${this.renderSteps(0)}
      <div class="step-header">
        <h1>Pick a Theme</h1>
        <p>Choose one of these themes, or type your own topic below.</p>
      </div>
      ${cards}
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
    $main().innerHTML = `
      ${this.renderSteps(1)}
      <div class="step-header">
        <h1>Researching: ${this.state.selectedTheme}</h1>
        <p>Finding and ranking sources...</p>
      </div>
      <div class="loading-msg"><div class="spinner"></div> Searching RSS feeds and fetching full article text. This takes about 30 seconds.</div>
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
    const cards = this.state.sources.map((s, i) => `
      <div class="source-card ${s.included ? '' : 'excluded'}">
        <div class="source-toggle">
          <input type="checkbox" ${s.included ? 'checked' : ''} onchange="app.toggleSource(${i})">
          <h4>${s.title}</h4>
        </div>
        <div class="meta">${s.source_domain} &middot; ${s.word_count} words${s.published_at ? ' &middot; ' + s.published_at.split('T')[0] : ''}</div>
        <div class="preview" id="preview-${i}">${(s.full_text || s.summary || 'No text available').substring(0, 300)}...</div>
        <button class="btn btn-sm btn-secondary" style="margin-top:8px" onclick="app.togglePreview(${i})">Show more</button>
      </div>
    `).join("");

    const included = this.state.sources.filter(s => s.included).length;

    $main().innerHTML = `
      ${this.renderSteps(1)}
      <div class="step-header">
        <h1>Review Sources</h1>
        <p>${included} sources selected for "${this.state.selectedTheme}". Uncheck any you want to exclude.</p>
      </div>
      ${cards}
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

  togglePreview(index) {
    const el = document.getElementById(`preview-${index}`);
    if (el) {
      el.classList.toggle("expanded");
      const s = this.state.sources[index];
      if (el.classList.contains("expanded")) {
        el.textContent = s.full_text || s.summary || "No text available";
      } else {
        el.textContent = (s.full_text || s.summary || "No text available").substring(0, 300) + "...";
      }
    }
  },

  // ── Step 3: Generate script ─────────────────────────────────────────

  async generateScript() {
    const includedSources = this.state.sources.filter(s => s.included);

    $main().innerHTML = `
      ${this.renderSteps(2)}
      <div class="step-header">
        <h1>Generating Script</h1>
        <p>Writing episode script for "${this.state.selectedTheme}"...</p>
      </div>
      <div class="loading-msg"><div class="spinner"></div> The AI is writing your script. This usually takes 30-60 seconds.</div>
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
    $main().innerHTML = `
      ${this.renderSteps(3)}
      <div class="step-header">
        <h1>Generating Audio</h1>
        <p>Converting script to speech with Fish Audio...</p>
      </div>
      <div class="loading-msg"><div class="spinner"></div> Generating audio. This can take 1-3 minutes depending on script length.</div>
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

      const audioHtml = data.has_audio
        ? `<div class="audio-player">
            <strong>Episode Audio</strong>
            <audio controls src="${data.audio_url}"></audio>
          </div>`
        : '';

      $main().innerHTML = `
        <div class="step-header">
          <h1>${data.name}</h1>
        </div>
        <div class="tabs">
          <button class="tab active" id="tab-script" onclick="app.showViewTab('script', '${name.replace(/'/g, "\\'")}')">Script</button>
          <button class="tab" id="tab-teams" onclick="app.showViewTab('teams', '${name.replace(/'/g, "\\'")}')">Teams Post</button>
          <button class="tab" id="tab-trythis" onclick="app.showViewTab('trythis', '${name.replace(/'/g, "\\'")}')">Try This</button>
        </div>
        <div class="script-display" id="view-content">${data.script || '(No script found)'}</div>
        ${audioHtml}
        <div class="actions" style="margin-top:16px">
          <button class="btn btn-primary" onclick="app.newEpisode()">+ New Episode</button>
        </div>
      `;

      // Stash for tab switching.
      this._viewData = data;
    } catch (e) {
      $main().innerHTML = `<p style="color:var(--danger)">Error loading episode: ${e.message}</p>`;
    }
  },

  showViewTab(tab) {
    const d = this._viewData;
    const content = { script: d.script, teams: d.teams_post, trythis: d.try_this };
    document.getElementById("view-content").textContent = content[tab] || "(empty)";
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.getElementById(`tab-${tab}`).classList.add("active");
  },
};

// Boot.
document.addEventListener("DOMContentLoaded", () => app.init());
