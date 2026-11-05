"""Discord PRICE CHANGE post only: two mobile-legible dark pages, one message.

Root fix: the old single 3200x2400, 20-row, side-by-side table was shrunk
to phone width by Discord; its 26px labels became approximately 3px.
This renderer displays all 10 rises and all 10 drops, but on separate
1440x2160 portrait images attached to ONE existing Discord price post.
It does not affect the injury/news renderer, shared master, or other posts.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont
try:
    from .minimal_theme import background_color
except ImportError:
    from minimal_theme import background_color

WIDTH, HEIGHT = 1440, 2160
PAGE_SIZE = (WIDTH, HEIGHT)
ROW_LIMIT = 10
ROW_START, ROW_STEP, ROW_HEIGHT = 292, 169, 154
NAVY = (252, 251, 247)
PANEL = (255, 255, 255)
PANEL_EDGE = (216, 212, 199)
WHITE = (12, 16, 20)
SECONDARY = (49, 54, 59)
CYAN = (12, 16, 20)
GOLD = (12, 16, 20)
GREEN = (20, 110, 56)
RED = (167, 43, 98)
FONT_BOLD = ("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
FONT_NORMAL = ("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def _font(size: int, bold: bool = True):
    for path in FONT_BOLD if bold else FONT_NORMAL:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def fitted(draw, content, max_width: int, wanted: int, minimum: int,
           bold: bool = True):
    """Return (visible string, font) without ever painting beyond its column."""
    content = str(content).replace("\n", " ").strip()
    if max_width < 1:
        raise ValueError("Text column must have positive width")
    for size in range(wanted, minimum - 1, -1):
        font = _font(size, bold)
        bounds = draw.textbbox((0, 0), content, font=font)
        if bounds[2] - bounds[0] <= max_width:
            return content, font
    font = _font(minimum, bold)
    ellipsis = "…"
    while content and draw.textbbox((0, 0), content + ellipsis, font=font)[2] > max_width:
        content = content[:-1]
    return (content.rstrip() + ellipsis if content else ellipsis), font


def _line(draw, text, pos, *, width, size=50, min_size=30, color=WHITE, bold=True):
    label, font = fitted(draw, text, width, size, min_size, bold)
    draw.text(pos, label, font=font, fill=color)
    return label


def _image_within(canvas, picture, bounds):
    if picture is None:
        return
    x1, y1, x2, y2 = bounds
    if not (x1 < x2 and y1 < y2):
        raise ValueError("Invalid proportional media bounding rectangle")
    media = picture.convert("RGBA")
    media.thumbnail((x2 - x1, y2 - y1), Image.Resampling.LANCZOS)
    canvas.paste(media, (x1 + (x2 - x1 - media.width)//2,
                         y1 + (y2 - y1 - media.height)//2), media)


def row_rect(index):
    if not 0 <= index < ROW_LIMIT:
        raise ValueError("Only 10 players can fit on one price slide")
    top = ROW_START + index * ROW_STEP
    return (44, top, WIDTH - 44, top + ROW_HEIGHT)


def _draw_player(canvas, draw, item, index, direction, assets):
    x1, y1, x2, y2 = row_rect(index)
    accent = GREEN if direction == "rise" else RED
    shade = (196, 240, 208) if direction == "rise" else (250, 211, 231)
    draw.rounded_rectangle((x1, y1, x2, y2), radius=17,
                           fill=PANEL, outline=PANEL_EDGE, width=3)
    draw.rounded_rectangle((x1, y1 + 9, x1 + 11, y2 - 9),
                           radius=5, fill=accent)
    player_id = item.get("id")
    code = item.get("team_code")
    _image_within(canvas, assets.get(("photo", player_id)), (76, y1 + 13, 198, y2 - 9))
    _image_within(canvas, assets.get(("crest", code)), (219, y1 + 91, 267, y2 - 12))

    _line(draw, item.get("name", "Unknown"), (214, y1 + 10),
          width=737, size=69, min_size=45, color=WHITE)
    # Keep actual team / price facts visible even on a narrow phone.
    club_price = f"{item.get('team') or 'Team N/A'}  •  {item.get('price_label', '£N/A')}"
    _line(draw, club_price, (281, y1 + 93), width=667,
          size=43, min_size=35, color=SECONDARY, bold=True)

    progress = item.get("prediction")
    if not isinstance(progress, (int, float)):
        raise ValueError("Price progress must originate in verified upstream data")
    pct = f"{abs(progress)*100:.1f}%"
    _line(draw, pct, (1042, y1 + 14), width=316,
          size=70, min_size=55, color=accent)
    # Small labels are grouped into one high-contrast chip instead of
    # illegible beige 'TARGET %', 'LIKELIHOOD', 'PREDICTION' columns.
    if abs(progress) >= 1.0:
        status = "VERY LIKELY"
    elif abs(progress) >= .8:
        status = "LIKELY"
    elif abs(progress) >= .6:
        status = "POSSIBLE"
    else:
        status = "MONITOR"
    draw.rounded_rectangle((1044, y1 + 98, 1359, y1 + 142),
                           radius=15, fill=shade)
    _line(draw, status, (1062, y1 + 102), width=285,
          size=33, min_size=28, color=accent)


def render_price_pages(rises, falls, date_text, source_label, assets=None,
                       logo=None):
    """Preserve ALL twenty original top-10 candidates in two large readable pages."""
    if len(rises) > ROW_LIMIT or len(falls) > ROW_LIMIT:
        raise ValueError("Price prediction must keep maximum 10 per direction")
    if not rises and not falls:
        raise ValueError("No verified price movement rows")
    assets = assets or {}
    result = []
    for direction, entries in (("rise", rises), ("drop", falls)):
        if not entries:
            continue
        canvas = Image.new("RGB", PAGE_SIZE, background_color(f"{date_text}|{direction}"))
        draw = ImageDraw.Draw(canvas)
        _image_within(canvas, logo, (42, 27, 192, 160))
        _line(draw, "PRICE CHANGE PREDICTIONS", (216, 41),
              width=1172, size=74, min_size=58, color=WHITE)
        _line(draw, date_text, (219, 129), width=1100, size=44,
              min_size=36, color=SECONDARY, bold=True)
        title = "▲  TOP 10 PRICE RISE TARGETS" if direction == "rise" \
            else "▼  TOP 10 PRICE DROP TARGETS"
        accent = GREEN if direction == "rise" else RED
        draw.rounded_rectangle((43, 199, 1398, 280), radius=15,
                               fill=PANEL, outline=accent, width=3)
        _line(draw, title, (71, 211), width=1277, size=55, min_size=41,
              color=WHITE)
        for i, item in enumerate(entries):
            _draw_player(canvas, draw, item, i, direction, assets)

        # No tiny three-line source in the margin, and no fabricated probability.
        draw.line((47, 2002, 1395, 2002), fill=(67, 129, 169), width=3)
        _line(draw, f"Source: {source_label}", (59, 2020),
              width=1338, size=39, min_size=31, color=CYAN, bold=True)
        _line(draw, "Progress % is an indicator, not a probability of a price change",
              (59, 2070), width=1338, size=36, min_size=31,
              color=SECONDARY, bold=True)
        result.append(canvas)
    return result
