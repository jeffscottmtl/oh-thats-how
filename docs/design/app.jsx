// The Signal — main app
const { useState, useEffect, useMemo, useRef, useCallback } = React;

const D = window.SIGNAL_DATA;
const CoverTemplates = window.CoverTemplates;

// ── Icon set (inline SVG) ───────────────────────────────
const Icon = ({ name, size = 16 }) => {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" };
  const paths = {
    plus: <><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></>,
    search: <><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></>,
    chevronRight: <polyline points="9 6 15 12 9 18"/>,
    chevronLeft: <polyline points="15 6 9 12 15 18"/>,
    check: <polyline points="20 6 9 17 4 12"/>,
    refresh: <><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></>,
    play: <polygon points="5 3 19 12 5 21 5 3"/>,
    pause: <><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></>,
    trash: <><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></>,
    gear: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06A1.65 1.65 0 0 0 15 19.4a1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09A1.65 1.65 0 0 0 15 4.6a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></>,
    dl: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></>,
    fileText: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></>,
    music: <><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></>,
    image: <><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></>,
    send: <><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></>,
    info: <><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></>,
    ext: <><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></>,
    sparkle: <><path d="M12 3v18M3 12h18M6.3 6.3l11.4 11.4M17.7 6.3L6.3 17.7"/></>,
    drag: <><circle cx="9" cy="6" r="1"/><circle cx="15" cy="6" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="9" cy="18" r="1"/><circle cx="15" cy="18" r="1"/></>,
    x: <><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>,
    eye: <><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></>,
    download: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></>,
    book: <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></>,
    copy: <><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></>,
  };
  return <svg {...common}>{paths[name]}</svg>;
};

const STAGES = [
  { id: "theme", label: "Theme" },
  { id: "articles", label: "Articles" },
  { id: "script", label: "Script" },
  { id: "cover", label: "Cover" },
  { id: "audio", label: "Audio" },
  { id: "publish", label: "Publish" },
];

const ACCENT_PALETTE = [
  { name: "CN Red", value: "#ED0500" },
  { name: "Deep Red", value: "#A60200" },
  { name: "Ink", value: "#0B0D10" },
  { name: "Forest", value: "#2E6F4E" },
  { name: "Signal", value: "#2F62D8" },
  { name: "Amber", value: "#E8A93A" },
  { name: "Bone", value: "#DDD7C3" },
];

// ── Topbar ───────────────────────────────────────────────
const Topbar = ({ episode, onToggleDetails, detailsOpen }) => (
  <div className="topbar">
    <div className="brand">
      <span className="brand-mark"><span/></span>
      The Signal
      <span style={{ fontSize: 10, fontFamily: "var(--font-mono)", color: "var(--ink-500)", marginLeft: 6, padding: "2px 5px", background: "var(--ink-100)", borderRadius: 3, letterSpacing: "0.04em" }}>STUDIO</span>
    </div>
    <div className="divider" />
    <div className="crumbs">
      <span>Library</span>
      <span className="sep">/</span>
      <span className="ep-name">{episode.name}</span>
    </div>
    <div className="spacer" />
    <div className="right">
      <span className={`status-pill ${episode.state}`}>
        <span className="dot" />
        {episode.state.charAt(0).toUpperCase() + episode.state.slice(1)}
      </span>
      <button className={`icon-btn ${detailsOpen ? "active" : ""}`} onClick={onToggleDetails} title="Run details">
        <Icon name="info" size={18} />
      </button>
      <button className="icon-btn" title="Settings"><Icon name="gear" size={18} /></button>
      <div style={{ width: 28, height: 28, borderRadius: "50%", background: "var(--cn-red)", color: "white", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 600, marginLeft: 4 }}>
        JS
      </div>
    </div>
  </div>
);

