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
) -> None:
    """Render a 3000×3000 PNG cover for the episode.

    The cover uses CN brand colours and displays the show title,
    episode number badge, and episode date.
    """
    from PIL import Image, ImageDraw

    dt = episode_dt.astimezone(ZoneInfo(TIMEZONE))
    logger.debug("Rendering cover for episode %d ('%s')…", episode_number, episode_name)

    width = 3000
    height = 3000
    im = Image.new("RGB", (width, height), color=CN_PETROLEUM_BLACK)
    draw = ImageDraw.Draw(im)

    # Subtle vertical gradient background.
    for y in range(height):
        t = y / (height - 1)
        color = _blend(CN_PETROLEUM_BLACK, CN_BLACK_DEEP, t)
        draw.line([(0, y), (width, y)], fill=color)

    # Decorative accent polygons.
    draw.polygon([(0, 0), (1200, 0), (650, 1700), (0, 1400)], fill=_blend(CN_RED, CN_PETROLEUM_BLACK, 0.35))
    draw.polygon([(1400, 3000), (3000, 1950), (3000, 3000)], fill=_blend(CN_RED, CN_BLACK_DEEP, 0.65))
    draw.rectangle([(180, 2120), (2820, 2280)], fill=CN_RED)

    title_font = _load_font(360, "extrabold")
    strap_font = _load_font(86, "semibold")
    date_font = _load_font(110, "regular")
    episode_font = _load_font(84, "bold")

    draw.text((200, 340), "The Signal", fill=CN_WHITE, font=title_font)
    draw.text((205, 790), "Weekly AI and Communications Brief", fill=CN_LIGHT, font=strap_font)

    # Episode number badge (top-right corner).
    episode_label = f"Episode {episode_number}"
    bbox = draw.textbbox((0, 0), episode_label, font=episode_font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    box_x0 = width - text_w - 340
    box_y0 = 250
    box_x1 = width - 200
    box_y1 = box_y0 + text_h + 70
    draw.rounded_rectangle([(box_x0, box_y0), (box_x1, box_y1)], radius=24, fill=CN_RED)
    draw.text((box_x0 + 70, box_y0 + 35), episode_label, fill=CN_WHITE, font=episode_font)

    # Date line below the red bar.
    date_line = format_episode_date(dt)
    draw.text((200, 2460), date_line, fill=CN_WHITE, font=date_font)

    im.save(output_path, format="PNG", optimize=False)
    logger.debug("Cover saved to %s.", output_path.name)
