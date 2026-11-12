import json
import os
import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont


FPL_API_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
FPL_FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/?future=1"

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
RUN_MODE = os.environ.get("TEST_MODE", "monitor").lower()

STATE_FILE = Path("data/injury_state.json")
X_DRAFT_FILE = Path("data/x_drafts.json")
LOGO_FILE = Path("logo.png")


WIDTH = 1600

BACKGROUND = (7, 13, 39)
CARD = (10, 26, 62)
ROW = (10, 26, 62)
BORDER = (43, 205, 247)

WHITE = (240, 247, 255)
MUTED = (163, 190, 225)
PLAYER_COLOR = (42, 225, 251)
BLACK = (240, 247, 255)

RED = (222, 55, 55)
YELLOW = (235, 185, 45)
GREEN = (55, 184, 100)


def _neon_injury_canvas(height):
    """Only the graphic backdrop changes; original injury content is retained."""
    top = (5, 12, 37)
    bottom = (37, 11, 78)
    column = Image.new("RGBA", (1, height))
    column.putdata([tuple(round(top[i]*(1-t) + bottom[i]*t) for i in range(3))+(255,)
                    for t in (y/max(1,height-1) for y in range(height))])
    canvas = column.resize((WIDTH, height))
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.rounded_rectangle((11, 11, WIDTH-12, height-12),
                           radius=22, outline=(155, 66, 249, 255), width=4)
    return canvas

FDR_COLORS = {
    1: (64, 190, 105),
    2: (116, 201, 93),
    3: (235, 194, 55),
    4: (239, 137, 52),
    5: (220, 61, 61),
}


CATEGORY_STYLE = {
    "INJURY": {
        "label": "INJURY UPDATE",
        "symbol": "!",
        "header": RED,
        "hash": "#FPL #FPLNews #FPLInjury",
    },
    "DOUBT": {
        "label": "FITNESS DOUBT",
        "symbol": "!",
        "header": YELLOW,
        "hash": "#FPL #FPLNews #FPLInjury",
    },
    "SUSPENSION": {
        "label": "SUSPENSION UPDATE",
        "symbol": "X",
        "header": RED,
        "hash": "#FPL #FPLNews #FPLSuspension",
    },
    "AVAILABLE": {
        "label": "AVAILABLE",
        "symbol": "✓",
        "header": GREEN,
        "hash": "#FPL #FPLNews",
    },
}


POSITION_TEXT = {
    1: "GK",
    2: "DEF",
    3: "MID",
    4: "FWD",
}


STATUS_TEXT = {
    "a": "AVAILABLE",
    "d": "DOUBT",
    "i": "INJURED",
    "s": "SUSPENDED",
    "u": "UNAVAILABLE",
}


def fetch_json(url):
    response = requests.get(
        url,
        headers={
            "User-Agent": "FPL-Vortex-Injury-Bot/1.0",
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
            headers={
                "User-Agent": "FPL-Vortex-Injury-Bot/1.0",
            },
            timeout=20,
        )

        response.raise_for_status()

        return Image.open(
            BytesIO(response.content)
        ).convert("RGBA")

    except Exception as exc:
        print(
            f"Could not download image: {exc}"
        )

        return None


def load_font(size, bold=False):
    if bold:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]

    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(
                path,
                size,
            )

    return ImageFont.load_default()


def clean_text(text):
    return re.sub(
        r"\s+",
        " ",
        (text or "").strip(),
    )


def text_width(draw, text, font):
    box = draw.textbbox(
        (0, 0),
        text,
        font=font,
    )

    return box[2] - box[0]


def fit_font(
    draw,
    text,
    max_width,
    start_size,
    min_size=16,
    bold=False,
):
    size = start_size

    while size >= min_size:
        font = load_font(
            size,
            bold=bold,
        )

        if text_width(
            draw,
            text,
            font,
        ) <= max_width:
            return font

        size -= 1

    return load_font(
        min_size,
        bold=bold,
    )


def shorten_text(
    text,
    max_chars,
):
    text = clean_text(text)

    if not text:
        return "No update provided"

    if len(text) <= max_chars:
        return text

    trimmed = text[:max_chars].rsplit(
        " ",
        1,
    )[0]

    return f"{trimmed}..."


def get_position(element_type):
    return POSITION_TEXT.get(
        element_type,
        "UNK",
    )


def get_status(status):
    return STATUS_TEXT.get(
        status,
        status or "UNKNOWN",
    )


def format_price(now_cost):
    try:
        return f"£{float(now_cost) / 10:.1f}m"
    except Exception:
        return "£0.0m"


