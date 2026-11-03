"""No-network brand and five-gameweek regression tests."""
from pathlib import Path

from PIL import Image
import pytest
from src import branded_renderer as branded


def sample():
    data = {"events": [{"id": 10, "is_next": True, "finished": False}],
            "teams": [{"id": 1, "name": "Arsenal", "short_name": "ARS", "code": 3},
                      {"id": 2, "name": "Chelsea", "short_name": "CHE", "code": 8}],
            "elements": [{"id": 99, "code": 1234, "team": 1,
                          "first_name": "Alex", "second_name": "Example",
                          "web_name": "Example", "element_type": 2,
                          "now_cost": 74, "selected_by_percent": "20.1",
                          "minutes": 700, "form": "4.7"}]}
    fixtures = [{"id": 10, "event": 10, "team_h": 1, "team_a": 2,
                 "finished": False, "team_h_difficulty": 2,
                 "team_a_difficulty": 4, "kickoff_time": "2026-11-07T15:00:00Z"},
                {"id": 11, "event": 10, "team_h": 2, "team_a": 1,
                 "finished": False, "team_h_difficulty": 3,
                 "team_a_difficulty": 3, "kickoff_time": "2026-11-08T15:00:00Z"}]
    return data, fixtures


def test_verified_handles_required(monkeypatch):
    monkeypatch.delenv("FPL_TELEGRAM_HANDLE", raising=False)
    monkeypatch.delenv("FPL_DISCORD_HANDLE", raising=False)
    with pytest.raises(RuntimeError, match="FPL_TELEGRAM_HANDLE"):
        branded.verified_handles()


def test_existing_blue_master_is_not_replaced_by_fake_image(monkeypatch, tmp_path):
    monkeypatch.setenv("FPL_BRAND_MASTER_PATH", str(tmp_path / "missing.png"))
    with pytest.raises(FileNotFoundError):
        branded.master_slide()


def test_five_fdr_gameweeks_preserve_double_and_blank():
    data, fixtures = sample()
    schedule = branded.next_five(fixtures, 1, {t["id"]: t for t in data["teams"]}, 10)
    assert len(schedule) == 5
    assert len(schedule[0][1]) == 2
    assert schedule[0][1][0][2] == 2
    assert schedule[1][1] == []


def test_verified_player_photo_and_club_badge_in_card(monkeypatch):
    data, fixtures = sample()
    monkeypatch.setenv("FPL_TELEGRAM_HANDLE", "@verifiedTelegram")
    monkeypatch.setenv("FPL_DISCORD_HANDLE", "@verifiedDiscord")
    monkeypatch.setattr(branded, "master_slide", lambda session: Image.new("RGB", (1536,864)))
    recorded = []
    def fake_image(session, url):
        recorded.append(url)
        return Image.new("RGBA", (100,200))
    monkeypatch.setattr(branded, "actual_image", fake_image)
    images = branded.render_batches("Player Watch", [{"id": 99}], data, fixtures,
                                   session=object())
    assert len(images) == 1 and images[0].size == (1920,1080)
    assert len(recorded) == 2
    assert any("photos/players" in value for value in recorded)
    assert any("badges" in value for value in recorded)


def test_price_watch_missing_portrait_does_not_block_other_verified_players(monkeypatch):
    data, fixtures = sample()
    data["elements"].append(dict(data["elements"][0], id=100, code=5678))
    monkeypatch.setenv("FPL_TELEGRAM_HANDLE", "@verifiedTelegram")
    monkeypatch.setenv("FPL_DISCORD_HANDLE", "@verifiedDiscord")
    monkeypatch.setattr(branded, "master_slide", lambda session: Image.new("RGB", (1536, 864)))
    def media(session, code, category):
        if code == 1234:
            raise branded.MissingVerifiedMedia("missing official photo")
        return Image.new("RGBA", (100, 200))
    monkeypatch.setattr(branded, "_current_verified_media", media)
    omitted = []
    pages = branded.render_batches("Price watch", [{"id": 99}, {"id": 100}],
                                   data, fixtures, session=object(), unavailable=omitted)
    assert omitted == [99]
    assert len(pages) == 1 and pages[0].size == (1920, 1080)
    with pytest.raises(branded.MissingVerifiedMedia):
        branded.render_batches("Injury news", [{"id": 99}], data, fixtures, session=object())
