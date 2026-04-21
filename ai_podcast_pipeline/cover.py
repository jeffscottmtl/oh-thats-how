from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .artifacts import format_episode_date
from .constants import TIMEZONE

logger = logging.getLogger(__name__)

# Colour values from the CN identity guides:
# CN Red (Pantone 485 CVC) via extracted CMYK approximation.
# Petroleum Black via RGB values found in the guide PDF metadata.
CN_RED = (237, 5, 0)
CN_PETROLEUM_BLACK = (33, 38, 43)
CN_BLACK_DEEP = (17, 20, 24)
CN_WHITE = (255, 255, 255)
CN_LIGHT = (232, 236, 240)


def _blend(
    a: tuple[int, int, int],
    b: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    """Linear interpolate between two RGB tuples. t=0 → a, t=1 → b."""
    return (
        int(a[0] * (1.0 - t) + b[0] * t),
        int(a[1] * (1.0 - t) + b[1] * t),
        int(a[2] * (1.0 - t) + b[2] * t),
    )


def _font_candidates(style: str) -> tuple[str, ...]:
    home_fonts = Path.home() / "Library" / "Fonts"
    averta_files = {
        "regular": "Intelligent Design - Averta-Regular.otf",
        "semibold": "Intelligent Design - Averta-Semibold.otf",
        "bold": "Intelligent Design - Averta-Bold.otf",
        "extrabold": "Intelligent Design - Averta-ExtraBold.otf",
    }
    preferred = home_fonts / averta_files.get(style, averta_files["regular"])
    return (
        str(preferred),
        # macOS system fonts
        "/System/Library/Fonts/Supplemental/HelveticaNeue.ttc",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        # Linux common fonts
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    )


def _load_font(size: int, style: str):
    from PIL import ImageFont

    for name in _font_candidates(style):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    logger.debug("No preferred font found for style=%s; using PIL default.", style)
    return ImageFont.load_default()


def render_cover(
    episode_name: str,
    episode_dt: datetime,
    output_path: Path,
    episode_number: int,
    theme_name: str = "",
) -> None:
    """Render a 3000×3000 PNG cover with the Signal Wave design.

    Light warm background, serif title, theme-driven generative wave
    pattern in CN Red + dark ink, episode info, and theme title.
    """
    import math
    from PIL import Image, ImageDraw

    dt = episode_dt.astimezone(ZoneInfo(TIMEZONE))
    logger.debug("Rendering cover for episode %d ('%s')…", episode_number, episode_name)

    W = 3000
    H = 3000
    PAPER = (253, 252, 249)      # warm off-white
    INK = (11, 13, 16)           # near-black
    INK_MID = (90, 102, 116)     # grey for meta text
    RED = CN_RED

    im = Image.new("RGB", (W, H), color=PAPER)
    draw = ImageDraw.Draw(im)

    # Fonts.
    title_font = _load_font(420, "extrabold")
    meta_font = _load_font(66, "semibold")
    theme_font = _load_font(160, "bold")
    footer_font = _load_font(54, "regular")

    # ── Title: "The Signal" ──
    draw.text((180, 240), "The Signal", fill=INK, font=title_font)

    # Red accent bar under title.
    draw.rectangle([(180, 560), (510, 569)], fill=RED)

    # ── Episode + date meta line ──
    date_line = format_episode_date(dt)
    meta_text = f"EPISODE {episode_number}  ·  {date_line.upper()}"
    draw.text((180, 620), meta_text, fill=INK_MID, font=meta_font)

    # ── Theme title ──
    if theme_name:
        # Word-wrap the theme title.
        words = theme_name.split()
        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), test, font=theme_font)
            if bbox[2] - bbox[0] > 2640:
                lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)
        y = 820
        for line in lines[:3]:  # max 3 lines
            draw.text((180, y), line, fill=INK, font=theme_font)
            y += 180

    # ── Signal wave pattern (theme-driven) ──
    # Deterministic seed from theme name.
    seed_val = sum(ord(c) for c in (theme_name or "signal"))
    import random
    rng = random.Random(seed_val)

    rows = 7
    cols = 48
    wave_y_start = 1860
    row_spacing = 126

    for r in range(rows):
        amp = 36 + rng.random() * 72
        freq = 0.8 + rng.random() * 1.8
        phase = rng.random() * math.pi * 2
        row_seed = rng.random()
        y_base = wave_y_start + r * row_spacing - rng.random() * 30

        points = []
        for c in range(cols + 1):
            x = 180 + (c / cols) * 2640
            fall = math.sin((c / cols) * math.pi * freq + phase + row_seed) * amp
            pulse = math.exp(-((c / cols - 0.6) ** 2) * 6) * 90 * (r / rows)
            y = y_base + fall + pulse
            points.append((int(x), int(y)))

        # Draw as connected line segments.
        color = RED if r < 3 else INK
        width = 9 if r < 3 else 5
        opacity_factor = 0.95 if r < 3 else 0.35

        if r >= 3:
            # For dark lines, blend with background for transparency effect.
            color = _blend(INK, PAPER, 1.0 - opacity_factor)

        for i in range(len(points) - 1):
            draw.line([points[i], points[i + 1]], fill=color, width=width)

    # ── Footer ──
    draw.text((2640, 2850), "AI + COMMS · CN", fill=INK_MID, font=footer_font, anchor="ra")

    im.save(output_path, format="PNG", optimize=False)
    logger.debug("Cover saved to %s.", output_path.name)