def format_ownership(value):
    try:
        return f"{float(value):.1f}%"
    except Exception:
        return "0.0%"


def get_player_image(photo):
    if not photo:
        return None

    photo_id = str(photo)

    if photo_id.endswith(".jpg"):
        photo_id = photo_id[:-4]

    if not photo_id.isdigit():
        return None

    return (
        "https://resources.premierleague.com/"
        "premierleague/photos/players/250x250/"
        f"p{photo_id}.png"
    )


def get_team_logo(team_code):
    if not team_code:
        return None

    return (
        "https://resources.premierleague.com/"
        f"premierleague/badges/t{team_code}.png"
    )


def get_fdr_color(difficulty):
    try:
        value = int(difficulty)
    except Exception:
        value = 3

    return FDR_COLORS.get(
        value,
        FDR_COLORS[3],
    )


def extract_expected_return(news):
    news = clean_text(news)

    if not news:
        return "TBC"

    patterns = [
        r"\b\d{1,2}\s+"
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|"
        r"Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
        r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
        r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\b",

        r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|"
        r"Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
        r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
        r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+\d{1,2}\b",

        r"\bGW\s*\d+\b",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            news,
            re.IGNORECASE,
        )

        if match:
            return match.group(0)

    return "TBC"


def build_player_record(
    player,
    teams_by_id,
):
    team = teams_by_id.get(
        player.get("team"),
        {},
    )

    return {
        "name": (
            f"{player.get('first_name', '').strip()} "
            f"{player.get('second_name', '').strip()}"
        ).strip(),

        "team": team.get(
            "name",
            "Unknown",
        ),

        "team_short": team.get(
            "short_name",
            "UNK",
        ),

        "team_code": team.get(
            "code",
        ),

        "team_id": player.get(
            "team",
        ),

        "position": get_position(
            player.get("element_type")
        ),

        "now_cost": player.get(
            "now_cost",
            0,
        ),

        "ownership": player.get(
            "selected_by_percent",
            "0.0",
        ),

        "chance_next": player.get(
            "chance_of_playing_next_round",
        ),

        "chance_this": player.get(
            "chance_of_playing_this_round",
        ),

        "status": player.get(
            "status"
        ) or "a",

        "news": clean_text(
            player.get("news")
        ),

        "news_added": player.get(
            "news_added"
        ),

        "photo": player.get(
            "photo"
        ),

        "code": player.get(
            "code"
        ),
    }


def is_relevant(record):
    if not record:
        return False

    return (
        record.get("status") != "a"
        or record.get("chance_next") is not None
        or record.get("chance_this") is not None
        or bool(record.get("news"))
    )


def classify_category(
    old_record,
    new_record,
):
    status = new_record.get(
        "status",
        "a",
    )

    if status == "i":
        return "INJURY"

    if status == "d":
        return "DOUBT"

    if status == "s":
        return "SUSPENSION"

    if status == "a":

        if old_record:

            old_status = old_record.get(
                "status",
                "a",
            )

            if old_status in (
                "i",
                "d",
                "u",
            ):
                return "AVAILABLE"

            if (
                old_record.get(
                    "chance_next"
                )
                != new_record.get(
                    "chance_next"
                )
            ):
                return "AVAILABLE"

        return "AVAILABLE"

    return "INJURY"


def get_next_fixture(
    player_team_id,
    fixtures,
    teams_by_id,
):
    options = []

    for fixture in fixtures:

        if fixture.get("finished"):
            continue

        event = fixture.get(
            "event"
        )

        if event is None:
            continue

        home = fixture.get(
            "team_h"
        )

        away = fixture.get(
            "team_a"
        )

        if (
            home != player_team_id
            and away != player_team_id
        ):
            continue

        if home == player_team_id:

            opponent = teams_by_id.get(
                away,
                {},
            ).get(
                "short_name",
                "UNK",
            )

            home_away = "H"

            difficulty = fixture.get(
                "team_h_difficulty"
            )

        else:

            opponent = teams_by_id.get(
                home,
                {},
            ).get(
                "short_name",
                "UNK",
            )

            home_away = "A"

            difficulty = fixture.get(
                "team_a_difficulty"
            )

        options.append(
            {
                "event": event,
                "opponent": opponent,
                "home_away": home_away,
                "difficulty": difficulty,
                "kickoff": fixture.get(
                    "kickoff_time"
                ),
            }
        )

    options.sort(
        key=lambda item: (
            item["event"],
            item["kickoff"] or "",
        )
    )

    return (
        options[0]
        if options
        else None
    )


