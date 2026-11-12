"""Reference-2 appearance, honest missing stats and undistorted media."""
from PIL import Image, ImageChops, ImageDraw
import pytest
from src import comparison_board as board


def profile(name="Example"):
    return {"name": name, "club": "Verified club", "position": "DEF",
            "metrics": {"PRICE": "£5.0m", "OWNERSHIP": "12.3%", "FORM": "6.1",
                        "MINUTES": "810", "TOTAL PTS": "55", "CS": "4",
                        "GOALS": "1", "ASSISTS": "2", "xG": "1.20", "xA": ".70"},
            "fixtures": [{"gw": 10, "opponent": "CHE", "venue": "H", "fdr": 3}],
            "portrait": Image.new("RGBA", (90, 160), (40, 120, 210)),
            "badge": Image.new("RGBA", (60, 60), (210, 80, 40)),
            "action": "HOLD", "reason": "Check the confirmed next fixture", "label": "HOLD"}


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_neon_navy_panels_white_ink_and_action_ribbons(count):
    original = Image.new("RGB", board.SIZE, (11, 30, 51))
    players = [profile(f"Verified Player {i}") for i in range(count)]
    for p, action in zip(players, ('START', 'HOLD', 'MONITOR', 'HOLD')):
        p['action'] = p['label'] = action
    image = board.comparison_board(original, "CURRENT PLAYER PICKS", 10, players)
    assert image.size == board.SIZE
    assert max(image.getpixel((0, 400))) < 100
    if count == 4:
        width = (1460-14*(count-1))/count
        for n, p in enumerate(players):
            x = round(38+n*(width+14))
            assert image.getpixel((x+20, 150)) == board.action_fill(p['action'])
    assert image.getpixel((48, 520)) == board.TABLE_YELLOW
    assert min(board.TABLE_INK) >= 230


def test_background_varies_by_edition_but_retry_is_stable():
    from importlib import import_module
    theme = import_module(board.__package__ + '.minimal_theme')
    assert theme.background_color('morning') != theme.background_color('evening')
    assert theme.background_color('morning') == theme.background_color('morning')


def test_portraits_keep_original_proportions_and_align_to_bottom():
    image = Image.new("RGB", (200, 300))
    board.contain(image, profile()["portrait"], (0, 0, 120, 280), bottom=True)
    box = ImageChops.difference(image, Image.new("RGB", image.size)).getbbox()
    assert box[3] == 280
    assert abs((box[2]-box[0])/(box[3]-box[1]) - 90/160) < .01


def test_missing_xgi_is_not_calculated_or_invented(monkeypatch):
    labels = []
    original = board.text
    def capture(draw, value, *args, **kwargs):
        labels.append(str(value))
        return original(draw, value, *args, **kwargs)
    monkeypatch.setattr(board, "text", capture)
    image = Image.new("RGB", board.SIZE)
    board.advanced_table(ImageDraw.Draw(image), [profile()])
    assert "xGI" not in labels
    assert profile()["metrics"].get("xGI") is None
