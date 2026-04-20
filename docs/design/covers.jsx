// Cover templates — parametric SVG generators
// Each template takes { title, date, episodeNumber, accent, theme, seed } and returns JSX.

const CoverTemplates = (() => {
  const fmt = {
    date: (iso) => {
      const d = new Date(iso + "T12:00:00");
      return d.toLocaleDateString("en-CA", { year: "numeric", month: "long", day: "numeric" });
    },
  };

  // Deterministic PRNG from string seed
  const mulberry32 = (seed) => {
    let t = seed + 0x6D2B79F5;
    return () => {
      t = (t + 0x6D2B79F5) | 0;
      let r = Math.imul(t ^ (t >>> 15), 1 | t);
      r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
      return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
  };
  const hashStr = (s) => {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
    return h >>> 0;
  };

  // ── Template 1: Classic (current Python-generated style) ──
  const Classic = (p) => (
    <svg viewBox="0 0 1000 1000" xmlns="http://www.w3.org/2000/svg" style={{ display: "block", width: "100%", height: "100%" }}>
      <defs>
        <linearGradient id="bg1" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#21262B" />
          <stop offset="100%" stopColor="#111418" />
        </linearGradient>
      </defs>
      <rect width="1000" height="1000" fill="url(#bg1)" />
      <polygon points="0,0 400,0 217,567 0,467" fill={p.accent} opacity="0.88" />
      <polygon points="467,1000 1000,650 1000,1000" fill={p.accent} opacity="0.55" />
      <rect x="60" y="707" width="880" height="54" fill={p.accent} />
      <text x="66" y="235" fill="white" fontSize="120" fontWeight="800" fontFamily="Inter, sans-serif" letterSpacing="-0.02em">The Signal</text>
      <text x="68" y="295" fill="#E8ECF0" fontSize="29" fontFamily="Inter, sans-serif" fontWeight="500">Weekly AI and Communications Brief</text>
      <rect x="770" y="70" width="168" height="52" rx="7" fill={p.accent} />
      <text x="792" y="105" fill="white" fontSize="22" fontFamily="Inter, sans-serif" fontWeight="700">Episode {p.episodeNumber}</text>
      <text x="66" y="850" fill="white" fontSize="34" fontFamily="Inter, sans-serif" fontWeight="400">{fmt.date(p.date)}</text>
    </svg>
  );

  // ── Template 2: Editorial — typographic, light, serif title, theme-driven ──
  const Editorial = (p) => {
    const title = p.theme || "The Signal";
    const words = title.split(" ");
    return (
      <svg viewBox="0 0 1000 1000" xmlns="http://www.w3.org/2000/svg" style={{ display: "block", width: "100%", height: "100%" }}>
        <rect width="1000" height="1000" fill="#F6F4EE" />
        <rect x="0" y="0" width="1000" height="62" fill={p.accent} />
        <text x="50" y="42" fill="white" fontSize="22" fontFamily="Inter, sans-serif" fontWeight="700" letterSpacing="0.18em">THE SIGNAL</text>
        <text x="950" y="42" fill="white" fontSize="22" fontFamily="Inter, sans-serif" fontWeight="500" textAnchor="end" letterSpacing="0.1em">Nº {String(p.episodeNumber).padStart(3, "0")}</text>
        <line x1="50" y1="130" x2="950" y2="130" stroke="#0B0D10" strokeWidth="1" />
        <text x="50" y="120" fill="#7A8593" fontSize="18" fontFamily="Inter, sans-serif" letterSpacing="0.14em" textTransform="uppercase">WEEKLY — {fmt.date(p.date).toUpperCase()}</text>
        <foreignObject x="50" y="180" width="900" height="620">
          <div xmlns="http://www.w3.org/1999/xhtml" style={{ fontFamily: "'Instrument Serif', Georgia, serif", fontSize: "102px", lineHeight: 1.02, color: "#0B0D10", fontWeight: 400, letterSpacing: "-0.02em", textWrap: "balance" }}>
            {title}
          </div>
        </foreignObject>
        <line x1="50" y1="840" x2="950" y2="840" stroke="#0B0D10" strokeWidth="1" />
        <text x="50" y="895" fill="#0B0D10" fontSize="20" fontFamily="Inter, sans-serif" fontWeight="500" letterSpacing="0.1em">AI & COMMUNICATIONS · CN</text>
        <text x="950" y="895" fill="#0B0D10" fontSize="20" fontFamily="Inter, sans-serif" fontWeight="500" textAnchor="end">5 min read · 4 sources</text>
        <circle cx="950" cy="940" r="4" fill={p.accent} />
        <circle cx="925" cy="940" r="4" fill="#0B0D10" />
      </svg>
    );
  };

  // ── Template 3: Signal Wave — generative data-viz, theme-driven wave ──
  const Wave = (p) => {
    const rng = mulberry32(hashStr(p.theme || "signal"));
    const rows = 7;
    const cols = 48;
    const lines = [];
    for (let r = 0; r < rows; r++) {
      const pts = [];
      const rowSeed = rng();
      const amp = 12 + rng() * 24;
      const freq = 0.8 + rng() * 1.8;
      const phase = rng() * Math.PI * 2;
      const yBase = 620 + r * 42 - rng() * 10;
      for (let c = 0; c <= cols; c++) {
        const x = 60 + (c / cols) * 880;
        const fall = Math.sin((c / cols) * Math.PI * freq + phase + rowSeed) * amp;
        const pulse = Math.exp(-Math.pow((c / cols - 0.6), 2) * 6) * 30;
        const y = yBase + fall + pulse * (r / rows);
        pts.push(`${x},${y}`);
      }
      lines.push(
        <polyline
          key={r}
          points={pts.join(" ")}
          fill="none"
          stroke={r < 3 ? p.accent : "#0B0D10"}
          strokeWidth={r < 3 ? 3 : 1.5}
          opacity={r < 3 ? 0.95 : 0.35}
        />
      );
    }
    return (
      <svg viewBox="0 0 1000 1000" xmlns="http://www.w3.org/2000/svg" style={{ display: "block", width: "100%", height: "100%" }}>
        <rect width="1000" height="1000" fill="#FDFCF9" />
        <text x="60" y="150" fill="#0B0D10" fontSize="140" fontFamily="'Instrument Serif', Georgia, serif" fontWeight="400" letterSpacing="-0.02em">The Signal</text>
        <rect x="60" y="180" width="110" height="3" fill={p.accent} />
        <text x="60" y="230" fill="#5A6674" fontSize="22" fontFamily="Inter, sans-serif" fontWeight="500" letterSpacing="0.08em">EPISODE {p.episodeNumber} · {fmt.date(p.date).toUpperCase()}</text>
        <foreignObject x="60" y="290" width="880" height="240">
          <div xmlns="http://www.w3.org/1999/xhtml" style={{ fontFamily: "Inter, sans-serif", fontSize: "54px", lineHeight: 1.1, color: "#0B0D10", fontWeight: 600, letterSpacing: "-0.01em", textWrap: "balance" }}>
            {p.theme || "Untitled"}
          </div>
        </foreignObject>
        {lines}
        <text x="940" y="950" fill="#5A6674" fontSize="18" fontFamily="'JetBrains Mono', monospace" textAnchor="end">AI + COMMS · CN</text>
      </svg>
    );
  };

  // ── Template 4: Grid — geometric, modular, punchy color ──
  const Grid = (p) => {
    const rng = mulberry32(hashStr(p.theme || "grid") ^ (p.seed || 0));
    const cells = [];
    const cols = 6, rows = 6;
    const cellW = 880 / cols, cellH = 420 / rows;
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const r = rng();
        const fill =
          r < 0.5 ? "transparent" :
          r < 0.7 ? p.accent :
          r < 0.88 ? "#0B0D10" :
          "#FDFCF9";
        const stroke = fill === "transparent" ? "#0B0D10" : "none";
        cells.push(
          <rect key={`${x}-${y}`}
            x={60 + x * cellW}
            y={540 + y * cellH}
            width={cellW}
            height={cellH}
            fill={fill}
            stroke={stroke}
            strokeWidth="1.5"
          />
        );
      }
    }
    return (
      <svg viewBox="0 0 1000 1000" xmlns="http://www.w3.org/2000/svg" style={{ display: "block", width: "100%", height: "100%" }}>
        <rect width="1000" height="1000" fill="#FDFCF9" />
        <text x="60" y="180" fill="#0B0D10" fontSize="130" fontFamily="Inter, sans-serif" fontWeight="900" letterSpacing="-0.03em">The Signal</text>
        <foreignObject x="60" y="220" width="800" height="300">
          <div xmlns="http://www.w3.org/1999/xhtml" style={{ fontFamily: "Inter, sans-serif", fontSize: "44px", lineHeight: 1.08, color: p.accent, fontWeight: 700, letterSpacing: "-0.015em", textWrap: "balance" }}>
            {p.theme || "Untitled"}
          </div>
        </foreignObject>
        {cells}
        <rect x="780" y="70" width="160" height="54" fill="#0B0D10" />
        <text x="860" y="106" fill="white" fontSize="24" fontFamily="'JetBrains Mono', monospace" fontWeight="700" textAnchor="middle">EP.{String(p.episodeNumber).padStart(3, "0")}</text>
        <text x="60" y="960" fill="#5A6674" fontSize="20" fontFamily="'JetBrains Mono', monospace" letterSpacing="0.1em">{fmt.date(p.date).toUpperCase()} · CN</text>
      </svg>
    );
  };

  // ── Template 5: Ribbon — single bold typographic statement, CN red cut ──
  const Ribbon = (p) => {
    const title = p.theme || "The Signal";
    return (
      <svg viewBox="0 0 1000 1000" xmlns="http://www.w3.org/2000/svg" style={{ display: "block", width: "100%", height: "100%" }}>
        <defs>
          <clipPath id="ribbonClip">
            <polygon points="0,560 1000,480 1000,720 0,800" />
          </clipPath>
        </defs>
        <rect width="1000" height="1000" fill="#F6F4EE" />
        <polygon points="0,560 1000,480 1000,720 0,800" fill={p.accent} />
        <foreignObject x="60" y="90" width="880" height="400">
          <div xmlns="http://www.w3.org/1999/xhtml" style={{ fontFamily: "'Instrument Serif', Georgia, serif", fontSize: "128px", lineHeight: 0.98, color: "#0B0D10", fontWeight: 400, letterSpacing: "-0.025em", textWrap: "balance" }}>
            {title}
          </div>
        </foreignObject>
        <g clipPath="url(#ribbonClip)">
          <foreignObject x="60" y="90" width="880" height="400">
            <div xmlns="http://www.w3.org/1999/xhtml" style={{ fontFamily: "'Instrument Serif', Georgia, serif", fontSize: "128px", lineHeight: 0.98, color: "#FDFCF9", fontWeight: 400, letterSpacing: "-0.025em", textWrap: "balance" }}>
              {title}
            </div>
          </foreignObject>
        </g>
        <text x="60" y="870" fill="#0B0D10" fontSize="22" fontFamily="Inter, sans-serif" fontWeight="700" letterSpacing="0.14em">THE SIGNAL · EPISODE {p.episodeNumber}</text>
        <text x="60" y="910" fill="#5A6674" fontSize="20" fontFamily="Inter, sans-serif" fontWeight="500">AI & Communications Brief · {fmt.date(p.date)}</text>
        <circle cx="940" cy="890" r="12" fill={p.accent} />
      </svg>
    );
  };

  // ── Template 6: Monolith — big number, minimalist, swiss ──
  const Monolith = (p) => (
    <svg viewBox="0 0 1000 1000" xmlns="http://www.w3.org/2000/svg" style={{ display: "block", width: "100%", height: "100%" }}>
      <rect width="1000" height="1000" fill="#0B0D10" />
      <text x="60" y="860" fill="white" fontSize="560" fontFamily="Inter, sans-serif" fontWeight="900" letterSpacing="-0.05em">{String(p.episodeNumber).padStart(2, "0")}</text>
      <rect x="60" y="80" width="4" height="80" fill={p.accent} />
      <text x="80" y="115" fill="white" fontSize="24" fontFamily="Inter, sans-serif" fontWeight="700" letterSpacing="0.22em">THE SIGNAL</text>
      <text x="80" y="150" fill="#A0A9B5" fontSize="16" fontFamily="Inter, sans-serif" fontWeight="500" letterSpacing="0.08em">AI AND COMMUNICATIONS BRIEF</text>
      <foreignObject x="60" y="200" width="880" height="360">
        <div xmlns="http://www.w3.org/1999/xhtml" style={{ fontFamily: "'Instrument Serif', Georgia, serif", fontSize: "72px", lineHeight: 1.05, color: p.accent, fontWeight: 400, letterSpacing: "-0.02em", textWrap: "balance" }}>
          {p.theme || "Untitled"}
        </div>
      </foreignObject>
      <text x="940" y="940" fill="white" fontSize="18" fontFamily="'JetBrains Mono', monospace" textAnchor="end" letterSpacing="0.08em">{fmt.date(p.date).toUpperCase()}</text>
    </svg>
  );

  return {
    list: [
      { id: "classic", name: "Classic", desc: "The original — matches your current template", render: Classic },
      { id: "editorial", name: "Editorial", desc: "Serif title, light paper, magazine-feel", render: Editorial },
      { id: "wave", name: "Signal Wave", desc: "Generative waveform driven by the theme text", render: Wave },
      { id: "grid", name: "Grid", desc: "Modular geometric composition, bold sans", render: Grid },
      { id: "ribbon", name: "Ribbon", desc: "Typographic — the theme IS the artwork", render: Ribbon },
      { id: "monolith", name: "Monolith", desc: "Big number, dark, minimalist, swiss", render: Monolith },
    ],
    byId: {
      classic: Classic, editorial: Editorial, wave: Wave, grid: Grid, ribbon: Ribbon, monolith: Monolith,
    },
  };
})();

window.CoverTemplates = CoverTemplates;