def build_takeaway(category):
    if category == "INJURY":
        return (
            "Monitor the next confirmed update before making a transfer."
        )

    if category == "DOUBT":
        return (
            "Hold fire and monitor final team news before the deadline."
        )

    if category == "SUSPENSION":
        return (
            "Check the suspension timeline before using a transfer."
        )

    return (
        "Availability is positive, but monitor final team news."
    )


def load_logo():
    if not LOGO_FILE.exists():
        print(
            "logo.png not found. Continuing without logo."
        )

        return None

    try:
        return Image.open(
            LOGO_FILE
        ).convert("RGBA")
    except Exception as exc:
        print(
            f"Could not load logo.png: {exc}"
        )

        return None


def paste_contain(
    base,
    image,
    box,
):
    if image is None:
        return

    x1, y1, x2, y2 = box

    max_width = x2 - x1
    max_height = y2 - y1

    image = image.copy()

    image.thumbnail(
        (
            max_width,
            max_height,
        ),
        Image.Resampling.LANCZOS,
    )

    x = x1 + (
        max_width - image.width
    ) // 2

    y = y1 + (
        max_height - image.height
    ) // 2

    base.alpha_composite(
        image,
        (
            x,
            y,
        ),
    )


def create_card(
    category,
    players,
    gameweek,
):
    """Create a cleaner, more readable Discord injury graphic."""
    style = CATEGORY_STYLE[category]
    logo = load_logo()

    # ---------------------------------------------------------
    # COMPACT 16:9-STYLE DISCORD CARD
    # ---------------------------------------------------------

    header_height = 120
    row_height = 145
    footer_height = 19

    height = (
        header_height
        + row_height * len(players)
        + footer_height
        + 20
    )

    canvas = _neon_injury_canvas(height)

    draw = ImageDraw.Draw(canvas)

    # ---------------------------------------------------------
    # HEADER
    # ---------------------------------------------------------

    draw.rectangle(
        (
            0,
            0,
            WIDTH,
            header_height,
        ),
        fill=(9, 22, 54, 255),
    )

    # Larger real FPL Vortex logo.
    paste_contain(
        canvas,
        logo,
        (
            25,
            8,
            165,
            112,
        ),
    )

    header_text = (
        f"{style['symbol']} "
        f"{style['label']}"
    )

    header_font = fit_font(
        draw,
        header_text,
        1050,
        58,
        min_size=42,
        bold=True,
    )

    draw.text(
        (
            175,
            29,
        ),
        header_text,
        font=header_font,
        fill=BLACK,
    )

    # Gameweek.
    gw_text = f"GW{gameweek}"

    gw_font = load_font(
        34,
        bold=True,
    )

    gw_width = text_width(
        draw,
        gw_text,
        gw_font,
    )

    draw.rounded_rectangle(
        (
            WIDTH - gw_width - 65,
            35,
            WIDTH - 25,
            88,
        ),
        radius=14,
        fill=(9, 22, 54, 255),
    )

    draw.text(
        (
            WIDTH - gw_width - 45,
            43,
        ),
        gw_text,
        font=gw_font,
        fill=BLACK,
    )

    # ---------------------------------------------------------
    # PLAYER ROWS
    # ---------------------------------------------------------

    y = header_height + 8

    player_font = load_font(
        42,
        bold=True,
    )

    meta_font = load_font(
        25,
        bold=True,
    )

    update_font = load_font(
        23,
        bold=False,
    )

    small_font = load_font(
        20,
        bold=True,
    )

    for player in players:

        row_top = y

        row_bottom = (
            y
            + row_height
            - 7
        )

        draw.rounded_rectangle(
            (
                30,
                row_top,
                WIDTH - 30,
                row_bottom,
            ),
            radius=18,
            fill=ROW + (255,),
            outline=(185, 188, 194, 255),
            width=2,
        )

        # -----------------------------------------------------
        # PLAYER PHOTO
        # -----------------------------------------------------

        player_image = download_image(
            get_player_image(
                player.get("photo")
            )
        )

        image_box = 108

        if player_image:

            player_image.thumbnail(
                (
                    image_box,
                    image_box,
                ),
                Image.Resampling.LANCZOS,
            )

            mask = Image.new(
                "L",
                (
                    image_box,
                    image_box,
                ),
                0,
            )

            mask_draw = ImageDraw.Draw(
                mask
            )

            mask_draw.ellipse(
                (
                    0,
                    0,
                    image_box - 1,
                    image_box - 1,
                ),
                fill=255,
            )

            photo_layer = Image.new(
                "RGBA",
                (
                    image_box,
                    image_box,
                ),
                (0, 0, 0, 0),
            )

            photo_layer.alpha_composite(
                player_image,
                (
                    (
                        image_box
                        - player_image.width
                    ) // 2,
                    (
                        image_box
                        - player_image.height
                    ) // 2,
                ),
            )

            photo_layer.putalpha(
                mask
            )

            canvas.alpha_composite(
                photo_layer,
                (
                    48,
                    row_top + 12,
                ),
            )

        # -----------------------------------------------------
        # PLAYER INFORMATION
        # -----------------------------------------------------

        text_x = 180

        # Reserve right side for ownership/FDR.
        main_width = 1080

        player_name = shorten_text(
            player.get("name"),
            32,
        )

        player_name_font = fit_font(
            draw,
            player_name,
            main_width,
            42,
            min_size=30,
            bold=True,
        )

        draw.text(
            (
                text_x,
                row_top + 9,
            ),
            player_name,
            font=player_name_font,
            fill=PLAYER_COLOR,
        )

        # -----------------------------------------------------
        # TEAM CREST
        # -----------------------------------------------------

        crest = download_image(
            get_team_logo(
                player.get("team_code")
            )
        )

        crest_x = text_x
        crest_y = row_top + 60
        crest_size = 27

        if crest:

            paste_contain(
                canvas,
                crest,
                (
                    crest_x,
                    crest_y,
                    crest_x + crest_size,
                    crest_y + crest_size,
                ),
            )

            crest_x += 37

        metadata = (
            f"{player['team']} • "
            f"{player['position']} • "
            f"{format_price(player['now_cost'])}"
        )

        metadata_font = fit_font(
            draw,
            metadata,
            main_width,
            25,
            min_size=18,
            bold=True,
        )

        draw.text(
            (
                crest_x,
                row_top + 58,
            ),
            metadata,
            font=metadata_font,
            fill=BLACK,
        )

        # -----------------------------------------------------
        # UPDATE
        # -----------------------------------------------------

        chance = player.get(
            "chance_next"
        )

        chance_text = (
            "TBC"
            if chance is None
            else f"{chance}%"
        )

        return_text = extract_expected_return(
            player.get("news")
        )

        if player["status"] == "s":

            update_line = (
                f"SUSPENDED • "
                f"Return {return_text}"
            )

        elif player["status"] == "a":

            update_line = (
                f"AVAILABLE • "
                f"Chance {chance_text}"
            )

        else:

            news = shorten_text(
                player.get("news"),
                48,
            )

            update_line = (
                f"{news} • "
                f"{chance_text} • "
                f"Return {return_text}"
            )

        update_line = shorten_text(
            update_line,
            110,
        )

        update_actual = fit_font(
            draw,
            update_line,
            main_width,
            23,
            min_size=17,
            bold=False,
        )

        draw.text(
            (
                text_x,
                row_top + 94,
            ),
            update_line,
            font=update_actual,
            fill=BLACK,
        )

        # -----------------------------------------------------
        # OWNERSHIP
        # -----------------------------------------------------

        ownership = format_ownership(
            player.get(
                "ownership",
                "0.0",
            )
        )

        delta = player.get(
            "ownership_delta"
        )

        if delta is None:

            ownership_text = (
                f"OWN {ownership}"
            )

        else:

            sign = (
                "+"
                if delta > 0
                else ""
            )

            ownership_text = (
                f"OWN {ownership} "
                f"• Δ {sign}{delta:.1f}pp"
            )

        ownership_font = fit_font(
            draw,
            ownership_text,
            300,
            20,
            min_size=15,
            bold=True,
        )

        ownership_width = text_width(
            draw,
            ownership_text,
            ownership_font,
        )

        draw.text(
            (
                WIDTH
                - ownership_width
                - 65,
                row_top + 20,
            ),
            ownership_text,
            font=ownership_font,
            fill=MUTED,
        )

        # -----------------------------------------------------
        # FDR
        # -----------------------------------------------------

        fixture = player.get(
            "fixture"
        )

        if fixture:

            try:
                fdr = int(
                    fixture.get(
                        "difficulty",
                        3,
                    )
                )
            except Exception:
                fdr = 3

            fdr = max(
                1,
                min(
                    5,
                    fdr,
                ),
            )

            fdr_x = WIDTH - 220

            draw.text(
                (
                    fdr_x,
                    row_top + 58,
                ),
                "FDR",
                font=small_font,
                fill=MUTED,
            )

            circle_x = (
                fdr_x + 55
            )

            draw.ellipse(
                (
                    circle_x,
                    row_top + 60,
                    circle_x + 22,
                    row_top + 82,
                ),
                fill=get_fdr_color(
                    fdr
                ),
            )

            draw.text(
                (
                    circle_x + 31,
                    row_top + 55,
                ),
                f"{fdr}/5",
                font=small_font,
                fill=BLACK,
            )

        y += row_height

    # ---------------------------------------------------------
    # COMPACT FOOTER
    # ---------------------------------------------------------

    footer_y = height - footer_height

    draw.rectangle(
        (
            0,
            footer_y,
            WIDTH,
            height,
        ),
        fill=(9, 22, 54, 255),
    )

    footer_font = fit_font(
        draw,
        "FPL VORTEX",
        190,
        17,
        min_size=13,
        bold=True,
    )

    draw.text(
        (
            28,
            footer_y - 3,
        ),
        "FPL VORTEX",
        font=footer_font,
        fill=BLACK,
    )

    takeaway = build_takeaway(category)
    takeaway_full = (
        "  •  FPL TAKEAWAY: "
        + shorten_text(takeaway, 58)
    )

    channel_width = text_width(
        draw,
        "FPL VORTEX",
        footer_font,
    )

    takeaway_font = fit_font(
        draw,
        takeaway_full,
        900,
        17,
        min_size=9,
        bold=True,
    )

    draw.text(
        (
            40 + channel_width,
            footer_y - 3,
        ),
        takeaway_full,
        font=takeaway_font,
        fill=RED,
    )

    right_footer = (
        f"Official FPL Data • "
        f"{style['hash']}"
    )

    right_footer_font = fit_font(
        draw,
        right_footer,
        470,
        17,
        min_size=9,
        bold=True,
    )

    right_width = text_width(
        draw,
        right_footer,
        right_footer_font,
    )

    draw.text(
        (
            WIDTH
            - right_width
            - 28,
            footer_y - 3,
        ),
        right_footer,
        font=right_footer_font,
        fill=BLACK,
    )

    return canvas.convert(
        "RGB"
    )


