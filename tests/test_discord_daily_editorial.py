"""Offline regression coverage for three Discord editorial slots (no live webhook)."""
from datetime import datetime, timezone
import json

from PIL import Image
import pytest

from src import discord_daily_editorial as daily


def now_at(hour):
    # November 2, 2026 is EST (UTC-05:00).
    return datetime(2026, 11, 2, hour + 5, 7, tzinfo=timezone.utc)


def fixture_data():
    events = [
        {"id": 9, "finished": True},
        {"id": 10, "finished": False, "is_next": True,
         "deadline_time": "2026-11-06T18:30:00Z"},
    ]
    teams = [
        {"id": 1, "name": "Arsenal", "short_name": "ARS", "code": 3},
        {"id": 2, "name": "Chelsea", "short_name": "CHE", "code": 8},
    ]
    person = {
        "id": 42, "code": 12345, "team": 1, "element_type": 3,
        "first_name": "Test", "second_name": "Example", "web_name": "Example",
        "now_cost": 74, "selected_by_percent": "20.1", "minutes": 700,
        "form": "5.4", "status": "a", "transfers_in_event": 120000,
        "transfers_out_event": 6000,
    }
    fixture = {
        "id": 100, "event": 10, "team_h": 1, "team_a": 2,
        "kickoff_time": "2026-11-07T15:00:00Z",
        "team_h_difficulty": 2, "team_a_difficulty": 4,
        "finished": False,
    }
    return {"events": events, "teams": teams, "elements": [person]}, [fixture]


class FakeSession:
    def get(self, url, **kwargs):
        class Response:
            def raise_for_status(self):
                return None
            def json(self):
                return {"history": [
                    {"round": 9, "total_points": 8, "minutes": 90}
                ]}
        assert "/api/element-summary/42/" in url
        return Response()


def test_slots_et_and_existing_schedule_unchanged():
    assert daily.slot_for(now_at(12))[0] == "fixture-targets"
    assert daily.slot_for(now_at(14))[0] == "transfer-advice"
    assert daily.slot_for(now_at(17))[0] == "decision-watch"
    assert daily.slot_for(now_at(11)) is None
    assert daily.slot_for(now_at(13)) is None
    assert daily.slot_for(now_at(19)) is None


def test_deadline_must_be_future():
    bootstrap, _ = fixture_data()
    assert daily.actionable_gw(bootstrap, now_at(12))[0] == 10
    with pytest.raises(RuntimeError, match="deadline passed"):
        daily.actionable_gw(
            bootstrap, datetime(2026, 11, 7, 0, 0, tzinfo=timezone.utc))


def test_discards_unverified_player_media(monkeypatch, tmp_path):
    bootstrap, fixtures = fixture_data()
    monkeypatch.setattr(daily, "RECEIPTS", tmp_path / "ledger.json")
    monkeypatch.setattr(daily, "_outside_already_published", lambda *args: set())
    def missing_media(*args, **kwargs):
        raise RuntimeError("Image host blocked")
    monkeypatch.setattr(daily.branded, "_current_verified_media", missing_media)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/42/TEST")
    assert daily.run_edition(
        bootstrap, fixtures, now_at(12), session=FakeSession()
    ) == "held-unverified"


def test_one_verified_graphic_exact_caption_and_receipt_dedup(monkeypatch, tmp_path):
    bootstrap, fixtures = fixture_data()
    journal = tmp_path / "ledger.json"
    monkeypatch.setattr(daily, "RECEIPTS", journal)
    monkeypatch.setattr(daily, "_outside_already_published", lambda *args: set())
    monkeypatch.setattr(daily.branded, "_current_verified_media",
                        lambda *args: Image.new("RGB", (100, 100)))
    monkeypatch.setattr(daily.branded, "render_batches",
                        lambda *args, **kwargs: [Image.new("RGB", (1920, 1080))])
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/42/TEST")
    sent = []
    def send(images, caption, identity, webhook, journal_path, *, session=None):
        assert len(images) == 1 and images[0].size == (1920, 1080)
        assert webhook == "https://discord.com/api/webhooks/42/TEST"
        lines = caption.splitlines()
        assert len(lines) == 5
        assert lines[-1].count("#") == 4
        assert "GW9" in caption and "90 mins" in caption
        assert "FDR 2" in caption
        sent.append(identity)
        journal.write_text(json.dumps({identity: {"message_id": "confirmed-123"}}))
        return ("confirmed-123", True)
    monkeypatch.setattr(daily.branded, "receipt_send", send)
    assert daily.run_edition(
        bootstrap, fixtures, now_at(12), session=FakeSession()
    ) == "posted"
    assert daily.run_edition(
        bootstrap, fixtures, now_at(12), session=FakeSession()
    ) == "already-delivered"
    assert len(sent) == 1


def test_duplicate_topic_candidates_are_not_reused(monkeypatch):
    data, fixtures = fixture_data()
    assert len(daily._ranked(data, fixtures, 10, "fixture-targets", {42})) == 0
    assert len(daily._ranked(data, fixtures, 10, "fixture-targets", set())) == 1
