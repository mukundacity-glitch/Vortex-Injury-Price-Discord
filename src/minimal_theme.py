"""FPL VORTEX broadcast styling based on the approved neon references.

Visual-only helpers. No publication, timing, or factual-data decisions live here.
Identical editions render deterministically; the approved master supplies marks.
"""
from __future__ import annotations
import hashlib
from PIL import Image, ImageDraw, ImageFont

INK = (232, 244, 255)
MUTED = (168, 196, 226)
PAPER = (8, 15, 40)
RULE = (29, 207, 246)
CYAN = (0, 226, 248)
GOLD = (255, 204, 64)
START = (65, 235, 134)
HOLD = (255, 204, 64)
MONITOR = (249, 98, 194)


def face(size):
    return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf', size)


def action_fill(action):
    word = str(action).strip().upper().split('•')[0].split(':')[0].strip()
    if word in ('START', 'BUY', 'CAPTAIN'): return START
    if word == 'HOLD': return HOLD
    if word in ('MONITOR', 'WATCHLIST', 'BENCH', 'SELL', 'AVOID'): return MONITOR
    return (152, 116, 255)


def background_color(key):
    """Dark deterministic navy/purple base, never a near-white pastel."""
    digest = hashlib.sha256(str(key).encode('utf-8')).digest()
    return (9 + digest[0] % 8, 9 + digest[1] % 7, 39 + digest[2] % 19)


def background(master, key, size=(1536, 864)):
    """Gradient, neon trim and existing real master logos; no white canvas."""
    w, h = size
    base = background_color(key)
    top = (base[0], base[1] + 5, base[2])
    bottom = (29 + base[0] // 3, 6 + base[1] // 4, 63 + base[2] // 4)
    column = Image.new('RGB', (1, h))
    column.putdata([
        tuple(round(top[i] + (bottom[i] - top[i]) * y / max(1, h - 1))
              for i in range(3))
        for y in range(h)
    ])
    canvas = column.resize((w, h))
    d = ImageDraw.Draw(canvas, 'RGBA')
    # Off-axis purple ribbons, keeping the reading surfaces dark.
    d.polygon([(0, int(h*.12)), (int(w*.27), 0), (int(w*.35), 0),
               (0, int(h*.52))], fill=(105, 32, 206, 46))
    d.polygon([(w, int(h*.27)), (w, int(h*.72)),
               (int(w*.72), h)], fill=(82, 26, 174, 61))
    d.ellipse((-int(w*.23), int(h*.21), int(w*.23), int(h*1.07)),
              outline=(132, 45, 248, 65), width=max(3, w//190))
    d.rounded_rectangle((int(w*.012), int(h*.013), int(w*.988), int(h*.984)),
                        radius=max(12, w//65), outline=(0, 218, 249, 215),
                        width=max(2, w//510))
    d.line((int(w*.015), int(h*.108), int(w*.985), int(h*.108)),
           fill=(174, 67, 255, 200), width=max(2, h//410))
    # The existing approved master is the source of lion/league marks.
    # Import only the edge masthead logos, leaving the new dark data area intact.
    if master is not None:
        marks = master.convert('RGB').resize(size, Image.Resampling.LANCZOS)
        strip_h = max(1, round(h*.102))
        logo_w = round(w*.205)
        league_w = round(w*.13)
        canvas.paste(marks.crop((0, 0, logo_w, strip_h)), (0, 0))
        canvas.paste(marks.crop((w-league_w, 0, w, strip_h)),
                     (w-league_w, 0))
    return canvas


def social_footer(canvas, telegram='', discord=''):
    """Neon footer with unchanged, caller-provided channel handles."""
    draw = ImageDraw.Draw(canvas, 'RGBA')
    w, h = canvas.size
    y = round(h*.928)
    draw.rectangle((0, y, w, h), fill=(*PAPER, 255))
    draw.line((round(w*.02), y, round(w*.98), y),
              fill=(*CYAN, 255), width=max(2, w//510))
    draw.line((round(w*.02), y+3, round(w*.98), y+3),
              fill=(156, 55, 249, 185), width=2)
    values = ('TELEGRAM  t.me/'+telegram.lstrip('@') if telegram else 'FPL VORTEX',
              'DISCORD  '+discord if discord else 'FPL VORTEX')
    for x, value in zip((round(w*.06), round(w*.55)), values):
        size = round(w*.019)
        while size > 12 and draw.textbbox((0, 0), value, font=face(size))[2] > w*.40:
            size -= 1
        draw.text((x, y+round(h*.017)), value, font=face(size), fill=INK)
    return canvas