def create_news_page(grouped_players, gameweek):
    """Render all injury categories on one Discord graphic with a shared color."""
    sections = [
        (category, grouped_players[category])
        for category in CATEGORY_STYLE
        if grouped_players.get(category)
    ]
    if not sections:
        raise ValueError("No injury news to render")

    header_height = 120
    subheader_height = 72
    row_height = 145
    row_padding = 8
    section_gap = 10
    footer_height = 36
    height = (
        header_height
        + sum(
            section_gap + subheader_height + row_height * len(players) + row_padding
            for _, players in sections
        )
        + footer_height
    )
    canvas = _neon_injury_canvas(height)
    draw = ImageDraw.Draw(canvas)

    # Keep one main header and one gameweek badge for the complete update.
    draw.rectangle((0, 0, WIDTH, header_height), fill=(9, 22, 54, 255))
    paste_contain(canvas, load_logo(), (25, 8, 165, 112))
    title = "FPL VORTEX • INJURY NEWS"
    title_font = fit_font(draw, title, 1050, 58, min_size=32, bold=True)
    draw.text((175, 29), title, font=title_font, fill=BLACK)
    gw_text = f"GW{gameweek}"
    gw_font = load_font(34, bold=True)
    gw_width = text_width(draw, gw_text, gw_font)
    draw.rounded_rectangle(
        (WIDTH - gw_width - 65, 35, WIDTH - 25, 88),
        radius=14,
        fill=(9, 22, 54, 255),
    )
    draw.text(
        (WIDTH - gw_width - 45, 43), gw_text, font=gw_font, fill=BLACK
    )

    y = header_height
    for category, players in sections:
        y += section_gap
        style = CATEGORY_STYLE[category]
        draw.rectangle((0, y, WIDTH, y + subheader_height), fill=(9, 22, 54, 255))
        subtitle = f"{style['symbol']} {style['label']}"
        subtitle_font = fit_font(draw, subtitle, 760, 42, min_size=28, bold=True)
        draw.text((30, y + 12), subtitle, font=subtitle_font, fill=BLACK)
        takeaway = build_takeaway(category)
        takeaway_font = fit_font(
            draw, takeaway, 680, 20, min_size=14, bold=True
        )
        takeaway_width = text_width(draw, takeaway, takeaway_font)
        draw.text(
            (WIDTH - takeaway_width - 30, y + 24),
            takeaway,
            font=takeaway_font,
            fill=BLACK,
        )
        y += subheader_height

        # Reuse the existing player-row layout; only the category wrappers change.
        category_card = create_card(category, players, gameweek)
        row_area = category_card.crop(
            (0, header_height, WIDTH, header_height + row_height * len(players) + row_padding)
        )
        canvas.alpha_composite(row_area.convert("RGBA"), (0, y))
        y += row_area.height

    draw.rectangle(
        (0, height - footer_height, WIDTH, height), fill=(9, 22, 54, 255)
    )
    footer_text = "FPL VORTEX  •  Official FPL Data  •  #FPL #FPLNews #FPLInjury"
    if "SUSPENSION" in grouped_players:
        footer_text += " #FPLSuspension"
    footer_font = fit_font(draw, footer_text, WIDTH - 60, 20, min_size=15, bold=True)
    draw.text(
        (30, height - footer_height + 5),
        footer_text,
        font=footer_font,
        fill=BLACK,
    )
    return canvas.convert("RGB")


