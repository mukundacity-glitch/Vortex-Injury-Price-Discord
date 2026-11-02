import hashlib
import json
import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

FPL_API_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
PREDICTION_URL = "https://livefpl.us/api/prices.json"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
DRY_RUN = os.environ.get("PRICE_CHANGE_DRY_RUN", "0") == "1"
FORCE_POST = os.environ.get("PRICE_CHANGE_FORCE", "0") == "1"

STATE_FILE = Path("data/price_change_state.json")
PREVIEW_FILE = Path("data/price_change_preview.png")
LOGO_FILE = Path("logo.png")

WIDTH, HEIGHT = 3200, 2400
BG = (255, 240, 215)
TEXT = (22, 28, 34)
MUTED = (63, 70, 77)
GREEN = (0, 143, 84)
RED = (192, 36, 62)
BORDER = (210, 191, 171)
SOFT_GREEN = (218, 245, 228)
SOFT_RED = (252, 224, 229)

LEFT = (50, 315, 1570, 2290)
RIGHT = (1630, 315, 3150, 2290)
ROWS = 10
ROW_HEIGHT = 174


def fetch_json(url):
    response = requests.get(
        url,
        headers={
            "User-Agent": "FPL-Vortex-Price-Change-Bot/1.0",
            "Accept": "application/json",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def download_image(url):
    if not url:
        return None
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "FPL-Vortex-Price-Change-Bot/1.0"},
            timeout=20,
        )
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGBA")
    except Exception as exc:
        print(f"Could not download image: {exc}")
        return None