// ── Sidebar ─────────────────────────────────────────────
const Sidebar = ({ episodes, activeId, onSelect }) => {
  const [tab, setTab] = useState("all");
  const [search, setSearch] = useState("");
  const filtered = episodes.filter((e) => {
    if (tab === "drafts" && e.state !== "draft") return false;
    if (tab === "published" && e.state !== "published") return false;
    if (search && !e.name.toLowerCase().includes(search.toLowerCase()) && !(e.theme || "").toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <span className="label">Episodes · {episodes.length}</span>
        <button className="new-ep-btn" title="New episode"><Icon name="plus" size={12}/>New</button>
      </div>
      <div className="sidebar-search">
        <input placeholder="Search episodes or themes…" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      <div className="sidebar-tabs">
        {[["all", "All"], ["drafts", "Drafts"], ["published", "Published"]].map(([k, l]) => (
          <button key={k} className={`sidebar-tab ${tab === k ? "active" : ""}`} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      <div className="episode-list">
        {filtered.map((ep) => (
          <div key={ep.id} className={`ep-row ${ep.id === activeId ? "active" : ""}`} onClick={() => onSelect(ep.id)}>
            <div className="ep-thumb">
              {ep.state === "draft"
                ? <span style={{ color: "var(--ink-400)" }}>—</span>
                : <MiniCover ep={ep} />
              }
            </div>
            <div className="ep-meta">
              <div className="title">{ep.theme || ep.name}</div>
              <div className="sub">
                <span className="mono">Ep. {ep.number}</span>
                <span className="dot" />
                <span>{new Date(ep.date + "T12:00").toLocaleDateString("en-CA", { month: "short", day: "numeric" })}</span>
                {ep.duration && <>
                  <span className="dot" />
                  <span className="mono">{ep.duration}</span>
                </>}
              </div>
            </div>
            <span className={`ep-state-chip ${ep.state}`}>{ep.state}</span>
          </div>
        ))}
      </div>
    </aside>
  );
};

const MiniCover = ({ ep }) => (
  <svg viewBox="0 0 40 40" style={{ width: "100%", height: "100%" }}>
    <rect width="40" height="40" fill="#21262B" />
    <polygon points="0,0 16,0 8,23 0,19" fill="#ED0500" opacity="0.9" />
    <polygon points="19,40 40,26 40,40" fill="#ED0500" opacity="0.5" />
    <rect x="2" y="28" width="36" height="2.5" fill="#ED0500" />
    <text x="20" y="15" fill="white" fontSize="5" fontWeight="700" textAnchor="middle" fontFamily="Inter">{ep.number}</text>
  </svg>
);

// ── Stage rail ──────────────────────────────────────────
const StageRail = ({ current, onGo, progress }) => (
  <div className="stage-rail">
    {STAGES.map((s, i) => {
      const done = progress[s.id] === "done";
      return (
        <button key={s.id} className={`stage-step ${current === s.id ? "active" : ""} ${done ? "done" : ""}`} onClick={() => onGo(s.id)}>
          <span className="num">{done ? <Icon name="check" size={10}/> : i + 1}</span>
          {s.label}
        </button>
      );
    })}
  </div>
);

// ── Stage: Theme ────────────────────────────────────────
const ThemeStage = ({ chosen, onChoose, onCustom, custom, onContinue }) => {
  const [filter, setFilter] = useState("all"); // all | bank | generated
  const [bankOpen, setBankOpen] = useState(false);
  const meta = D.themeBankMeta;

  const daysAgo = (iso) => {
    if (!iso) return null;
    const ms = Date.now() - new Date(iso + "T12:00").getTime();
    return Math.floor(ms / 86400000);
  };

  const proposals = D.themeProposals
    .map((t, i) => ({ ...t, i }))
    .filter((t) => filter === "all" || t.origin === filter);

  return (
    <div className="stage-body">
      <div className="panel-pad" style={{ maxWidth: 1120, width: "100%", margin: "0 auto" }}>
        <div className="hello-head">
          <div>
            <div style={{ fontSize: 11, letterSpacing: "0.12em", color: "var(--ink-500)", fontWeight: 600, marginBottom: 8 }}>STEP 1 · CHOOSE A THEME</div>
            <h1>What's this week's signal?</h1>
            <div className="sub">
              Twenty proposals: pulled from your <strong>theme bank</strong> (ones we haven't shipped in the last {meta.cooldownDays} days),
              plus fresh themes the model generates from this morning's web search. Pick one, or type your own topic — you can override the cooldown if you want a follow-up to a recent episode.
            </div>
          </div>
          <div className="flex gap-2" style={{ alignItems: "center", flexWrap: "wrap", justifyContent: "flex-end" }}>
            <button className="btn outlined btn-sm" onClick={() => setBankOpen(true)}><Icon name="book" size={13}/>Theme bank</button>
            <button className="btn ghost btn-sm"><Icon name="refresh" size={13}/>Regenerate all</button>
          </div>
        </div>

        {/* Run stats strip */}
        <div className="theme-stats">
          <div><span className="k">BANK SIZE</span><span className="v">{meta.bankSize}</span><span className="d">curated themes</span></div>
          <div><span className="k">ELIGIBLE</span><span className="v">{meta.eligibleCount}</span><span className="d">outside {meta.cooldownDays}-day cooldown</span></div>
          <div><span className="k">SEARCH RESULTS</span><span className="v">{meta.resultsScanned}</span><span className="d">from {meta.searchQueries} web queries · {meta.uniqueDomains} unique domains</span></div>
          <div><span className="k">DEDUPED</span><span className="v">{meta.duplicateArticlesSkipped}</span><span className="d">articles skipped · already cited in past episodes</span></div>
        </div>

        {/* Filter */}
        <div className="theme-filter">
          {[
            ["all", "All 20"],
            ["bank", `Bank (${D.themeProposals.filter(t => t.origin === "bank").length})`],
            ["generated", `Fresh from search (${D.themeProposals.filter(t => t.origin === "generated").length})`],
          ].map(([k, l]) => (
            <button key={k} className={`filter-chip ${filter === k ? "active" : ""}`} onClick={() => setFilter(k)}>{l}</button>
          ))}
          <span className="mono" style={{ marginLeft: "auto", fontSize: 11, color: "var(--ink-500)" }}>
            {proposals.length} of 20 showing
          </span>
        </div>

        <div className="theme-grid">
          {proposals.map((t) => {
            const used = daysAgo(t.lastUsed);
            const onCooldown = t.origin === "bank" && used !== null && used <= meta.cooldownDays;
            return (
              <div key={t.i} className={`theme-card ${chosen === t.i ? "selected" : ""} origin-${t.origin} ${onCooldown ? "on-cooldown" : ""}`} onClick={() => onChoose(t.i)}>
                <div className="tc-head">
                  <span className="ix">THEME {String(t.i + 1).padStart(2, "0")}</span>
                  {t.origin === "bank" ? (
                    <span className="tc-tag bank" title={`Bank entry ${t.bankId}`}>
                      <Icon name="book" size={10}/> Bank · {t.bankId}
                    </span>
                  ) : (
                    <span className="tc-tag generated" title="LLM-generated from this morning's web search results">
                      <Icon name="sparkle" size={10}/> Fresh
                    </span>
                  )}
                </div>
                <h3>{t.name}</h3>
                <div className="pitch">{t.pitch}</div>
                <div className="preview-sources">
                  {t.sources.map((s, j) => <span key={j}>{s}</span>)}
                </div>
                <div className="tc-foot">
                  {t.origin === "bank" && (
                    onCooldown ? (
                      <span className="cooldown warn" title="Already aired recently. You can still pick this if you want a follow-up episode.">
                        ⚠ Aired {used}d ago · follow-up OK
                      </span>
                    ) : (
                      <span className="cooldown">
                        {used === null ? "Never aired" : `Last aired ${used}d ago`}
                      </span>
                    )
                  )}
                  {t.origin === "generated" && (
                    <span className="cooldown">Based on {t.sources.length} search result{t.sources.length === 1 ? "" : "s"} from this morning</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <div className="theme-custom">
          <label>Or type your own topic</label>
          <input value={custom} onChange={(e) => onCustom(e.target.value)} placeholder="e.g. How AI is changing the executive briefing note" />
          <button className="btn outlined btn-sm" disabled={!custom || custom.length < 6}>Use topic</button>
        </div>
      </div>
      <FooterActions onNext={onContinue} nextLabel="Find articles" disabled={chosen === null && (!custom || custom.length < 6)} hint={chosen !== null ? `“${D.themeProposals[chosen].name}”` : custom.length >= 6 ? `“${custom}”` : "Pick a theme to continue"} />
      {bankOpen && <ThemeBankModal onClose={() => setBankOpen(false)} />}
    </div>
  );
};

// Theme bank management modal
const ThemeBankModal = ({ onClose }) => {
  // Synthesized bank — mixes proposals + some extras + used ones
  const bank = [
    ...D.themeProposals.filter(t => t.origin === "bank").map(t => ({ id: t.bankId, name: t.name, lastUsed: t.lastUsed, tags: ["audience", "voice"] })),
    { id: "tb-001", name: "AI and your inbox", lastUsed: "2026-04-13", tags: ["daily", "tools"] },
    { id: "tb-002", name: "Meeting notes, automated", lastUsed: "2026-04-06", tags: ["tools"] },
    { id: "tb-005", name: "The prompt as a deliverable", lastUsed: "2026-03-22", tags: ["process"] },
    { id: "tb-010", name: "When to say no to AI", lastUsed: "2026-03-15", tags: ["judgment"] },
    { id: "tb-015", name: "Corporate voice for 50 languages", lastUsed: null, tags: ["scale", "voice"] },
    { id: "tb-020", name: "AI-safe messaging for regulated industries", lastUsed: null, tags: ["compliance"] },
  ];
  const today = new Date();
  const daysSince = (iso) => iso ? Math.floor((today - new Date(iso + "T12:00")) / 86400000) : null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <h2 style={{ margin: 0, fontSize: 20 }}>Theme bank</h2>
            <div style={{ fontSize: 12, color: "var(--ink-600)", marginTop: 2 }}>
              Your curated topic list. Edit here; the pipeline rotates through, respecting the {D.themeBankMeta.cooldownDays}-day cooldown.
            </div>
          </div>
          <button className="icon-btn" onClick={onClose}><Icon name="x" size={15}/></button>
        </div>
        <div className="modal-body">
          <div className="bank-toolbar">
            <button className="btn primary btn-sm"><Icon name="plus" size={13}/>Add entry</button>
            <input placeholder="Search themes…" className="bank-search" />
            <span className="mono" style={{ marginLeft: "auto", fontSize: 11, color: "var(--ink-500)" }}>{bank.length} entries</span>
          </div>
          <table className="bank-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Theme</th>
                <th>Tags</th>
                <th>Last aired</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {bank.map((b) => {
                const d = daysSince(b.lastUsed);
                const onCooldown = d !== null && d <= D.themeBankMeta.cooldownDays;
                return (
                  <tr key={b.id}>
                    <td className="mono" style={{ fontSize: 11, color: "var(--ink-500)" }}>{b.id}</td>
                    <td style={{ fontWeight: 500 }}>{b.name}</td>
                    <td>
                      {b.tags.map(t => <span key={t} className="bank-tag">{t}</span>)}
                    </td>
                    <td style={{ fontSize: 12, color: "var(--ink-600)" }}>
                      {b.lastUsed ? `${b.lastUsed} (${d}d ago)` : <span style={{ color: "var(--ink-400)" }}>never</span>}
                    </td>
                    <td>
                      <span className={`bank-status ${onCooldown ? "cooldown" : "eligible"}`}>
                        {onCooldown ? `Cooldown · ${D.themeBankMeta.cooldownDays - d}d left` : "Eligible"}
                      </span>
                    </td>
                    <td>
                      <button className="icon-btn" style={{ width: 24, height: 24 }}><Icon name="gear" size={13}/></button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// ── Stage: Articles ─────────────────────────────────────
const ArticlesStage = ({ selected, setSelected, onContinue, onBack }) => {
  const [activeIdx, setActiveIdx] = useState(1);
  const [filter, setFilter] = useState("all");
  const [draggingId, setDraggingId] = useState(null);

  const active = D.articles.find((a) => a.idx === activeIdx);
  const filtered = D.articles.filter((a) => {
    if (filter === "selected") return selected.includes(a.idx);
    if (filter === "fresh") return new Date(a.published) > new Date("2026-04-14");
    if (filter === "mainstream") return ["hbr.org", "reuters.com", "theglobeandmail.com", "technologyreview.com", "microsoft.com"].includes(a.source);
    return true;
  }).sort((a, b) => b.scores.total - a.scores.total);

  const toggle = (idx) => {
    if (selected.includes(idx)) setSelected(selected.filter((i) => i !== idx));
    else setSelected([...selected, idx]);
  };

  const move = (from, to) => {
    const next = [...selected];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    setSelected(next);
  };

  return (
    <div className="stage-body" style={{ overflow: "hidden" }}>
      <div className="articles-layout">
        {/* List column */}
        <div className="articles-col">
          <div className="col-head">
            <span className="title">Ranked Articles</span>
            <span className="count mono">{filtered.length} / {D.articles.length}</span>
          </div>
          <div className="filter-row">
            {[["all", "All"], ["fresh", "Last 7 days"], ["mainstream", "Mainstream"], ["selected", "Selected"]].map(([k, l]) => (
              <button key={k} className={`filter-chip ${filter === k ? "active" : ""}`} onClick={() => setFilter(k)}>{l}</button>
            ))}
          </div>
          <div className="article-list">
            {filtered.map((a) => (
              <div key={a.idx}
                className={`article-row ${activeIdx === a.idx ? "active" : ""} ${selected.includes(a.idx) ? "selected" : ""}`}
                onClick={() => setActiveIdx(a.idx)}
              >
                <div className="checkbox" onClick={(e) => { e.stopPropagation(); toggle(a.idx); }} />
                <div className="body">
                  <div className="title">{a.title}</div>
                  <div className="meta">
                    <span className="source">{a.source}</span>
                    <span>{new Date(a.published + "T12:00").toLocaleDateString("en-CA", { month: "short", day: "numeric" })}</span>
                    <span className="score">{a.scores.total.toFixed(1)}</span>
                  </div>
                  <div className="score-bar"><div style={{ width: `${a.scores.total}%` }} /></div>
                </div>
              </div>
            ))}
          </div>
        </div>
        {/* Preview column */}
        <div className="articles-col">
          <div className="col-head">
            <span className="title">Preview</span>
            <span className="count mono">#{String(activeIdx).padStart(2, "0")}</span>
          </div>
          {active && (
            <div className="preview-pane">
              <h2>{active.title}</h2>
              <div className="source-line">
                <span className="mono" style={{ padding: "1px 6px", background: "var(--ink-100)", borderRadius: 3 }}>{active.source}</span>
                <span>·</span>
                <span>{new Date(active.published + "T12:00").toLocaleDateString("en-CA", { year: "numeric", month: "long", day: "numeric" })}</span>
                <span>·</span>
                <a href={active.url} target="_blank" rel="noreferrer">Open <Icon name="ext" size={11}/></a>
              </div>
              <div className="summary">{active.summary}</div>
              <div className="body-text">
                <p>Full text was captured successfully. <span className="muted">({Math.round(active.summary.length * 18 / 6)} words estimated)</span></p>
                <p style={{ color: "var(--ink-600)" }}>This article will be passed to the script writer with its full body preserved. The model is instructed to cite the source naturally in the narrative and avoid verbatim copying.</p>
              </div>
              <div className="score-grid">
                {[
                  ["Credibility", active.scores.credibility],
                  ["Comms relevance", active.scores.commsRelevance],
                  ["Freshness", active.scores.freshness],
                  ["AI materiality", active.scores.aiMateriality],
                  ["Preferred topic", active.scores.preferred],
                  ["Total", active.scores.total.toFixed(1)],
                ].map(([k, v]) => (
                  <React.Fragment key={k}>
                    <div className="label">{k}</div>
                    <div className="value">{v}</div>
                  </React.Fragment>
                ))}
              </div>
              <div className="preview-actions">
                <button className={`btn ${selected.includes(active.idx) ? "danger-ghost" : "primary"}`} onClick={() => toggle(active.idx)}>
                  {selected.includes(active.idx) ? <>Remove from selection</> : <><Icon name="plus" size={13}/>Add to selection</>}
                </button>
                <button className="btn outlined"><Icon name="fileText" size={13}/>Paste full text</button>
              </div>
            </div>
          )}
        </div>
        {/* Lane column */}
        <div className="lane articles-col">
          <div className="col-head">
            <span className="title">Selected · Play Order</span>
            <span className="count mono">{selected.length}</span>
          </div>
          <div className="lane-list">
            {selected.length === 0 ? (
              <div className="lane-empty">
                <div>No articles yet.</div>
                <div style={{ marginTop: 8 }}>Click <span className="kbd">+</span> on any article, or drag from the list.</div>
              </div>
            ) : selected.map((idx, i) => {
              const a = D.articles.find((x) => x.idx === idx);
              return (
                <div key={idx}
                  draggable
                  className={`lane-item ${draggingId === idx ? "dragging" : ""}`}
                  onDragStart={(e) => { setDraggingId(idx); e.dataTransfer.effectAllowed = "move"; }}
                  onDragEnd={() => setDraggingId(null)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    if (draggingId !== null && draggingId !== idx) {
                      const from = selected.indexOf(draggingId);
                      const to = selected.indexOf(idx);
                      move(from, to);
                    }
                  }}
                >
                  <div className="handle"><Icon name="drag" size={11}/></div>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                      <span className="idx">{i + 1}</span>
                      <span style={{ fontSize: 10, color: "var(--ink-500)", fontFamily: "var(--font-mono)" }}>#{a.idx}</span>
                    </div>
                    <h4>{a.title}</h4>
                    <div className="meta">{a.source}</div>
                  </div>
                  <button className="remove" onClick={() => toggle(idx)}><Icon name="x" size={12}/></button>
                </div>
              );
            })}
          </div>
          <div className="lane-footer">
            <div className="stats">
              <span>Predicted runtime</span>
              <span className="num">~{4 + selected.length * 0.4}:{String(Math.round(Math.random() * 30)).padStart(2, "0")} min</span>
            </div>
            <div className="stats">
              <span>Target word count</span>
              <span className="num">{selected.length <= 1 ? "250-350" : selected.length === 2 ? "360-460" : selected.length === 3 ? "500-650" : "580-720"} words</span>
            </div>
            <div className="stats">
              <span>Source diversity</span>
              <span className="num">{new Set(selected.map((i) => D.articles.find((a) => a.idx === i)?.source)).size} domains</span>
            </div>
          </div>
        </div>
      </div>
      <FooterActions onBack={onBack} onNext={onContinue} nextLabel="Generate script" disabled={selected.length < 1} hint={`${selected.length} article${selected.length === 1 ? "" : "s"} in play order`} />
    </div>
  );
};

// ── Stage: Script ───────────────────────────────────────
const ScriptStage = ({ onContinue, onBack }) => {
  const [focused, setFocused] = useState(null);
  const s = D.script;
  const allText = [s.intro, ...s.body.map(b => b.text), s.foodForThought, s.outro].join(" ");
  const wc = allText.split(/\s+/).filter(Boolean).length;
  const target = { min: 580, max: 720 };
  const pct = Math.min(100, (wc / target.max) * 100);
  const inRange = wc >= target.min && wc <= target.max;
  const over = wc > target.max;
  const runtime = (wc / 135).toFixed(2); // ~135 wpm

  const renderText = (txt) => {
    const parts = txt.split(/(\[[^\]]+\]|\*[^*]+\*)/);
    return parts.map((p, i) => {
      if (/^\[.+\]$/.test(p)) return <span key={i} className="tag">{p}</span>;
      if (/^\*.+\*$/.test(p)) return <em key={i}>{p.slice(1, -1)}</em>;
      return <React.Fragment key={i}>{p}</React.Fragment>;
    });
  };

  const section = (key, label, text, citation) => (
    <div className={`script-section ${focused === key ? "focused" : ""}`} onClick={() => setFocused(key)}>
      <div className="label">
        <span>{label}</span>
        {citation && <span className="mono" style={{ padding: "1px 5px", background: "var(--cn-red-50)", color: "var(--cn-red)", borderRadius: 3, fontSize: 9 }}>cites #{citation}</span>}
        <span className="wc" style={{ marginLeft: "auto" }}>{text.split(/\s+/).filter(Boolean).length} words</span>
      </div>
      <div className="content" contentEditable suppressContentEditableWarning>{renderText(text)}</div>
    </div>
  );

  return (
    <div className="stage-body" style={{ overflow: "hidden" }}>
      <div className="script-layout">
        <div className="editor-col">
          <div className="editor-head">
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <span style={{ fontSize: 14, fontWeight: 600 }}>Script</span>
              <span className="mono" style={{ fontSize: 11, color: "var(--ink-500)" }}>Draft · 1 rewrite</span>
            </div>
            <div style={{ flex: 1 }} />
            <div className="meter">
              <span>WORDS</span>
              <span style={{ color: inRange ? "var(--forest)" : over ? "var(--amber)" : "var(--cn-red)", fontWeight: 600 }}>{wc}</span>
              <span style={{ color: "var(--ink-400)" }}>/ {target.min}–{target.max}</span>
            </div>
            <div className={`meter-bar ${inRange ? "in-range" : over ? "over" : ""}`}>
              <div className="target" style={{ left: `${(target.min / target.max) * 100}%`, right: 0 }} />
              <div className="fill" style={{ width: `${pct}%` }} />
            </div>
            <div className="meter">
              <Icon name="music" size={12}/>
              <span className="mono">~{runtime} min</span>
            </div>
            <div style={{ width: 1, height: 20, background: "var(--border)", margin: "0 6px" }} />
            <button className="btn ghost btn-sm"><Icon name="refresh" size={13}/>Regenerate section</button>
            <button className="btn outlined btn-sm"><Icon name="sparkle" size={13}/>Shorten</button>
          </div>
          <div className="editor-body">
            <div className="editor-content">
              {section("intro", "Intro · fixed", s.intro)}
              {s.body.map((b, i) => section(`body-${i}`, b.label, b.text, b.citation))}
              {section("fot", "Food for Thought", s.foodForThought)}
              {section("outro", "Outro · fixed", s.outro)}
            </div>
          </div>
        </div>
        <aside className="inspector">
          <div className="inspector-section">
            <h4>Pacing</h4>
            <div className="inspector-row"><span className="k">Total words</span><span className="v">{wc}</span></div>
            <div className="inspector-row"><span className="k">Target range</span><span className="v">{target.min}–{target.max}</span></div>
            <div className="inspector-row"><span className="k">Runtime @ 135 wpm</span><span className="v">~{runtime} min</span></div>
            <div className="inspector-row"><span className="k">Sentences</span><span className="v">{allText.split(/[.!?]+/).length}</span></div>
            <div className="inspector-row"><span className="k">Rewrite attempts</span><span className="v">1</span></div>
          </div>
          <div className="inspector-section">
            <h4>Voice tags in use</h4>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {["[pause]", "[soft]", "[emphasis]", "[long pause]"].map(t => (
                <span key={t} className="mono" style={{ fontSize: 11, padding: "2px 6px", background: "var(--ink-100)", borderRadius: 3, color: "var(--ink-700)" }}>{t}</span>
              ))}
            </div>
          </div>
          <div className="inspector-section">
            <h4>Cites these sources</h4>
            {D.selectedIndices.map((idx) => {
              const a = D.articles.find(x => x.idx === idx);
              return (
                <div key={idx} className="source-cite">
                  <span className="idx">{idx}</span>
                  <div>
                    <div className="title">{a.title}</div>
                    <div className="domain">{a.source}</div>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="inspector-section">
            <h4>Actions</h4>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <button className="btn outlined btn-sm" style={{ justifyContent: "flex-start" }}><Icon name="refresh" size={13}/>Regenerate entire script</button>
              <button className="btn outlined btn-sm" style={{ justifyContent: "flex-start" }}><Icon name="play" size={13}/>Read aloud preview</button>
              <button className="btn outlined btn-sm" style={{ justifyContent: "flex-start" }}><Icon name="download" size={13}/>Export Markdown</button>
            </div>
          </div>
        </aside>
      </div>
      <FooterActions onBack={onBack} onNext={onContinue} nextLabel="Design cover" hint={`${wc} words · ~${runtime} min`} />
    </div>
  );
};

// ── Stage: Cover ────────────────────────────────────────
const CoverStage = ({ ep, onContinue, onBack }) => {
  const [template, setTemplate] = useState("wave");
  const [accent, setAccent] = useState("#ED0500");
  const [title, setTitle] = useState(ep.theme);
  const [episodeNumber, setEpisodeNumber] = useState(ep.number);
  const [date, setDate] = useState(ep.date);
  const [seed, setSeed] = useState(1);

  const params = { title, date, episodeNumber, accent, theme: title, seed };

  return (
    <div className="stage-body" style={{ overflow: "hidden" }}>
      <div className="cover-layout">
        <div className="cover-stage">
          <div className="cover-frame">
            {CoverTemplates.byId[template](params)}
          </div>
        </div>
        <aside className="cover-inspector">
          <div className="inspector-section">
            <h4>Template</h4>
            <div className="template-grid">
              {CoverTemplates.list.map((t) => (
                <div key={t.id} className={`template-thumb ${template === t.id ? "active" : ""}`} onClick={() => setTemplate(t.id)}>
                  {t.render({ ...params, title: "The Signal", theme: title })}
                  <span className="tlabel">{t.name}</span>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 10, fontSize: 12, color: "var(--ink-600)" }}>
              <strong style={{ fontWeight: 600 }}>{CoverTemplates.list.find(t => t.id === template).name}:</strong>{" "}
              {CoverTemplates.list.find(t => t.id === template).desc}
            </div>
          </div>
          <div className="inspector-section">
            <h4>Content</h4>
            <div className="ctrl-row">
              <label>Theme</label>
              <input value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="ctrl-row">
              <label>Episode</label>
              <input type="number" value={episodeNumber} onChange={(e) => setEpisodeNumber(parseInt(e.target.value) || 1)} />
            </div>
            <div className="ctrl-row">
              <label>Date</label>
              <input type="text" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
          </div>
          <div className="inspector-section">
            <h4>Accent color</h4>
            <div className="swatch-grid">
              {ACCENT_PALETTE.map((c) => (
                <button key={c.value} className={`swatch ${accent === c.value ? "active" : ""}`}
                  style={{ background: c.value }} onClick={() => setAccent(c.value)} title={c.name} />
              ))}
            </div>
            <div style={{ fontSize: 10, color: "var(--ink-500)", fontFamily: "var(--font-mono)", marginTop: 8 }}>{accent.toUpperCase()} · {ACCENT_PALETTE.find(c => c.value === accent)?.name}</div>
          </div>
          {(template === "wave" || template === "grid") && (
            <div className="inspector-section">
              <h4>Variation</h4>
              <div className="ctrl-row">
                <label>Seed</label>
                <input type="range" min="1" max="99" value={seed} onChange={(e) => setSeed(parseInt(e.target.value))} />
                <span className="mono" style={{ fontSize: 11, color: "var(--ink-600)", minWidth: 28, textAlign: "right" }}>{seed}</span>
              </div>
              <button className="btn outlined btn-sm" onClick={() => setSeed(Math.floor(Math.random() * 99) + 1)} style={{ width: "100%" }}>
                <Icon name="refresh" size={12}/>Shuffle
              </button>
            </div>
          )}
          <div className="inspector-section">
            <h4>Export</h4>
            <div className="export-row">
              <button className="export-btn">1:1 · 3000px</button>
              <button className="export-btn">16:9</button>
              <button className="export-btn">Spotify</button>
            </div>
            <button className="btn primary" style={{ width: "100%", marginTop: 10 }}>
              <Icon name="download" size={13}/>Download cover
            </button>
          </div>
        </aside>
      </div>
      <FooterActions onBack={onBack} onNext={onContinue} nextLabel="Render audio" hint={`${CoverTemplates.list.find(t => t.id === template).name} template · ${accent.toUpperCase()}`} />
    </div>
  );
};

// ── Stage: Audio ────────────────────────────────────────
const AudioStage = ({ onContinue, onBack }) => {
  const [playing, setPlaying] = useState(false);
  const [t, setT] = useState(0);
  const [provider, setProvider] = useState("qwen");
  const duration = 302;

  useEffect(() => {
    if (!playing) return;
    const i = setInterval(() => setT((v) => (v >= duration ? 0 : v + 1)), 1000);
    return () => clearInterval(i);
  }, [playing]);

  const bars = Array.from({ length: 160 }, (_, i) => {
    const x = i / 160;
    const amp = Math.abs(Math.sin(x * 18) * Math.cos(x * 4)) * 0.7 + Math.random() * 0.2 + 0.1;
    return amp;
  });

  return (
    <div className="stage-body">
      <div className="audio-body">
        <div className="hello-head">
          <div>
            <div style={{ fontSize: 11, letterSpacing: "0.12em", color: "var(--ink-500)", fontWeight: 600, marginBottom: 8 }}>STEP 5 · NARRATE</div>
            <h1>Render the episode.</h1>
            <div className="sub">Your voice, cloned. The script above becomes a 5-minute MP3 with proper ID3 tags and cover art embedded.</div>
          </div>
        </div>

        <div className="tts-row">
          {[
            { id: "qwen", name: "Qwen Clone · Jeff", desc: "Your voice clone, Mandarin-capable base. Default. 15s render per minute." },
            { id: "fish", name: "Fish Audio S2", desc: "Alternate provider. Slightly faster but less tonal control." },
          ].map((p) => (
            <div key={p.id} className={`tts-card ${provider === p.id ? "active" : ""}`} onClick={() => setProvider(p.id)}>
              <div className="name">{p.name}</div>
              <div className="desc">{p.desc}</div>
            </div>
          ))}
        </div>

        <div className="waveform">
          <svg viewBox="0 0 160 40" preserveAspectRatio="none">
            {bars.map((h, i) => {
              const played = (i / 160) * duration < t;
              return (
                <rect
                  key={i}
                  x={i + 0.2}
                  y={20 - h * 18}
                  width="0.6"
                  height={h * 36}
                  fill={played ? "var(--cn-red)" : "#5A6674"}
                  opacity={played ? 1 : 0.55}
                />
              );
            })}
          </svg>
          <div className="playhead" style={{ left: `${(t / duration) * 100}%` }} />
        </div>

        <div className="audio-controls">
          <button className="big-play" onClick={() => setPlaying(!playing)}>
            <Icon name={playing ? "pause" : "play"} size={18}/>
          </button>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 500 }}>The Signal – April 20, 2026</div>
            <div className="mono" style={{ fontSize: 11, color: "var(--ink-500)" }}>
              {String(Math.floor(t / 60)).padStart(2, "0")}:{String(t % 60).padStart(2, "0")} / 05:02
            </div>
          </div>
          <button className="btn outlined btn-sm"><Icon name="refresh" size={12}/>Re-render</button>
          <button className="btn outlined btn-sm"><Icon name="download" size={12}/>Download MP3</button>
        </div>

        <div style={{ marginTop: 20, padding: 14, background: "var(--ink-50)", border: "1px solid var(--border)", borderRadius: "var(--r-md)", fontSize: 12, color: "var(--ink-600)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ width: 20, height: 20, borderRadius: 4, background: "var(--forest)", color: "white", display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
              <Icon name="check" size={12}/>
            </span>
            <strong style={{ color: "var(--ink-900)", fontSize: 13 }}>Cover art auto-embedded after render</strong>
          </div>
          The selected cover becomes an ID3v2 APIC frame (1400×1400 JPEG, q=85) so the artwork travels with the
          MP3 into Teams, Apple Podcasts, and local players. Plus tags: title, artist (Jeff Scott), album
          (The Signal), track 24, release date 2026-04-20. Voice tags like <span className="mono">[pause]</span>
          {" "}and <span className="mono">[soft]</span> are stripped before synthesis.
        </div>
      </div>
      <FooterActions onBack={onBack} onNext={onContinue} nextLabel="Publish" hint="5:02 · 4.8 MB · qwen" />
    </div>
  );
};

// ── Stage: Publish ──────────────────────────────────────
const PublishStage = ({ onBack }) => {
  const [copied, setCopied] = useState(null);
  const [tryThisMode, setTryThisMode] = useState("inline"); // inline | reply | attachment

  const copyRich = async () => {
    // Simulate; real impl would use ClipboardItem with text/html + text/plain
    try {
      await navigator.clipboard.writeText("(rich HTML copied — paste into Teams)");
      setCopied("rich");
      setTimeout(() => setCopied(null), 1600);
    } catch {}
  };
  const copyMd = async () => {
    try {
      await navigator.clipboard.writeText("# The Signal — April 20, 2026\n\n…");
      setCopied("md");
      setTimeout(() => setCopied(null), 1600);
    } catch {}
  };

  return (
    <div className="stage-body">
      <div className="publish-body">
        <div className="hello-head">
          <div>
            <div style={{ fontSize: 11, letterSpacing: "0.12em", color: "var(--ink-500)", fontWeight: 600, marginBottom: 8 }}>STEP 6 · SHIP IT</div>
            <h1>Grab it and paste.</h1>
            <div className="sub">
              Teams posting over the network is blocked for us, so we export it in the format Teams pastes cleanly.
              Rich text goes straight into the composer with formatting preserved; everything else is in the zip.
            </div>
          </div>
        </div>

        {/* Primary share surface */}
        <div className="share-primary">
          <div className="share-head">
            <div>
              <div className="k">TEAMS POST · ready to paste</div>
              <div className="v">Hit <span className="mono">Copy for Teams</span>, switch to the CN GPT channel, and paste.</div>
            </div>
            <div className="share-actions">
              <button className={`btn primary btn-lg ${copied === "rich" ? "copied" : ""}`} onClick={copyRich}>
                <Icon name={copied === "rich" ? "check" : "copy"} size={14}/>
                {copied === "rich" ? "Copied — paste now" : "Copy for Teams (rich text)"}
              </button>
              <button className="btn outlined btn-sm" onClick={copyMd}>
                <Icon name={copied === "md" ? "check" : "fileText"} size={13}/>
                {copied === "md" ? "Copied" : "Copy as Markdown"}
              </button>
            </div>
          </div>

          <div className="teams-preview">
            <div className="handle">
              <span className="av">JS</span>
              <span style={{ fontWeight: 600, color: "var(--ink-900)" }}>Jeff Scott</span>
              <span style={{ color: "var(--ink-500)" }}>· CN GPT Channel · preview</span>
              <span style={{ color: "var(--ink-400)", marginLeft: "auto", fontFamily: "var(--font-mono)", fontSize: 11 }}>preview</span>
            </div>
            <div style={{ fontSize: 15 }}>🎙️ <strong>New episode of The Signal — April 20, 2026</strong></div>
            <div style={{ marginTop: 8 }}>This week: <strong>Same message, different audience</strong></div>
            <div style={{ marginTop: 12 }}><strong>In this episode</strong></div>
            <ul style={{ margin: "6px 0 0 0", paddingLeft: 20 }}>
              <li>Why AI can help you adapt one core message to three very different audiences</li>
              <li>How to coach your tool on your corporate voice without losing yours</li>
              <li>A simple prompt framework to try this week</li>
            </ul>
            <div style={{ marginTop: 14, padding: "12px 14px", borderLeft: "3px solid var(--cn-red)", background: "var(--cn-red-50)", borderRadius: "0 6px 6px 0" }}>
              <div style={{ fontWeight: 600, fontSize: 13, color: "var(--cn-red)", marginBottom: 6 }}>💡 Try this week</div>
              <div style={{ fontSize: 13, color: "var(--ink-800)" }}>
                Take one executive-level message you wrote this month. Ask CN GPT to rewrite it for
                <strong> your frontline team </strong>and for<strong> a skeptical peer in finance</strong>.
                Compare all three. Keep the version that sounds most like you — use its edits as a style prompt for next time.
              </div>
            </div>
            <div style={{ marginTop: 14, color: "var(--ink-700)" }}>🎧 <strong>Listen:</strong> episode24.mp3 attached below. Questions or pushback — drop a reply.</div>
          </div>

          <div className="share-note">
            <Icon name="info" size={13}/>
            <span>
              Formatting preserved: headings, bold, bullets, the red <strong>Try this</strong> callout, and a thumbnail of the cover.
              Audio + cover attach when you paste into the Teams composer.
            </span>
          </div>
        </div>

        {/* Try This placement */}
        <div className="block-head">
          <h3>Where does "Try this" live?</h3>
          <span className="mono">{tryThisMode === "inline" ? "recommended" : "alternate"}</span>
        </div>
        <div className="try-this-picker">
          {[
            { id: "inline", t: "Inline callout", d: "Red-accent block at the bottom of the main post. Highest reach, keeps everything in one message.", reach: "every viewer" },
            { id: "reply", t: "Threaded reply", d: "Main post stays scannable; Try this drops as the first reply. Good when the prompt is long.", reach: "thread openers" },
            { id: "attachment", t: "Attachment only", d: "Ships in the zip as try-this.html + .md. Cleanest post, lowest discoverability.", reach: "click-through only" },
          ].map((o) => (
            <div key={o.id} className={`try-option ${tryThisMode === o.id ? "active" : ""}`} onClick={() => setTryThisMode(o.id)}>
              <div className="t">{o.t}</div>
              <div className="d">{o.d}</div>
              <div className="r"><span>reach · </span>{o.reach}</div>
            </div>
          ))}
        </div>

        {/* Download bundle */}
        <div className="block-head">
          <h3>Download bundle</h3>
          <button className="btn primary btn-sm"><Icon name="download" size={13}/>Download all (.zip)</button>
        </div>
        <div className="artifact-grid">
          {[
            { icon: "music", name: "episode-24.mp3", size: "4.8 MB · 5:02 · cover embedded", badge: "APIC" },
            { icon: "image", name: "cover.png", size: "1.1 MB · 3000×3000" },
            { icon: "image", name: "cover-1400.jpg", size: "186 KB · 1400×1400 · Spotify-ready" },
            { icon: "fileText", name: "teams-post.html", size: "8.2 KB · paste-ready", badge: "HTML" },
            { icon: "fileText", name: "teams-post.md", size: "1.4 KB" },
            { icon: "fileText", name: "try-this.html", size: "2.1 KB" },
            { icon: "fileText", name: "script.md", size: "817 words" },
            { icon: "fileText", name: "sources.json", size: "4 cited · 12 scanned" },
          ].map((a) => (
            <div key={a.name} className="artifact">
              <div className="icon"><Icon name={a.icon} size={16}/></div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="name">
                  {a.name}
                  {a.badge && <span className="fmt-badge">{a.badge}</span>}
                </div>
                <div className="size">{a.size}</div>
              </div>
              <button className="icon-btn" title={`Download ${a.name}`}><Icon name="download" size={15}/></button>
            </div>
          ))}
        </div>

        {/* Checklist */}
        <div className="block-head" style={{ marginTop: 24 }}>
          <h3>Publish checklist</h3>
        </div>
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--r-md)", padding: "14px 16px" }}>
          {[
            ["Script reviewed and accepted", true],
            ["Word count within target (817 / 580–720)", false],
            ["Audio rendered (qwen · Jeff clone)", true],
            ["Cover art embedded in MP3 (ID3v2 · APIC · 1400×1400 JPEG)", true],
            ["Teams-post HTML validated (pastes into Teams without strip)", true],
            ["Episode number incremented (24 → 25 on next run)", true],
            ["Zip archive bundled", true],
          ].map(([label, ok]) => (
            <div key={label} style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 0", fontSize: 13 }}>
              <span style={{ width: 18, height: 18, borderRadius: "50%", background: ok ? "var(--forest)" : "var(--amber)", color: "white", display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
                <Icon name={ok ? "check" : "info"} size={11}/>
              </span>
              <span style={{ color: ok ? "var(--ink-800)" : "var(--ink-700)" }}>{label}</span>
              {!ok && <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--amber-ink, #8A5D00)", fontFamily: "var(--font-mono)" }}>over by 97 words — OK to publish</span>}
            </div>
          ))}
        </div>
      </div>
      <FooterActions onBack={onBack} hint="Bundle ready · paste to ship" />
    </div>
  );
};

// ── Footer action bar ──────────────────────────────────
const FooterActions = ({ onBack, onNext, nextLabel, disabled, hint }) => (
  <div className="footer-actions">
    {onBack && <button className="btn ghost" onClick={onBack}><Icon name="chevronLeft" size={14}/>Back</button>}
    <span className="hint">{hint}</span>
    <div style={{ flex: 1 }} />
    {onNext && (
      <button className="btn primary btn-lg" onClick={onNext} disabled={disabled}>
        {nextLabel} <Icon name="chevronRight" size={14}/>
      </button>
    )}
  </div>
);

// ── Details drawer ─────────────────────────────────────
const DetailsDrawer = ({ onClose }) => (
  <div className="details-drawer">
    <div className="dh">
      <span>Run details</span>
      <button className="icon-btn" onClick={onClose} style={{ width: 22, height: 22 }}><Icon name="x" size={13}/></button>
    </div>
    <div className="dc">
      {Object.entries(D.telemetry).map(([k, v]) => (
        <div key={k} className="telemetry-row">
          <span className="k">{k}</span>
          <span className="v">{v}</span>
        </div>
      ))}
    </div>
  </div>
);

// ── Tweaks panel ───────────────────────────────────────
const TWEAKS_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#ED0500",
  "paper": "#FDFCF9",
  "font": "Inter Tight"
}/*EDITMODE-END*/;

const TweaksPanel = ({ open, onClose, tweaks, setTweak }) => (
  <div className={`tweaks-panel ${open ? "open" : ""}`}>
    <div className="h">
      <span>Tweaks</span>
      <button className="icon-btn" onClick={onClose} style={{ width: 22, height: 22 }}><Icon name="x" size={12}/></button>
    </div>
    <div className="c">
      <div className="row">
        <label>Accent</label>
        <select value={tweaks.accent} onChange={(e) => setTweak("accent", e.target.value)}>
          {ACCENT_PALETTE.map(c => <option key={c.value} value={c.value}>{c.name}</option>)}
        </select>
      </div>
      <div className="row">
        <label>Paper</label>
        <select value={tweaks.paper} onChange={(e) => setTweak("paper", e.target.value)}>
          <option value="#FDFCF9">Warm white</option>
          <option value="#FFFFFF">Pure white</option>
          <option value="#F4F6F8">Cool grey</option>
          <option value="#F6F4EE">Bone</option>
        </select>
      </div>
      <div className="row">
        <label>Type</label>
        <select value={tweaks.font} onChange={(e) => setTweak("font", e.target.value)}>
          <option value="Inter Tight">Inter Tight</option>
          <option value="Inter">Inter</option>
          <option value="IBM Plex Sans">IBM Plex Sans</option>
        </select>
      </div>
    </div>
  </div>
);

// ── App root ───────────────────────────────────────────
const App = () => {
  const persistKey = "signal-app-v1";
  const saved = (() => { try { return JSON.parse(localStorage.getItem(persistKey) || "{}"); } catch { return {}; } })();

  const [activeEpId, setActiveEpId] = useState(saved.activeEpId || "ep-24");
  const [stage, setStage] = useState(saved.stage || "articles");
  const [selectedTheme, setSelectedTheme] = useState(saved.selectedTheme ?? 0);
  const [customTheme, setCustomTheme] = useState(saved.customTheme || "");
  const [selectedArticles, setSelectedArticles] = useState(saved.selectedArticles || D.selectedIndices);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [tweaksOpen, setTweaksOpen] = useState(false);
  const [tweaks, setTweaks] = useState({ ...TWEAKS_DEFAULTS, ...(saved.tweaks || {}) });

  useEffect(() => {
    localStorage.setItem(persistKey, JSON.stringify({ activeEpId, stage, selectedTheme, customTheme, selectedArticles, tweaks }));
  }, [activeEpId, stage, selectedTheme, customTheme, selectedArticles, tweaks]);

  // Apply tweaks
  useEffect(() => {
    document.documentElement.style.setProperty("--cn-red", tweaks.accent);
    document.documentElement.style.setProperty("--paper", tweaks.paper);
    document.documentElement.style.setProperty("--font-sans", `"${tweaks.font}", ui-sans-serif, system-ui, sans-serif`);
  }, [tweaks]);

  // Tweaks handshake
  useEffect(() => {
    const handler = (e) => {
      if (e.data?.type === "__activate_edit_mode") setTweaksOpen(true);
      if (e.data?.type === "__deactivate_edit_mode") setTweaksOpen(false);
    };
    window.addEventListener("message", handler);
    window.parent.postMessage({ type: "__edit_mode_available" }, "*");
    return () => window.removeEventListener("message", handler);
  }, []);

  const setTweak = (k, v) => {
    setTweaks((prev) => {
      const next = { ...prev, [k]: v };
      window.parent.postMessage({ type: "__edit_mode_set_keys", edits: { [k]: v } }, "*");
      return next;
    });
  };

  const ep = D.episodes.find(e => e.id === activeEpId) || D.episodes[0];

  const progress = useMemo(() => {
    const order = ["theme", "articles", "script", "cover", "audio", "publish"];
    const i = order.indexOf(stage);
    return Object.fromEntries(order.map((s, idx) => [s, idx < i ? "done" : idx === i ? "current" : "todo"]));
  }, [stage]);

  const go = (s) => setStage(s);
  const next = () => {
    const order = STAGES.map(s => s.id);
    const i = order.indexOf(stage);
    if (i < order.length - 1) setStage(order[i + 1]);
  };
  const back = () => {
    const order = STAGES.map(s => s.id);
    const i = order.indexOf(stage);
    if (i > 0) setStage(order[i - 1]);
  };

  return (
    <div className="app">
      <Topbar episode={ep} onToggleDetails={() => setDetailsOpen(v => !v)} detailsOpen={detailsOpen} />
      <Sidebar episodes={D.episodes} activeId={activeEpId} onSelect={setActiveEpId} />
      <main className="workspace">
        <StageRail current={stage} onGo={go} progress={progress} />
        {stage === "theme" && <ThemeStage chosen={selectedTheme} onChoose={setSelectedTheme} onCustom={setCustomTheme} custom={customTheme} onContinue={next} />}
        {stage === "articles" && <ArticlesStage selected={selectedArticles} setSelected={setSelectedArticles} onContinue={next} onBack={back} />}
        {stage === "script" && <ScriptStage onContinue={next} onBack={back} />}
        {stage === "cover" && <CoverStage ep={ep} onContinue={next} onBack={back} />}
        {stage === "audio" && <AudioStage onContinue={next} onBack={back} />}
        {stage === "publish" && <PublishStage onBack={back} />}
        {detailsOpen && <DetailsDrawer onClose={() => setDetailsOpen(false)} />}
      </main>
      <TweaksPanel open={tweaksOpen} onClose={() => setTweaksOpen(false)} tweaks={tweaks} setTweak={setTweak} />
    </div>
  );
};

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