def send_discord_card(
    card,
    category,
):
    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError(
            "DISCORD_WEBHOOK_URL secret is missing"
        )

    buffer = BytesIO()

    card.save(
        buffer,
        format="PNG",
        optimize=True,
    )

    buffer.seek(0)

    if category is None:
        message_text = "FPL Vortex • INJURY NEWS"
    else:
        style = CATEGORY_STYLE[category]
        message_text = (
            f"{style['symbol']} "
            f"FPL Vortex • "
            f"{style['label']}"
        )

    payload = {
        "username": "FPL Vortex Injury News",
        "content": message_text,
        "allowed_mentions": {
            "parse": [],
        },
    }

    response = requests.post(
        DISCORD_WEBHOOK_URL,
        data={
            "payload_json": json.dumps(
                payload
            ),
        },
        files={
            "files[0]": (
                "fpl_vortex_injury.png",
                buffer,
                "image/png",
            ),
        },
        timeout=30,
    )

    response.raise_for_status()


def build_x_post(
    category,
    players,
):
    style = CATEGORY_STYLE[
        category
    ]

    names = ", ".join(
        player["name"]
        for player in players
    )

    chance_values = []

    for player in players:
        chance = player.get(
            "chance_next"
        )

        if chance is not None:
            chance_values.append(
                str(chance)
            )

    chance_text = ""

    if chance_values:
        chance_text = (
            f" | Chance "
            f"{'/'.join(chance_values[:3])}%"
        )

    text = (
        f"{style['symbol']} "
        f"{style['label']}\n"
        f"{names}"
        f"{chance_text}\n"
        f"{build_takeaway(category)}\n"
        f"{style['hash']}"
    )

    if len(text) <= 275:
        return text

    compact_names = ", ".join(
        player["name"]
        for player in players[:3]
    )

    text = (
        f"{style['symbol']} "
        f"{style['label']}\n"
        f"{compact_names}\n"
        f"{style['hash']}"
    )

    return text[:275]


