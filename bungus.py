"""
Wanted-poster image generator for the weekly Bungus Jones punishment.

Template: 2400x1792 — all layout constants below are measured from pixel analysis.
Run test_bungus.py to preview without touching the bot.
"""

import io
import os
from PIL import Image, ImageDraw, ImageFont

TEMPLATE_PATH = "wanted_template.png"
FONT_PATH = "impact.ttf"
_FONT_FALLBACK = "/System/Library/Fonts/Supplemental/Impact.ttf"

TEMPLATE_W = 2400

# ── Photo box ─────────────────────────────────────────────────────────────────
# Outer dark box: x=895–1503, y=666–1236. Avatar goes inside the frame (~35px).
PHOTO_X = 930    # ADJUST: left edge of avatar paste area
PHOTO_Y = 701    # ADJUST: top edge of avatar paste area
PHOTO_W = 538    # ADJUST: width  (outer box width  - 2 × frame thickness)
PHOTO_H = 500    # ADJUST: height (outer box height - 2 × frame thickness)

# ── Username line (covers "[INSERT USERNAME HERE]", measured at y=396–483) ────
USERNAME_COVER = (150, 388, 2250, 494)   # ADJUST: (x1, y1, x2, y2) cover rect
USERNAME_Y     = 390                     # ADJUST: top of drawn username text
USERNAME_SIZE  = 110                     # ADJUST: font size (pt)

# ── Score line (covers "LAST SEEN SCORING A MISERABLE … ON MAPTAP", y=1530–1627)
SCORE_COVER = (50, 1390, 2350, 1590)     # ADJUST: (x1, y1, x2, y2) cover rect
SCORE_Y     = 1420                       # ADJUST: top of drawn score text
SCORE_SIZE  = 72                         # ADJUST: font size — must fit ~45 chars across 2300px

# ── Colors ────────────────────────────────────────────────────────────────────
TEXT_COLOR      = (20, 10, 5)            # dark brown matching template ink
PARCHMENT_COLOR = (200, 168, 128)        # approximate parchment background


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    path = FONT_PATH if os.path.exists(FONT_PATH) else _FONT_FALLBACK
    return ImageFont.truetype(path, size)


def _centered_x(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return (TEMPLATE_W - (bbox[2] - bbox[0])) // 2


def _fit_font(draw: ImageDraw.ImageDraw, text: str, max_size: int, max_width: int) -> ImageFont.FreeTypeFont:
    """Reduce font size until text fits within max_width."""
    size = max_size
    while size > 20:
        font = _load_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
        size -= 4
    return _load_font(size)


def generate_wanted_poster(avatar_bytes: bytes, username: str, worst_score: int) -> io.BytesIO:
    poster = Image.open(TEMPLATE_PATH).convert("RGBA")
    draw = ImageDraw.Draw(poster)

    # Paste avatar into the photo box
    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    avatar = avatar.resize((PHOTO_W, PHOTO_H), Image.LANCZOS)
    poster.paste(avatar, (PHOTO_X, PHOTO_Y), avatar)

    # Cover username placeholder and draw actual username
    draw.rectangle(USERNAME_COVER, fill=PARCHMENT_COLOR)
    name_text = username.upper()
    name_font = _fit_font(draw, name_text, USERNAME_SIZE, USERNAME_COVER[2] - USERNAME_COVER[0])
    draw.text((_centered_x(draw, name_text, name_font), USERNAME_Y), name_text, font=name_font, fill=TEXT_COLOR)

    # Cover score placeholder and draw actual score line
    draw.rectangle(SCORE_COVER, fill=PARCHMENT_COLOR)
    score_text = f"LAST SEEN SCORING A MISERABLE {worst_score} ON MAPTAP"
    score_font = _fit_font(draw, score_text, SCORE_SIZE, SCORE_COVER[2] - SCORE_COVER[0])
    draw.text((_centered_x(draw, score_text, score_font), SCORE_Y), score_text, font=score_font, fill=TEXT_COLOR)

    buf = io.BytesIO()
    poster.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf
