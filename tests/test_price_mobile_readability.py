"""Only the Discord price-prediction artwork changes; no public sends.

This suite confirms all twenty original candidates are spread across two
contrast-safe, portrait Discord attachments, instead of one unreadable
3200x2400 2-column table with tiny text.
"""
from io import BytesIO
from pathlib import Path
import json

import pytest
from PIL import Image, ImageDraw

from src import price_graphics as pg
from src import price_change_bot as price


def item(idx, direction):
    return {
        "id": str(idx),
        "name": f"Example Player Number {idx}",
        "team": "Manchester City" if idx % 2 else "Nottingham Forest",
        "team_code": 3 + idx,
        "now_cost": 54 + idx,
        "price_label": f"£{(54+idx)/10:.1f}m",
        "photo": f"{10000+idx}.jpg",
        "prediction": (0.76 + idx/100) * direction,
        "source": "LiveFPL predictor",
    }


def test_root_cause_remedied_two_portrait_images_keep_all_top_20():
    rises = [item(i, 1) for i in range(10)]
    drops = [item(i+10, -1) for i in range(10)]
    pages = pg.render_price_pages(rises, drops, "Monday, 2 November 2026",
                                  "LiveFPL predictor + FPL player data",
                                  assets={}, logo=None)
    assert len(pages) == 2
    assert all(p.size == (1440, 2160) and p.mode == "RGB" for p in pages)
    assert pg.WIDTH < pg.HEIGHT  # phone-first, not shrink a 3200px-wide table
    assert pg.ROW_LIMIT == 10
    assert pg.row_rect(0)[1] == pg.ROW_START
    assert pg.row_rect(9)[3] < 2002  # space for an uncut source footer
    assert pg.ROW_HEIGHT > 140
    assert min(pages[0].getpixel((0, 0))) > 235
    assert pages[0].getpixel((0, 0)) != pages[1].getpixel((0, 0))
    assert pages[0].getpixel((100, pg.ROW_START+30)) == pg.PANEL
    # Minimal white panels use high-contrast black text and numbers.
    assert max(pg.WHITE) < 30
    assert min(pg.PANEL) > 235 and min(pg.NAVY) > 235


def test_displays_one_photo_and_one_crest_without_distorting_aspect_ratio(monkeypatch):
    rises = [item(5, 1)]
    assets = {
        ("photo", "5"): Image.new("RGBA", (70, 140), (240, 90, 90, 255)),
        ("crest", 8): Image.new("RGBA", (40, 100), (40, 240, 90, 255)),
    }
    pages = pg.render_price_pages(rises, [], "2 November 2026",
                                  "Official FPL", assets=assets)
    assert len(pages) == 1
    original = assets[("photo", "5")]
    assert original.size == (70, 140)
    # The photo is actually composited in its own bounded slot, not an icon.
    assert any(pages[0].getpixel((x, pg.ROW_START+70)) == (240, 90, 90)
               for x in range(95, 185))


def test_long_player_names_are_truncated_inside_names_column():
    canvas = Image.new("RGB", (1440, 2160))
    draw = ImageDraw.Draw(canvas)
    string, font = pg.fitted(draw, "A" * 150, 735, 69, 45)
    assert string.endswith("…")
    bbox = draw.textbbox((0, 0), string, font=font)
    assert bbox[2]-bbox[0] <= 735


def test_cannot_overfill_a_price_page_or_make_empty_images():
    with pytest.raises(ValueError, match="maximum 10"):
        pg.render_price_pages([item(i, 1) for i in range(11)], [],
                              "today", "LiveFPL")
    with pytest.raises(ValueError, match="No verified"):
        pg.render_price_pages([], [], "today", "LiveFPL")


def test_single_discord_post_carries_both_images(monkeypatch):
    first = Image.new("RGB", pg.PAGE_SIZE, pg.NAVY)
    second = Image.new("RGB", pg.PAGE_SIZE, pg.PANEL)
    calls = []
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"id": "confirmed-price-post-24"}
    def fake_post(url, **kwargs):
        assert url == "https://discord.com/api/webhooks/0/unit-test"
        assert kwargs["params"] == {"wait": "true"}
        assert len(kwargs["files"]) == 2
        assert all(record[1][2] == "image/png" for record in kwargs["files"])
        payload = json.loads(kwargs["data"]["payload_json"])
        assert payload["allowed_mentions"] == {"parse": []}
        calls.append(payload)
        return FakeResponse()
    monkeypatch.setattr(price, "DISCORD_WEBHOOK_URL",
                        "https://discord.com/api/webhooks/0/unit-test")
    monkeypatch.setattr(price.requests, "post", fake_post)
    message = price.send_discord([first, second], "2 November 2026")
    assert message == "confirmed-price-post-24"
    assert len(calls) == 1  # same post: never separate unsolicited messages


def test_verified_price_renderer_does_not_call_unrelated_shared_news_renderer(monkeypatch):
    rises = [item(i, 1) for i in range(10)]
    drops = [item(i+10, -1) for i in range(10)]
    def fails(*args, **kwargs):
        pytest.fail("Other Discord news and injury graphics must remain unchanged")
    import src.branded_renderer as shared
    monkeypatch.setattr(shared, "render_batches", fails)
    pages = price.create_price_pages(rises, drops, "2 November 2026", "LiveFPL",
                                     assets={})
    assert len(pages) == 2


def test_unavailable_official_photos_not_replaced_with_fake_illustrations(monkeypatch):
    class Response:
        status_code = 403
        headers = {"Content-Type": "text/html"}
        content = b""
    class Session:
        def get(self, url, **kwargs):
            return Response()
    media = price.load_price_assets([item(5, 1)], [], client=Session())
    assert media[("photo", "5")] is None
    assert media[("crest", 8)] is None