def save_x_draft(
    category,
    players,
    gameweek,
):
    X_DRAFT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    drafts = {}

    if X_DRAFT_FILE.exists():
        try:
            drafts = json.loads(
                X_DRAFT_FILE.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            drafts = {}

    key = (
        f"{datetime.now(timezone.utc).isoformat()}"
        f"_{category}"
    )

    drafts[key] = {
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "gameweek": gameweek,
        "category": category,
        "players": [
            player["name"]
            for player in players
        ],
        "text": build_x_post(
            category,
            players,
        ),
    }

    X_DRAFT_FILE.write_text(
        json.dumps(
            drafts,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def find_preview_players(
    data,
    teams_by_id,
):
    selected = []

    for player in data.get(
        "elements",
        []
    ):

        record = build_player_record(
            player,
            teams_by_id,
        )

        if not is_relevant(
            record
        ):
            continue

        selected.append(
            record
        )

        if len(selected) >= 12:
            break

    return selected


def current_gameweek(data):
    current = next(
        (
            event
            for event in data.get(
                "events",
                []
            )
            if event.get(
                "is_current"
            )
        ),
        None,
    )

    if current:
        return current.get(
            "id",
            "?",
        )

    next_event = next(
        (
            event
            for event in data.get(
                "events",
                []
            )
            if event.get(
                "is_next"
            )
        ),
        None,
    )

    if next_event:
        return next_event.get(
            "id",
            "?",
        )

    unfinished = next(
        (
            event
            for event in data.get(
                "events",
                []
            )
            if not event.get(
                "finished"
            )
        ),
        None,
    )

    if unfinished:
        return unfinished.get(
            "id",
            "?",
        )

    return "?"


def run_preview():
    data = fetch_json(
        FPL_API_URL
    )

    fixtures = fetch_json(
        FPL_FIXTURES_URL
    )

    teams_by_id = {
        team["id"]: team
        for team in data.get(
            "teams",
            []
        )
    }

    gameweek = current_gameweek(
        data
    )

    players = find_preview_players(
        data,
        teams_by_id,
    )

    if not players:
        raise RuntimeError(
            "No current injury or "
            "availability players found."
        )

    for player in players:

        fixture = get_next_fixture(
            player["team_id"],
            fixtures,
            teams_by_id,
        )

        player["fixture"] = fixture
        player["ownership_delta"] = None

    grouped = {}

    for player in players:

        category = classify_category(
            None,
            player,
        )

        grouped.setdefault(
            category,
            [],
        ).append(
            player
        )

    # Prefer a category with multiple players
    # for the preview.
    order = [
        "INJURY",
        "DOUBT",
        "SUSPENSION",
        "AVAILABLE",
    ]

    chosen_category = None

    for category in order:

        if len(
            grouped.get(
                category,
                [],
            )
        ) >= 2:

            chosen_category = category
            break

    if chosen_category is None:

        for category in order:

            if grouped.get(
                category
            ):

                chosen_category = category
                break

    preview_players = grouped[
        chosen_category
    ][:6]

    preview_groups = {
        category: grouped[category][:6]
        for category in order
        if grouped.get(category)
    }

    card = create_news_page(
        preview_groups,
        gameweek,
    )

    send_discord_card(
        card,
        None,
    )

    save_x_draft(
        chosen_category,
        preview_players,
        gameweek,
    )

    print(
        "Graphic preview sent successfully."
    )

    print(
        "Categories: " + ", ".join(preview_groups)
    )

    print(
        "Players: "
        + ", ".join(
            player["name"]
            for player in preview_players
        )
    )


def run_test():
    data = fetch_json(
        FPL_API_URL
    )

    teams_by_id = {
        team["id"]: team
        for team in data.get(
            "teams",
            []
        )
    }

    player = None

    for item in data.get(
        "elements",
        []
    ):

        record = build_player_record(
            item,
            teams_by_id,
        )

        if is_relevant(
            record
        ):
            player = record
            break

    if player is None:
        raise RuntimeError(
            "No player available for test."
        )

    category = classify_category(
        None,
        player,
    )

    card = create_news_page(
        {category: [player]},
        current_gameweek(
            data
        ),
    )

    send_discord_card(
        card,
        None,
    )

    print(
        "Single-player graphic test sent."
    )


def run_monitor():
    data = fetch_json(
        FPL_API_URL
    )

    fixtures = fetch_json(
        FPL_FIXTURES_URL
    )

    teams_by_id = {
        team["id"]: team
        for team in data.get(
            "teams",
            []
        )
    }

    gameweek = current_gameweek(
        data
    )

    # Route the requested 12:00, 14:00 and 17:00 ET Discord editions through
    # this EXISTING 15-minute monitor. Keep its cron and original injury logic.
    # Unverified media/fixtures/deadline must never be published; a held
    # editorial edition must not interrupt existing verified injury alerts.
    try:
        from .discord_daily_editorial import run_edition
        run_edition(data, fixtures)
    except Exception as exc:
        print(f"Discord editorial held ({type(exc).__name__}): {exc}")

    current = {}

    for player in data.get(
        "elements",
        []
    ):

        player_id = str(
            player["id"]
        )

        current[player_id] = (
            build_player_record(
                player,
                teams_by_id,
            )
        )

    previous = load_state()

    # First normal run creates the baseline.
    if not previous:

        save_state(
            current
        )

        print(
            "Initial FPL injury baseline created."
        )

        print(
            f"Players tracked: "
            f"{len(current)}"
        )

        return

    grouped_changes = {}

    for player_id, new_record in current.items():

        old_record = previous.get(
            player_id
        )

        if old_record == new_record:
            continue

        meaningful_old = {
            "status": (old_record or {}).get("status"),
            "chance_next": (old_record or {}).get("chance_next"),
            "chance_this": (old_record or {}).get("chance_this"),
            "news": clean_text((old_record or {}).get("news")),
        }

        meaningful_new = {
            "status": new_record.get("status"),
            "chance_next": new_record.get("chance_next"),
            "chance_this": new_record.get("chance_this"),
            "news": clean_text(new_record.get("news")),
        }

        if meaningful_old == meaningful_new:
            continue

        old_relevant = is_relevant(
            old_record
        )

        new_relevant = is_relevant(
            new_record
        )

        if (
            not old_relevant
            and not new_relevant
        ):
            continue

        category = classify_category(
            old_record,
            new_record,
        )

        try:
            old_ownership = float(
                old_record.get(
                    "ownership",
                    0,
                )
            )

            new_ownership = float(
                new_record.get(
                    "ownership",
                    0,
                )
            )

            ownership_delta = round(
                new_ownership -
                old_ownership,
                1,
            )

        except Exception:
            ownership_delta = None

        new_record["ownership_delta"] = (
            ownership_delta
        )

        fixture = get_next_fixture(
            new_record["team_id"],
            fixtures,
            teams_by_id,
        )

        new_record["fixture"] = fixture

        grouped_changes.setdefault(
            category,
            [],
        ).append(
            new_record
        )

    # Keep the existing per-category player order and X draft batches.
    for category, players in grouped_changes.items():
        players.sort(
            key=lambda player: float(
                player.get(
                    "ownership",
                    0,
                ) or 0
            ),
            reverse=True,
        )

    if grouped_changes:
        # Existing previews, draft generation and snapshot logic stay intact.
        # The new original-blue branded path is opt-in: no surprise change to
        # existing Discord production while template/handles remain unverified.
        if os.getenv("FPL_BRANDED_POSTS_ENABLED", "false").lower() == "true":
            import hashlib
            from .branded_renderer import render_batches, receipt_send
            all_changed = []
            for section, affected in grouped_changes.items():
                for item in affected:
                    all_changed.append(dict(item, action="MONITOR", category=section))
            identity_fields = [(p.get("name"), p.get("team_code"),
                                p.get("status"), p.get("chance_next"),
                                p.get("news")) for p in all_changed]
            canonical = json.dumps(sorted(identity_fields, key=str), sort_keys=True)
            version = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
            receipt_key = f"injury:{gameweek}:{version}"
            artwork = render_batches(
                "PLAYER STATUS • MANAGER WATCH", all_changed, data, fixtures)
            description = (
                f"GW{gameweek}: {len(all_changed)} confirmed FPL status changes.\n"
                "MONITOR availability and minutes before acting.\n"
                "Review fixtures and the next deadline before transfers.\n"
                "HOLD transfers until the latest squad news is checked.\n"
                "#FPL #FPLVortex #TeamNews #Availability")
            message_id, published = receipt_send(
                artwork, description, receipt_key, DISCORD_WEBHOOK_URL,
                Path("data/branded_discord_deliveries.json"))
            print(f"Verified branded status delivery: {published}; receipt ID={message_id}")
        else:
            card = create_news_page(
                grouped_changes,
                gameweek,
            )

            send_discord_card(
                card,
                None,
            )

        for category, players in grouped_changes.items():
            for start in range(
                0,
                len(players),
                8,
            ):
                batch = players[start:start + 8]

                save_x_draft(
                    category,
                    batch,
                    gameweek,
                )

        print(
            "Posted one combined injury-news card "
            f"with {sum(len(players) for players in grouped_changes.values())} player(s)."
        )

    save_state(
        current
    )

    print(
        "FPL Vortex injury monitoring complete."
    )

    print(
        f"Categories detected: "
        f"{len(grouped_changes)}"
    )

def save_state(state):
    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    STATE_FILE.write_text(
        json.dumps(
            state,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

def load_state():
    if not STATE_FILE.exists():
        return {}

    try:
        return json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return {}


def main():
    try:
        from .publishing_window import assert_allowed
    except ImportError:
        from publishing_window import assert_allowed
    assert_allowed()
    if RUN_MODE == "preview":
        run_preview()
        return

    if RUN_MODE == "test":
        run_test()
        return

    if RUN_MODE == "baseline":
        data = fetch_json(
            FPL_API_URL
        )

        teams_by_id = {
            team["id"]: team
            for team in data.get(
                "teams",
                []
            )
        }

        current = {}

        for player in data.get(
            "elements",
            []
        ):
            player_id = str(
                player["id"]
            )

            current[player_id] = (
                build_player_record(
                    player,
                    teams_by_id
                )
            )

        save_state(
            current
        )

        print(
            "FPL Vortex baseline created successfully."
        )

        print(
            f"Players tracked: "
            f"{len(current)}"
        )

        return

    run_monitor()


if __name__ == "__main__":
    main()
