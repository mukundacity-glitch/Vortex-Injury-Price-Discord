"""FPL VORTEX reference-2 broadcast layout, shared by both posting repositories.

This module draws supplied verified facts; it never selects players, invents a
ranking, fetches data or sends a post. Keep the Discord copy byte-identical.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont
try:
    from .minimal_theme import background, action_fill, social_footer
except ImportError:
    from minimal_theme import background, action_fill, social_footer

STYLE_VERSION = "minimal-paper-action-fills-v2"
SIZE = (1536, 864)
TABLE_YELLOW = (255, 255, 255)
TABLE_INK = (12, 16, 20)
TABLE_RULE = (216, 212, 199)
GOLD = (176, 139, 42)
CYAN = (30, 150, 157)
WHITE = (12, 16, 20)
NAVY = (255, 255, 255, 255)


def font(size, bold=True):
    for family in ("DejaVuSansCondensed", "DejaVuSans", "LiberationSans"):
        suffix = "-Bold" if bold else ""
        directory = "liberation2" if family == "LiberationSans" else "dejavu"
        try:
            return ImageFont.truetype(f"/usr/share/fonts/truetype/{directory}/{family}{suffix}.ttf", size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def text(draw, value, x, y, width, size=23, color=WHITE, minimum=15, center=False):
    color = TABLE_INK
    value = " ".join(str(value).split())
    while size > minimum and draw.textbbox((0, 0), value, font=font(size))[2] > width:
        size -= 1
    face = font(size)
    while value and draw.textbbox((0, 0), value, font=face)[2] > width:
        value = value[:-2].rstrip("… ") + "…" if len(value) > 2 else ""
    if center:
        x += (width - draw.textbbox((0, 0), value, font=face)[2]) / 2
    draw.text((x, y), value, font=face, fill=color)


def paragraph(draw, value, box, size=19, color=WHITE, lines=2):
    x, y, width = box
    words, rows, current = str(value).split(), [], ""
    for word in words:
        trial = (current + " " + word).strip()
        if current and draw.textbbox((0, 0), trial, font=font(size))[2] > width:
            rows.append(current)
            current = word
        else:
            current = trial
    if current:
        rows.append(current)
    for n, row in enumerate(rows[:lines]):
        if n == lines - 1 and len(rows) > lines:
            row += "…"
        text(draw, row, x, y+n*(size+4), width, size, color)


def contain(canvas, source, box, *, bottom=False, crop_alpha=False):
    """Contain a genuine portrait/crest without ever changing its aspect ratio."""
    image = source.convert("RGBA").copy()
    if crop_alpha:
        bounds = image.getchannel("A").getbbox()
        if bounds:
            image = image.crop(bounds)
    x, y, w, h = box
    ratio = min(w/image.width, h/image.height)
    image = image.resize((max(1, round(image.width*ratio)), max(1, round(image.height*ratio))), Image.Resampling.LANCZOS)
    target_y = y+h-image.height if bottom else y+(h-image.height)//2
    canvas.paste(image, (round(x+(w-image.width)/2), round(target_y)), image)


def panel(draw, box, accent=GOLD):
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=20, fill=NAVY, outline=TABLE_RULE, width=2)


def compact_table(draw, rows, box):
    """White cells, fine rules and bold black text."""
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=7, fill=TABLE_YELLOW, outline=TABLE_RULE, width=2)
    height = (y1-y0)/len(rows)
    width = x1-x0
    label_width = width*.53
    size = 21 if width >= 230 else 18
    for n, (label, value) in enumerate(rows):
        top = y0+n*height
        if n:
            draw.line((x0, top, x1, top), fill=TABLE_RULE, width=1)
        text(draw, label, x0+9, top+5, label_width-12, size, TABLE_INK, 13)
        text(draw, value, x0+label_width, top+4, width-label_width-8,
             size+1, TABLE_INK, 14, center=True)


def current_fixture(fixtures, gw):
    rows = [item for item in fixtures if item.get("gw") == gw and not item.get("blank")]
    if not rows:
        return "BLANK", "—"
    opponent = " / ".join(f"{r['opponent']} ({r['venue']})" for r in rows)
    difficulty = " / ".join(str(r["fdr"]) for r in rows)
    return opponent, difficulty


ADVANCED = (("MINUTES", "MINUTES"), ("TOTAL PTS", "TOTAL PTS"),
            ("CS", "CLEAN SHEETS"), ("GOALS", "GOALS"),
            ("ASSISTS", "ASSISTS"), ("xG", "xG"), ("xA", "xA"),
            ("DC ACTIONS", "DC ACTIONS"), ("xGI", "xGI"),
            ("SAVES", "SAVES"), ("xGC", "xGC"))


def advanced_table(draw, players, box=(44, 514, 1492, 663)):
    columns = [(key, label) for key, label in ADVANCED
               if any(key in p["metrics"] for p in players)]
    # Nine statistical columns remain mobile-readable; GK-only boards include
    # saves/xGC naturally. Optional missing facts are never replaced with zero.
    columns = columns[:9]
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=TABLE_YELLOW, outline=TABLE_RULE, width=2)
    name_width = 260
    col_width = (x1-x0-name_width)/max(1, len(columns))
    header = 45
    row_height = (y1-y0-header)/len(players)
    text(draw, "KEY STATS • ADVANCED", x0+12, y0+12, name_width-22, 20, TABLE_INK)
    for col, (_, label) in enumerate(columns):
        left = x0+name_width+col*col_width
        draw.line((left, y0, left, y1), fill=TABLE_RULE, width=1)
        paragraph(draw, label.replace(" ", "\n"), (left+4, y0+8, col_width-8), 16, TABLE_INK, 2)
    draw.line((x0, y0+header, x1, y0+header), fill=TABLE_RULE, width=2)
    for row, player in enumerate(players):
        top = y0+header+row*row_height
        if row:
            draw.line((x0, top, x1, top), fill=TABLE_RULE, width=1)
        size = min(27, max(17, int(row_height)-8))
        text(draw, player["name"].upper(), x0+12, top+4, name_width-24, size, TABLE_INK)
        for col, (key, _) in enumerate(columns):
            value = player["metrics"].get(key, "—")
            if key in ("xG", "xA", "xGI", "xGC") and value != "—":
                value = f"{float(value):.2f}"
            text(draw, value, x0+name_width+col*col_width+4, top+4,
                 col_width-8, size, TABLE_INK, 15, center=True)


def comparison_board(master, title, gw, players, *, verdict=""):
    """Draw reference-2 geometry for one to four fact-checked player profiles."""
    if not 1 <= len(players) <= 4:
        raise ValueError("Comparison board supports one to four players per slide")
    key = f'{title}|{gw}|' + '|'.join(p['name'] + str(p['metrics']) for p in players)
    canvas = background(master, key, SIZE)
    draw = ImageDraw.Draw(canvas, "RGBA")
    # The minimal background retains supplied masthead brand marks.
    text(draw, title.upper(), 302, 4, 1035, 40, WHITE, 23, center=True)
    text(draw, "FORM • MINUTES • FIXTURE • VALUE", 385, 47, 900, 18, CYAN, center=True)
    draw.polygon([(680, 78), (856, 78), (846, 115), (670, 115)], fill=GOLD, outline=(255, 240, 180))
    text(draw, f"GW{gw}", 686, 78, 148, 30, TABLE_INK, center=True)
    gap = 14
    width = (1460-gap*(len(players)-1))/len(players)
    for n, player in enumerate(players):
        x0 = round(38+n*(width+gap))
        x1 = round(x0+width)
        accent = GOLD if player.get('label') == 'VORTEX CAPTAIN' else CYAN if len(players) == 3 else CYAN if n % 2 else GOLD
        panel(draw, (x0, 124, x1, 496), accent)
        if len(players) == 4:
            # Four equal columns: no portrait/table squeeze or clipped names.
            draw.rounded_rectangle((x0+12, 132, x1-12, 161), radius=4, fill=action_fill(player['action']))
            text(draw, player.get('label') or player['action'], x0+18, 134,
                 width-36, 25, TABLE_INK, 18, center=True)
            text(draw, player['name'].upper(), x0+16, 168, width-32, 32, WHITE, 23, center=True)
            text(draw, f"{player['club']} • {player['position']}", x0+14, 203,
                 width-28, 17, WHITE, 15, center=True)
            contain(canvas, player['portrait'], (x0+52, 222, width-104, 124), bottom=True, crop_alpha=True)
            contain(canvas, player['badge'], (x1-69, 232, 48, 48))
            draw = ImageDraw.Draw(canvas, 'RGBA')
            metrics = player['metrics']
            opponent, difficulty = current_fixture(player['fixtures'], gw)
            compact_table(draw, player.get('summary_rows') or [('PRICE', metrics['PRICE']), ('OWNERSHIP', metrics['OWNERSHIP']),
                                ('FORM', metrics['FORM']), ('FIXTURE', opponent), ('FDR', difficulty)],
                          (x0+12, 352, x1-12, 487))
            continue
        photo_width = min(400, round(width*.40))
        detail_x = x0+photo_width+16
        detail_w = x1-detail_x-13
        contain(canvas, player["portrait"], (x0+9, 149, photo_width, 279), bottom=True, crop_alpha=True)
        contain(canvas, player["badge"], (x1-73, 174, 58, 61))
        draw = ImageDraw.Draw(canvas, "RGBA")
        ribbon_x = max(x0+18, detail_x-18)
        draw.polygon([(ribbon_x+9, 133), (x1-18, 133), (x1-27, 166), (ribbon_x, 166)], fill=action_fill(player['action']))
        label = player.get("label") or player["action"]
        text(draw, label.upper(), ribbon_x+12, 138, x1-ribbon_x-43, 21, TABLE_INK, 14, center=True)
        text(draw, player["name"].upper(), detail_x, 179, detail_w-65, 34, WHITE, 18)
        text(draw, f"{player['club']} • {player['position']}", detail_x, 224, detail_w, 17, WHITE, 14)
        metrics = player["metrics"]
        opponent, difficulty = current_fixture(player["fixtures"], gw)
        rows = [("PRICE", metrics["PRICE"]), ("OWNERSHIP", metrics["OWNERSHIP"]),
                ("FORM", metrics["FORM"]), ("FIXTURE", opponent), ("FDR", difficulty)]
        current = [f for f in player["fixtures"] if f.get("gw") == gw and not f.get("blank")]
        if current and all(type(f.get("xpts")) in (int, float) for f in current):
            rows.append(("MODEL xPTS", f"{sum(f['xpts'] for f in current):.2f}"))
        compact_table(draw, rows, (detail_x, 253, x1-13, 412))
        draw.line((x0+18, 429, x1-18, 429), fill=accent, width=2)
        paragraph(draw, f"{player['action']} • {player['reason']}",
                  (x0+18, 440, width-36), 19 if len(players) <= 3 else 16)
    advanced_table(draw, players)
    panel(draw, (28, 679, 1508, 728), GOLD)
    text(draw, "FINAL VERDICT", 48, 691, 218, 24, GOLD)
    generic = {"BUY", "HOLD", "SELL", "START", "BENCH", "MONITOR", "CAPTAIN", "WATCHLIST"}
    summary = verdict if verdict.strip().upper() not in generic else ""
    summary = summary or "  |  ".join(f"{p['name']}: {p['action']}" for p in players)
    text(draw, summary, 280, 692, 1208, 21, WHITE, 16)
    # Five consecutive GW slots per player; doubles stay in the same cell.
    band_width = 1436 / len(players)
    colors = {1: '#00be86', 2: '#6bcf9c', 3: '#ffd477', 4: '#f3a36d', 5: '#ef6975'}
    for i, player in enumerate(players):
        left = 50 + i*band_width
        cell_width = (band_width-14)/5
        for offset in range(5):
            week = gw+offset
            rows = [r for r in player['fixtures'] if r.get('gw') == week]
            fixture = ' / '.join(f"{r['opponent']}({r['venue']})" for r in rows if not r.get('blank')) or 'BLANK'
            fdrs = [r['fdr'] for r in rows if r.get('fdr') in colors]
            color = colors[max(fdrs)] if fdrs else '#718096'
            x = left+offset*cell_width
            draw.rounded_rectangle((x, 738, x+cell_width-4, 795), radius=5, fill=NAVY, outline=color, width=2)
            text(draw, f'GW{week}', x+5, 740, cell_width-12, 16, WHITE, 13, center=True)
            if len(players) == 4:
                teams = '/'.join(r['opponent'] for r in rows if not r.get('blank')) or 'BLANK'
                venues = '/'.join(r['venue'] for r in rows if not r.get('blank'))
                text(draw, teams, x+4, 758, cell_width-10, 18, WHITE, 10, center=True)
                text(draw, venues, x+4, 780, cell_width-10, 12, WHITE, 10, center=True)
            else:
                text(draw, fixture, x+5, 761, cell_width-12, 21, WHITE, 14, center=True)
    return canvas
