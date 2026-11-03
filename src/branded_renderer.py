"""Original blue FPL VORTEX branded cards for existing Discord schedules.

The approved existing master is fetched read-only from the canonical
Telegram-Bot assets (or FPL_BRAND_MASTER_PATH). Its actual artwork, masthead,
lion, background and footer survive; we never synthesize new brand elements.
No guessed handles, placeholder images, fabricated xPts or N/A.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import hashlib
import json
import os
import re

from PIL import Image, ImageDraw, ImageFont
import requests


class MissingVerifiedMedia(RuntimeError):
    """A current official portrait/crest is unavailable, not a data failure."""

CANONICAL_MASTER = ("https://raw.githubusercontent.com/mukundacity-glitch/"
                    "Telegram-Bot/main/assets/references/brand_background.png")
# Exact SHA-1 Git blob of the user-confirmed existing original master already in Telegram-Bot.
APPROVED_MASTER_BLOB_SHA = "b0d890a529ad7416a142d3cfbbadfc800eb26bd0"

POSITIONS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
FDR = {1: (62, 224, 147), 2: (122, 206, 172), 3: (244, 209, 112),
       4: (239, 157, 92), 5: (238, 94, 115)}
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"


def font(size, bold=False):
    for path in (BOLD if bold else FONT,
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
                 if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def verified_handles():
    handles = []
    for env in ("FPL_TELEGRAM_HANDLE", "FPL_DISCORD_HANDLE"):
        value = os.getenv(env, "").strip()
        if not re.fullmatch(r"@[A-Za-z0-9_.-]{2,50}", value):
            raise RuntimeError("Unverified footer handle: " + env)
        handles.append(value)
    return tuple(handles)


def master_slide(session=None):
    path = os.getenv("FPL_BRAND_MASTER_PATH", "").strip()
    if path:
        asset = Path(path)
        if not asset.is_file():
            raise FileNotFoundError("Branded 16:9 master is not installed")
        with Image.open(asset) as source:
            raw = asset.read_bytes()
            image = source.convert("RGB")
    else:
        client = session or requests.Session()
        response = client.get(CANONICAL_MASTER, timeout=15, allow_redirects=False)
        response.raise_for_status()
        if len(response.content) > 4_000_000:
            raise ValueError("Approved master is too large")
        raw = response.content
        with Image.open(BytesIO(raw)) as source:
            image = source.convert("RGB")
    if image.width * 9 != image.height * 16:
        raise ValueError("Original branded master has incorrect aspect ratio")
    required_sha = os.getenv("FPL_BRAND_MASTER_BLOB_SHA", "").strip()
    blob_sha = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if required_sha != APPROVED_MASTER_BLOB_SHA or blob_sha != APPROVED_MASTER_BLOB_SHA:
        raise RuntimeError("Installed slide differs from user-confirmed Telegram-Bot master; hold post")
    return image.resize((1536, 864), Image.Resampling.LANCZOS)


def actual_image(session, url):
    r = session.get(url, timeout=12, allow_redirects=False)
    r.raise_for_status()
    if len(r.content) > 3_000_000 or not r.headers.get("Content-Type", "image/").startswith("image/"):
        raise RuntimeError("Real player image/club crest not available")
    with Image.open(BytesIO(r.content)) as photo:
        return photo.convert("RGBA")


def _current_verified_media(session, code, category):
    """Try genuine Premier League/FPL image hosts; never invent a crest/photo."""
    if not isinstance(code, int) or code <= 0:
        raise RuntimeError("No official current player/club media ID")
    cache = getattr(session, "_vortex_verified_media", {})
    if (category, code) in cache:
        return cache[category, code].copy()
    if category == "photo":
        urls = [
            f"https://resources.premierleague.com/premierleague25/photos/players/250x250/{code}.png",
            f"https://resources.premierleague.com/premierleague25/photos/players/110x140/{code}.png",
            f"https://resources.premierleague.com/premierleague25/photos/players/250x250/p{code}.png",
            f"https://images.fantasy.premierleague.com/premierleague/photos/players/250x250/p{code}.png",
            f"https://resources.premierleague.com/premierleague/photos/players/250x250/p{code}.png",
        ]
    elif category == "crest":
        urls = [
            f"https://resources.premierleague.com/premierleague/badges/70/t{code}.png",
            f"https://resources.premierleague.com/premierleague/badges/50/t{code}.png",
            f"https://resources.premierleague.com/premierleague/badges/t{code}.png",
        ]
    else:
        raise ValueError("Unsupported verified media category")
    errors = []
    for url in urls:
        try:
            image = actual_image(session, url)
            if image.width >= 48 and image.height >= 48:
                if hasattr(session, "__dict__"):
                    cache[category, code] = image.copy()
                    session._vortex_verified_media = cache
                return image
        except (requests.RequestException, OSError, ValueError, RuntimeError) as exc:
            errors.append(type(exc).__name__)
    raise MissingVerifiedMedia(f"Verified current {category} media missing; affected edition held")


def next_five(fixtures, team_id, teams, gw):
    rows = []
    for event in range(gw, min(39, gw + 5)):
        selected = sorted((x for x in fixtures if x.get("event") == event
                           and team_id in (x.get("team_h"), x.get("team_a"))
                           and not x.get("finished")),
                          key=lambda f: (f.get("kickoff_time") or "", f.get("id") or 0))
        if not selected:
            rows.append((event, []))  # explicitly blank
            continue
        items = []
        for f in selected:
            home = f.get("team_h") == team_id
            opp = teams.get(f["team_a"] if home else f["team_h"], {})
            difficulty = f.get("team_h_difficulty" if home else "team_a_difficulty")
            if (not opp.get("short_name") or difficulty not in FDR
                    or not f.get("kickoff_time")):
                raise RuntimeError("Official next-five fixture is incomplete")
            items.append((opp["short_name"], "H" if home else "A", difficulty, f["id"]))
        rows.append((event, items))
    return rows


def _label(draw, text, x, y, size, width, color=(235, 246, 255)):
    text = str(text)
    while size >= 16 and draw.textbbox((0, 0), text, font=font(size, True))[2] > width:
        size -= 1
    draw.text((x, y), text, font=font(size, True), fill=color)


def _one_card(base, title, rows, teams, fixtures, gw, session, handles):
    try:
        from .comparison_board import comparison_board
    except ImportError:  # existing production entrypoint: python src/price_change_bot.py
        from comparison_board import comparison_board
    profiles = []
    fields = {"TOTAL PTS": "total_points", "MINUTES": "minutes",
              "CS": "clean_sheets", "GOALS": "goals_scored", "ASSISTS": "assists",
              "xG": "expected_goals", "xA": "expected_assists", "xGI": "expected_goal_involvements",
              "DC ACTIONS": "defensive_contribution", "SAVES": "saves", "xGC": "expected_goals_conceded"}
    for data in rows:
        player = data["player"]
        club = teams[player["team"]]
        if player.get("form") is None:
            raise RuntimeError("Verified official player form is missing")
        metrics = {"PRICE": f"£{player['now_cost']/10:.1f}m",
                   "OWNERSHIP": f"{float(player['selected_by_percent']):.1f}%",
                   "FORM": str(player["form"])}
        for label, field in fields.items():
            if player.get(field) is not None:
                metrics[label] = str(player[field])
        future = []
        for event, games in next_five(fixtures, player["team"], teams, gw):
            if not games:
                future.append({"gw": event, "blank": True})
            for opponent, venue, difficulty, fixture_id in games:
                future.append({"gw": event, "blank": False, "opponent": opponent,
                               "venue": venue, "fdr": difficulty, "fixture_id": fixture_id})
        action = data.get("action") or "MONITOR"
        profiles.append({"name": player.get("web_name") or player["second_name"],
                         "club": club.get("name") or club["short_name"],
                         "position": POSITIONS[player["element_type"]],
                         "metrics": metrics, "fixtures": future,
                         "portrait": _current_verified_media(session, player["code"], "photo"),
                         "badge": _current_verified_media(session, club["code"], "crest"),
                         "action": action.split("•")[0].strip(),
                         "reason": player.get("news") or action,
                         "label": action})
    canvas = comparison_board(base, title, gw, profiles)
    # Cover the original informational footer only where new handles belong;
    # original lion, left social icons and header remain original pixels.
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rounded_rectangle((644, 803, 1519, 854), radius=5,
                           fill=(3, 14, 35, 245), outline=(48, 188, 241, 175), width=1)
    _label(draw, f"TELEGRAM  t.me/{handles[0].lstrip('@')}", 658, 816, 22, 416,
           (47, 218, 246))
    _label(draw, f"DISCORD  {handles[1]}", 1100, 816, 22, 395,
           (169, 172, 253))
    return canvas.resize((1920, 1080), Image.Resampling.LANCZOS)


def render_batches(title, records, official_data, fixtures,
                   *, session=None, max_cards=10, unavailable=None):
    if not records or len(records) > max_cards*3:
        raise RuntimeError("Too many player stories for readable verified slides")
    handles = verified_handles()
    client = session or requests.Session()
    base = master_slide(client)
    clubs = {t["id"]: t for t in official_data.get("teams", [])}
    people = {p["id"]: p for p in official_data.get("elements", [])}
    gameweek = next((int(e["id"]) for e in official_data.get("events", [])
                     if e.get("is_next") and not e.get("finished")), None)
    if gameweek is None:
        raise RuntimeError("Current official FPL gameweek cannot be verified")
    validated = []
    for item in records:
        player_id = item.get("id")
        try:
            p = people.get(int(player_id)) if player_id is not None else None
        except (TypeError, ValueError):
            p = None
        if p is None:
            # Some old injury state files don't store ID, so join ONLY when
            # full name and current club uniquely identify one FPL player.
            full = item.get("name", "").casefold()
            team_code = item.get("team_code")
            matches = [p for p in people.values()
                       if (p.get("first_name", "") + " " + p.get("second_name", "")).strip().casefold() == full
                       and clubs.get(p.get("team"), {}).get("code") == team_code]
            if len(matches) == 1:
                p = matches[0]
        if (p is None or p.get("code") is None or p.get("element_type") not in POSITIONS
                or p.get("team") not in clubs or p.get("now_cost") is None
                or p.get("selected_by_percent") is None or p.get("minutes") is None):
            raise RuntimeError("Player identity or mandatory real profile stat missing")
        if unavailable is not None:
            try:
                _current_verified_media(client, p["code"], "photo")
                _current_verified_media(client, clubs[p["team"]]["code"], "crest")
            except MissingVerifiedMedia:
                unavailable.append(p["id"])
                print(f"Price watch: omitted official player ID {p['id']}; verified media unavailable")
                continue
        validated.append({"player": p, "action": item.get("action") or "MONITOR"})
    if not validated:
        raise MissingVerifiedMedia("No price candidates have verified current portraits and crests")
    return [_one_card(base, title, validated[n:n+3], clubs, fixtures,
                      gameweek, client, handles)
            for n in range(0, len(validated), 3)]


def receipt_send(images, caption, identity, webhook_url, journal_path, *,
                 session=None):
    """Send all pages as one Discord message, receipt-check and dedup."""
    if not images or len(images) > 10 or len(caption) > 2000:
        raise RuntimeError("Message violates Discord media/caption limits")
    if not webhook_url or not webhook_url.startswith("https://discord.com/api/webhooks/"):
        raise RuntimeError("Verified Discord webhook not configured")
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        prior = json.loads(journal_path.read_text()) if journal_path.is_file() else {}
    except (OSError, ValueError) as exc:
        raise RuntimeError("Cannot safely read prior Discord receipt ledger") from exc
    if identity in prior and prior[identity].get("message_id"):
        return prior[identity]["message_id"], False
    buffers = []
    try:
        files = []
        for idx, card in enumerate(images):
            out = BytesIO()
            card.save(out, "PNG", optimize=True)
            out.seek(0)
            buffers.append(out)
            files.append((f"files[{idx}]", (f"fpl_vortex_{idx+1}.png", out, "image/png")))
        client = session or requests.Session()
        response = client.post(webhook_url, params={"wait": "true"}, timeout=50,
                               data={"payload_json": json.dumps({
                                   "username": "FPL VORTEX", "content": caption,
                                   "allowed_mentions": {"parse": []}})},
                               files=files)
        response.raise_for_status()
        message_id = response.json().get("id")
        if not message_id:
            raise RuntimeError("Discord did not return a verified message ID")
        prior[identity] = {"message_id": str(message_id), "version": identity,
                           "published_at": datetime.now(timezone.utc).isoformat(),
                           "pages": len(images)}
        tmp = journal_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(prior, sort_keys=True))
        tmp.replace(journal_path)
        return str(message_id), True
    finally:
        for b in buffers:
            b.close()
