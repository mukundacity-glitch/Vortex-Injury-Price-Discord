"""Reviewed, player-ID-bound AI artwork, used only after official CDN failure.

The ChatGPT tasks create raster assets with their image tool and commit them
with identity metadata. Scheduled Python jobs never substitute generic faces.
"""
from pathlib import Path
from io import BytesIO
import base64
import hashlib
import json

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'assets' / 'ai-portraits' / 'manifest.json'


def load_portrait(code, root=ROOT):
    manifest_path = root / 'assets' / 'ai-portraits' / 'manifest.json'
    records = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    row = records.get(str(code))
    remote = False
    if not row:
        import requests
        try:
            response = requests.get('https://raw.githubusercontent.com/mukundacity-glitch/Telegram-Bot/main/assets/ai-portraits/manifest.json', timeout=8)
            response.raise_for_status()
            row = response.json().get(str(code))
            remote = True
        except (requests.RequestException, ValueError, AttributeError):
            return None
    if not row:
        return None
    if row.get('player_code') != code or not row.get('player_name') or row.get('type') != 'AI_ILLUSTRATION':
        raise ValueError('AI portrait identity metadata invalid')
    path = (root / row['path']).resolve()
    if not path.is_relative_to((root / 'assets' / 'ai-portraits').resolve()):
        raise ValueError('AI portrait path outside reviewed asset directory')
    if remote and not path.exists():
        import requests
        relative = path.relative_to(root.resolve()).as_posix()
        try:
            response = requests.get('https://raw.githubusercontent.com/mukundacity-glitch/Telegram-Bot/main/' + relative, timeout=10)
            response.raise_for_status()
            raw = response.content
        except requests.RequestException:
            return None
    else:
        raw = path.read_bytes()
    if path.suffix == '.b64':
        raw = base64.b64decode(raw, validate=True)
    if hashlib.sha256(raw).hexdigest() != row.get('sha256'):
        raise ValueError('AI portrait checksum differs from reviewed asset')
    with Image.open(BytesIO(raw)) as source:
        image = source.convert('RGBA')
    # The disclosure travels with the portrait through EVERY renderer.
    image.thumbnail((650, 850), Image.Resampling.LANCZOS)
    labeled = Image.new('RGBA', (image.width, image.height+38))
    labeled.paste(image, (0, 0), image)
    draw = ImageDraw.Draw(labeled)
    draw.rectangle((0, image.height, image.width, image.height+38), fill='#031329')
    face = ImageFont.load_default(size=max(12, min(22, image.width//18)))
    draw.text((8, image.height+8), 'AI ILLUSTRATION', fill='white', font=face)
    return labeled


def record_missing(code):
    path = ROOT / 'state' / 'missing_portraits.json'
    rows = json.loads(path.read_text()) if path.exists() else {}
    rows[str(code)] = {'player_code': code, 'status': 'needs_ai_generation'}
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(rows, indent=2, sort_keys=True)+'\n')
    temp.replace(path)
