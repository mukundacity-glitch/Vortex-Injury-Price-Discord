"""Reference-inspired FPL VORTEX navy/violet neon graphics; publishing is untouched."""
from __future__ import annotations

import hashlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

INK = (239, 247, 255)
MUTED = (158, 189, 222)
PAPER = (7, 14, 38)
RULE = (34, 203, 248)
CYAN = (23, 229, 249)
GOLD = (255, 205, 82)
START = (82, 238, 141)
HOLD = (255, 214, 95)
MONITOR = (244, 105, 194)


def face(size):
    for path in ('/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def action_fill(action):
    word = str(action).strip().upper().split('•')[0].split(':')[0].strip()
    if word in ('START', 'BUY', 'CAPTAIN'): return START
    if word == 'HOLD': return HOLD
    if word in ('MONITOR', 'WATCHLIST', 'BENCH', 'SELL', 'AVOID'): return MONITOR
    return GOLD


def edition_key(item):
    return '|'.join(str(getattr(item, field, '')) for field in ('kind', 'title', 'gw', 'data_at', 'source_time'))


def background_color(key):
    """Deterministic dark navy/purple; a retry renders the same pixels."""
    seed = hashlib.sha256(str(key).encode('utf-8')).digest()
    return (8 + seed[0] % 6, 10 + seed[1] % 6, 34 + seed[2] % 14)


def _brand_logo(canvas):
    """Use the existing authentic repository logo, never a synthetic lion."""
    root = Path(__file__).resolve().parents[1]
    candidates = (root / 'assets' / 'brand' / 'vortex-lion.png',
                  root / 'logo.png')
    for asset in candidates:
        if not asset.is_file():
            continue
        with Image.open(asset) as source:
            logo = source.convert('RGBA')
        # A non-transparent source can have a white rectangle; never paste it.
        if logo.getchannel('A').getextrema()[0] == 255:
            continue
        w, h = canvas.size
        logo.thumbnail((round(w * .064), round(h * .086)),
                       Image.Resampling.LANCZOS)
        canvas.paste(logo, (round(w * .025), round(h * .015)), logo)
        return True
    return False


def background(master, key, size=(1536, 864)):
    """Deep navy/purple gradient and cyan/violet broadcast frame (no white fill)."""
    w, h = size
    base = background_color(key)
    upper = (base[0], base[1], base[2])
    lower = (max(4, base[0] - 3), max(5, base[1] - 5), min(78, base[2] + 25))
    column = Image.new('RGB', (1, h))
    column.putdata([tuple(round(upper[i] * (1 - y / max(1, h - 1))
                                + lower[i] * y / max(1, h - 1)) for i in range(3))
                    for y in range(h)])
    canvas = column.resize(size)
    glow = Image.new('RGBA', size)
    g = ImageDraw.Draw(glow, 'RGBA')
    g.polygon([(0, 0), (round(w*.38), 0), (0, round(h*.47))],
              fill=(51, 15, 126, 75))
    g.polygon([(w, 0), (round(w*.83), 0), (w, round(h*.40))],
              fill=(11, 179, 240, 40))
    g.polygon([(0, h), (0, round(h*.75)), (round(w*.28), h)],
              fill=(128, 25, 202, 69))
    g.polygon([(w, h), (round(w*.73), h), (w, round(h*.66))],
              fill=(86, 16, 201, 85))
    canvas = Image.alpha_composite(canvas.convert('RGBA'), glow).convert('RGB')
    d = ImageDraw.Draw(canvas)
    margin = max(12, round(w * .012))
    line = max(2, round(w / 650))
    d.rounded_rectangle((margin, margin, w-margin-1, h-margin-1),
                        radius=round(h*.028), outline=(132, 48, 245), width=line)
    d.line((margin+14, round(h*.105), w-margin-14, round(h*.105)),
           fill=CYAN, width=max(2, line))
    d.line((margin+14, round(h*.920), w-margin-14, round(h*.920)),
           fill=(166, 60, 251), width=max(2, line))
    branded = _brand_logo(canvas)
    title = 'FPL VORTEX'
    d = ImageDraw.Draw(canvas)
    brand_x = round(w * (.092 if branded else .033))
    max_brand_width = round(w * .196) - brand_x
    brand_size = round(w * .028)
    while brand_size > 14 and d.textbbox((0, 0), title, font=face(brand_size))[2] > max_brand_width:
        brand_size -= 1
    d.text((brand_x, round(h*.031)), title,
           font=face(brand_size), fill=CYAN, stroke_width=1,
           stroke_fill=(28, 7, 72))
    return canvas


def social_footer(canvas, telegram='', discord=''):
    """Existing handle strings are unchanged; only their appearance is updated."""
    draw = ImageDraw.Draw(canvas)
    w, h = canvas.size
    y = round(h*.928)
    draw.rectangle((0, y, w, h), fill=PAPER)
    draw.line((round(w*.025), y, round(w*.975), y), fill=CYAN,
              width=max(2, round(w*.002)))
    values = ('TELEGRAM  t.me/'+telegram.lstrip('@') if telegram else 'FPL VORTEX',
              'DISCORD  '+discord if discord else 'FPL VORTEX')
    for x, value in zip((round(w*.058), round(w*.550)), values):
        size = round(w*.019)
        while size > 12 and draw.textbbox((0, 0), value, font=face(size))[2] > w*.40:
            size -= 1
        draw.text((x, y+round(h*.016)), value, font=face(size), fill=INK)
    return canvas