def load_font(size, bold=False):
    paths = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]
    )
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def text_width(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def fit_font(draw, text, max_width, start_size, min_size=16, bold=False):
    for size in range(start_size, min_size - 1, -1):
        font = load_font(size, bold)
        if text_width(draw, text, font) <= max_width:
            return font
    return load_font(min_size, bold)


def paste_contain(base, image, box):
    if image is None:
        return
    x1, y1, x2, y2 = box
    image = image.copy()
    image.thumbnail((x2 - x1, y2 - y1), Image.Resampling.LANCZOS)
    x = x1 + ((x2 - x1) - image.width) // 2
    y = y1 + ((y2 - y1) - image.height) // 2
    base.alpha_composite(image, (x, y))


def player_image_url(photo):
    if not photo:
        return None
    photo_id = str(photo).removesuffix(".jpg")
    return (
        f"https://resources.premierleague.com/premierleague/photos/players/250x250/"
        f"p{photo_id}.png"
        if photo_id.isdigit()
        else None
    )


def team_logo_url(code):
    return (
        f"https://resources.premierleague.com/premierleague/badges/t{code}.png"
        if code
        else None
    )


def normalize_predictor_payload(payload):
    if isinstance(payload, list):
        return {
            str(item.get("id")): item
            for item in payload
            if item.get("id") is not None
        }
    if isinstance(payload, dict):
        if isinstance(payload.get("players"), list):
            return {
                str(item.get("id")): item
                for item in payload["players"]
                if item.get("id") is not None
            }
        return payload
    return {}


def estimate_prediction(player, total_managers):
    transfers_in = float(player.get("transfers_in_event") or 0)
    transfers_out = float(player.get("transfers_out_event") or 0)
    net = transfers_in - transfers_out
    ownership = max(float(player.get("selected_by_percent") or 0), 0.1)
    owned = max(total_managers * ownership / 100.0, 1.0)
    threshold = max(25000.0, owned * 0.012)
    return net / threshold


def build_candidates(data, predictor):
    teams = {team["id"]: team for team in data.get("teams", [])}
    total_managers = float(data.get("total_players") or 1)
    candidates = []

    for player in data.get("elements", []):
        player_id = str(player.get("id"))
        external = predictor.get(player_id) or predictor.get(
            str(player.get("code")), {}
        )
        prediction = None
        source = "FPL transfer-data fallback"

        if isinstance(external, dict):
            for key in ("progress_tonight", "prediction", "predicted_progress"):
                if external.get(key) is not None:
                    prediction = float(external[key])
                    source = "LiveFPL predictor"
                    break

        if prediction is None:
            prediction = estimate_prediction(player, total_managers)

        team = teams.get(player.get("team"), {})
        candidates.append(
            {
                "id": player_id,
                "name": " ".join(
                    str(player.get("web_name") or player.get("second_name") or "Unknown").split()
                ),
                "team": team.get("name", "Unknown"),
                "team_code": team.get("code"),
                "now_cost": player.get("now_cost", 0),
                "photo": player.get("photo"),
                "prediction": prediction,
                "source": source,
            }
        )

    rises = sorted(
        (item for item in candidates if item["prediction"] > 0),
        key=lambda item: item["prediction"],
        reverse=True,
    )[:ROWS]
    falls = sorted(
        (item for item in candidates if item["prediction"] < 0),
        key=lambda item: item["prediction"],
    )[:ROWS]
    return rises, falls


def likelihood(progress):
    value = abs(progress) * 100
    if value >= 100:
        return "Very Likely"
    if value >= 80:
        return "Likely"
    if value >= 60:
        return "Possible"
    return "Monitor"


def format_price(cost):
    try:
        return f"£{float(cost) / 10:.1f}m"
    except Exception:
        return "£0.0m"


def draw_row(canvas, draw, item, box, direction, assets):
    x1, y1, x2, y2 = box
    accent = GREEN if direction == "rise" else RED
    soft = SOFT_GREEN if direction == "rise" else SOFT_RED

    draw.rounded_rectangle(
        (x1, y1, x2, y2),
        radius=25,
        fill=(255, 255, 255),
        outline=BORDER,
        width=3,
    )
    draw.rectangle((x1, y1, x1 + 15, y2), fill=accent)

    paste_contain(
        canvas,
        assets.get(("photo", item["id"])),
        (x1 + 32, y1 + 18, x1 + 150, y2 - 18),
    )

    player_name = item["name"]
    name_font = fit_font(draw, player_name, 620, 57, 34, True)
    draw.text((x1 + 180, y1 + 18), player_name, font=name_font, fill=TEXT)

    crest_x = x1 + 182
    paste_contain(
        canvas,
        assets.get(("crest", item["team_code"])),
        (crest_x, y1 + 98, crest_x + 40, y1 + 138),
    )
    meta = f"{item['team']}  •  {format_price(item['now_cost'])}"
    meta_font = fit_font(draw, meta, 620, 35, 24, True)
    draw.text((crest_x + 52, y1 + 98), meta, font=meta_font, fill=MUTED)

    status = likelihood(item["prediction"])
    status_font = fit_font(draw, status, 260, 33, 26, True)
    status_width = text_width(draw, status, status_font)
    pill_right = x2 - 322
    pill_left = pill_right - max(status_width + 48, 205)
    draw.rounded_rectangle(
        (pill_left, y1 + 52, pill_right, y1 + 110),
        radius=25,
        fill=soft,
    )
    draw.text(
        (pill_left + (pill_right - pill_left - status_width) // 2, y1 + 62),
        status,
        font=status_font,
        fill=accent,
    )

    target = f"{abs(item['prediction']) * 100:.1f}%"
    target_font = fit_font(draw, target, 265, 54, 35, True)
    target_width = text_width(draw, target, target_font)
    target_right = x2 - 30
    draw.text(
        (target_right - target_width, y1 + 58),
        target,
        font=target_font,
        fill=accent,
    )
    draw.text(
        (x2 - 260, y1 + 24),
        "TARGET %",
        font=load_font(26, True),
        fill=MUTED,
    )


def create_card(rises, falls, date_text, source_label):
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), BG + (255,))
    draw = ImageDraw.Draw(canvas)

    if LOGO_FILE.exists():
        try:
            logo = Image.open(LOGO_FILE).convert("RGBA")
            paste_contain(canvas, logo, (70, 42, 320, 226))
        except Exception as exc:
            print(f"Could not load logo.png: {exc}")

    title = "PRICE CHANGE PREDICTIONS"
    draw.text(
        (365, 55),
        title,
        font=fit_font(draw, title, WIDTH - 430, 80, 57, True),
        fill=TEXT,
    )
    draw.text(
        (370, 154),
        date_text,
        font=load_font(52, True),
        fill=TEXT,
    )
    draw.text(
        (370, 235),
        "Fantasy Premier League • daily price movement watch",
        font=load_font(34),
        fill=MUTED,
    )

    for box, color in ((LEFT, GREEN), (RIGHT, RED)):
        draw.rounded_rectangle(
            box,
            radius=34,
            fill=(255, 255, 255),
            outline=BORDER,
            width=4,
        )
        draw.rounded_rectangle(
            (box[0], box[1], box[2], box[1] + 110),
            radius=34,
            fill=color,
        )
        draw.rectangle(
            (box[0], box[1] + 65, box[2], box[1] + 110),
            fill=color,
        )

    section_font = load_font(58, True)
    draw.text(
        (LEFT[0] + 38, LEFT[1] + 18),
        "▲  PRICE RISES",
        font=section_font,
        fill=(255, 255, 255),
    )
    draw.text(
        (RIGHT[0] + 38, RIGHT[1] + 18),
        "▼  PRICE DROPS",
        font=section_font,
        fill=(255, 255, 255),
    )

    header_font = load_font(30, True)
    for column in (LEFT, RIGHT):
        draw.text(
            (column[0] + 180, 455),
            "PLAYER / CLUB",
            font=header_font,
            fill=TEXT,
        )
        draw.text(
            (column[0] + 860, 455),
            "LIKELIHOOD",
            font=header_font,
            fill=TEXT,
        )
        draw.text(
            (column[2] - 300, 455),
            "PREDICTION",
            font=header_font,
            fill=TEXT,
        )

    assets = {}
    for item in rises + falls:
        photo_key = ("photo", item["id"])
        if photo_key not in assets:
            assets[photo_key] = download_image(player_image_url(item["photo"]))
        crest_key = ("crest", item["team_code"])
        if crest_key not in assets:
            assets[crest_key] = download_image(team_logo_url(item["team_code"]))

    for index, item in enumerate(rises):
        row_top = 520 + index * ROW_HEIGHT
        draw_row(
            canvas,
            draw,
            item,
            (LEFT[0] + 25, row_top, LEFT[2] - 25, row_top + 160),
            "rise",
            assets,
        )

    for index, item in enumerate(falls):
        row_top = 520 + index * ROW_HEIGHT
        draw_row(
            canvas,
            draw,
            item,
            (RIGHT[0] + 25, row_top, RIGHT[2] - 25, row_top + 160),
            "fall",
            assets,
        )

    footer = (
        f"FPL VORTEX  •  {source_label}  •  Prediction is a guide, not a guarantee"
        f"  •  Price-change check: 00:00 UK"
    )
    draw.text(
        (70, 2330),
        footer,
        font=fit_font(draw, footer, WIDTH - 140, 32, 23, True),
        fill=TEXT,
    )
    return canvas.convert("RGB")


