"""Minimal broadcast styling only; never changes facts or publishing behavior."""
from __future__ import annotations
import colorsys
import hashlib
from PIL import Image, ImageDraw, ImageFont

INK = (12, 16, 20)
MUTED = (49, 54, 59)
PAPER = (255, 255, 255)
RULE = (216, 212, 199)
CYAN = (30, 150, 157)
GOLD = (176, 139, 42)
START = (126, 222, 155)
HOLD = (255, 222, 105)
MONITOR = (247, 169, 204)


def face(size):
    return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf', size)


def action_fill(action):
    word = str(action).strip().upper().split('•')[0].split(':')[0].strip()
    if word in ('START', 'BUY', 'CAPTAIN'): return START
    if word == 'HOLD': return HOLD
    if word in ('MONITOR', 'WATCHLIST', 'BENCH', 'SELL', 'AVOID'): return MONITOR
    return (241, 229, 190)


def background_color(key):
    # Stable within an edition/retry, varied for the next post; no global RNG.
    digest = hashlib.sha256(str(key).encode()).digest()
    hue = int.from_bytes(digest[:2], 'big') / 65535
    return tuple(round(c * 255) for c in colorsys.hsv_to_rgb(hue, .035 + digest[2]/255*.025, .99))


def edition_key(item):
    return '|'.join(str(getattr(item, field, '')) for field in ('kind', 'title', 'gw', 'data_at', 'source_time'))


def background(master, key, size=(1536, 864)):
    canvas = Image.new('RGB', size, background_color(key))
    # Retain actual supplied brand marks, rather than inventing replacements.
    # The attached reference provides clean white-background brand marks.
    from pathlib import Path
    asset = Path(__file__).resolve().parent / 'minimal_brand.png'
    if asset.exists():
        with Image.open(asset) as strip:
            marks = strip.convert('RGBA')
        scale = size[0] / 1536
        for box, x in (((0, 0, 270, 80), 20), ((270, 0, 460, 80), 1326)):
            mark = marks.crop(box)
            mark.thumbnail((round((box[2]-box[0])*scale), round(64*scale)), Image.Resampling.LANCZOS)
            canvas.paste(mark, (round(x*scale), round(5*scale)), mark)
    return canvas


def social_footer(canvas, telegram='', discord=''):
    draw = ImageDraw.Draw(canvas)
    w, h = canvas.size
    y = round(h*.928)
    draw.rectangle((0, y, w, h), fill=PAPER)
    draw.line((round(w*.035), y, round(w*.965), y), fill=RULE, width=1)
    values = ('TELEGRAM  t.me/'+telegram.lstrip('@') if telegram else 'FPL VORTEX',
              'DISCORD  '+discord if discord else 'FPL VORTEX')
    for x, value in zip((round(w*.06), round(w*.55)), values):
        size = round(w*.019)
        while size > 12 and draw.textbbox((0,0),value,font=face(size))[2] > w*.40: size -= 1
        draw.text((x, y+round(h*.017)), value, font=face(size), fill=INK)
    return canvas
