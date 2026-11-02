"""Production contract: doubles, branded landscape price pages, real captions."""
from PIL import Image
import pytest
from src import discord_daily_editorial as daily
from src import price_change_bot as price


def test_cross_repo_player_exclusion_joins_stable_photo_codes():
    from test_discord_daily_editorial import fixture_data
    data, fixtures = fixture_data()
    assert daily._ranked(data, fixtures, 10, 'fixture-targets', set())
    assert daily._ranked(data, fixtures, 10, 'fixture-targets', {12345}) == []


def test_completed_double_gw_sums_both_fixtures():
    class Session:
        def get(self, *args, **kwargs):
            class Response:
                def raise_for_status(self): pass
                def json(self):
                    return {'history': [
                        {'round': 8, 'total_points': 20, 'minutes': 90},
                        {'round': 9, 'total_points': 3, 'minutes': 70},
                        {'round': 9, 'total_points': 8, 'minutes': 90}]}
            return Response()
    assert daily._verified_last_gw(Session(), 42, 9) == {'points': 11, 'minutes': 160}


def test_price_production_uses_original_master_renderer_for_all_twenty(monkeypatch):
    from src import branded_renderer as branded
    rises = [{'id': str(i)} for i in range(10)]
    falls = [{'id': str(i)} for i in range(10, 20)]
    monkeypatch.setattr(price, 'fetch_json', lambda url: [{'id': 100}])
    calls = []
    def render(title, records, data, fixtures):
        calls.append(records)
        assert len(records) == 20
        assert all('MONITOR' in item['action'] for item in records)
        return [Image.new('RGB', (1920, 1080)) for _ in range(7)]
    monkeypatch.setattr(branded, 'render_batches', render)
    assert len(price.create_branded_price_pages({}, rises, falls)) == 7
    assert {r['id'] for r in calls[0]} == {str(i) for i in range(20)}


def test_price_rejects_non_landscape_production_art(monkeypatch):
    from src import branded_renderer as branded
    monkeypatch.setattr(price, 'fetch_json', lambda url: [])
    monkeypatch.setattr(branded, 'render_batches', lambda *args: [Image.new('RGB', (1440, 2160))])
    with pytest.raises(RuntimeError, match='1920x1080'):
        price.create_branded_price_pages({}, [{'id': '1'}], [])


def test_font_fallback_preserves_headline_size(monkeypatch):
    from src import branded_renderer as branded
    monkeypatch.setattr(branded, 'BOLD', '/missing/condensed.ttf')
    font = branded.font(48, True)
    assert font.getbbox('GAMEWEEK')[3] - font.getbbox('GAMEWEEK')[1] >= 30