def load_state():
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def send_discord(card, date_text):
    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError("DISCORD_WEBHOOK_URL secret is missing")

    buffer = BytesIO()
    card.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)

    response = requests.post(
        DISCORD_WEBHOOK_URL,
        data={
            "payload_json": json.dumps(
                {
                    "username": "FPL Vortex Price Changes",
                    "content": f"📈 **FPL VORTEX • PRICE CHANGE PREDICTIONS** — {date_text}",
                    "allowed_mentions": {"parse": []},
                }
            )
        },
        files={
            "files[0]": (
                "fpl_vortex_price_changes_4k.png",
                buffer,
                "image/png",
            )
        },
        timeout=30,
    )
    response.raise_for_status()


def main():
    data = fetch_json(FPL_API_URL)

    try:
        predictor = normalize_predictor_payload(fetch_json(PREDICTION_URL))
    except Exception as exc:
        print(
            "LiveFPL predictor unavailable; using official FPL transfer-data "
            f"fallback: {exc}"
        )
        predictor = {}

    rises, falls = build_candidates(data, predictor)
    if not rises and not falls:
        raise RuntimeError("No price-change candidates were found.")

    london_now = datetime.now(ZoneInfo("Europe/London"))
    date_text = london_now.strftime("%A, %-d %B %Y")
    source_label = (
        "LiveFPL predictor + official FPL player data"
        if predictor
        else "official FPL transfer-data fallback"
    )

    card = create_card(rises, falls, date_text, source_label)
    PREVIEW_FILE.parent.mkdir(parents=True, exist_ok=True)
    card.save(PREVIEW_FILE, format="PNG", optimize=True)

    signature_payload = {
        "date": date_text,
        "rises": [(x["id"], round(x["prediction"], 4)) for x in rises],
        "falls": [(x["id"], round(x["prediction"], 4)) for x in falls],
    }
    signature = hashlib.sha256(
        json.dumps(signature_payload, sort_keys=True).encode()
    ).hexdigest()

    state = load_state()
    if not FORCE_POST and state.get("date") == date_text and state.get("signature") == signature:
        print("Price-change prediction is unchanged; no duplicate post sent.")
        return

    if DRY_RUN:
        print(f"Preview created: {PREVIEW_FILE}")
        print("Rises:", ", ".join(item["name"] for item in rises))
        print("Falls:", ", ".join(item["name"] for item in falls))
        return

    if os.getenv("FPL_BRANDED_POSTS_ENABLED", "false").lower() == "true":
        # Only genuine independent LiveFPL predictions are represented as
        # price forecast progress. Heuristic transfer-volume fallback remains
        # in legacy mode but is not labeled a verified market forecast here.
        trustworthy = [x for x in (rises + falls)
                       if x.get("source") == "LiveFPL predictor"]
        if not predictor or not trustworthy:
            raise RuntimeError("Price forecast feed unverified; hold branded post")
        from branded_renderer import render_batches, receipt_send
        upcoming = fetch_json("https://fantasy.premierleague.com/api/fixtures/")
        records = [dict(item, action="MONITOR") for item in trustworthy]
        artwork = render_batches(
            "FPL PRICE MOVEMENT • WATCH", records, data, upcoming)
        # Version is derived from actual provider values, not date/time
        # or scheduled run identity. Repeated run cannot resend old content.
        model = [(x["id"], round(x["prediction"], 4)) for x in trustworthy]
        version = hashlib.sha256(json.dumps(sorted(model)).encode()).hexdigest()[:24]
        next_event = next((e["id"] for e in data.get("events", [])
                           if e.get("is_next") and not e.get("finished")), None)
        if next_event is None:
            raise RuntimeError("No verified upcoming gameweek")
        caption = (
            f"GW{next_event}: {len(trustworthy)} verified price-watch candidates.\n"
            "MONITOR predicted changes; forecasts are not guaranteed.\n"
            "Confirm transfers and selling values before moving.\n"
            "#FPL #FPLVortex #PriceChanges #Transfers")
        message_id, published = receipt_send(
            artwork, caption, f"price:{next_event}:{version}",
            DISCORD_WEBHOOK_URL, Path("data/branded_discord_deliveries.json"))
        print(f"Branded price forecast delivery={published}; receipt ID={message_id}")
    else:
        send_discord(card, date_text)
    save_state(
        {
            "date": date_text,
            "signature": signature,
            "posted_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    print("Price-change prediction card processed successfully.")


if __name__ == "__main__":
    main()
