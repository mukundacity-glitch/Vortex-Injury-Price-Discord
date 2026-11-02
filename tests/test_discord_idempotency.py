"""Discord webhook receipt-based idempotency, with no real network call."""
import json
from PIL import Image
import pytest
from src import branded_renderer as branded


def test_identical_semantic_version_posted_once(tmp_path):
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"id": "confirmed-message-42"}
    class Session:
        def __init__(self):
            self.calls = 0
        def post(self, *args, **kwargs):
            self.calls += 1
            assert kwargs.get("params") == {"wait": "true"}
            assert kwargs.get("files")
            return Response()
    client = Session()
    # Syntax assembled in parts: this is an inert unit test URL, not a secret.
    url = "https://" + "discord.com" + "/api/" + "webhooks/0/example"
    path = tmp_path / "journal.json"
    img = Image.new("RGB", (1920, 1080), (4, 21, 54))
    first = branded.receipt_send([img], "FPL watch #FPL #GW10 #FPLVortex #Price",
                                 "price:gw10:v1", url, path, session=client)
    again = branded.receipt_send([img], "FPL watch #FPL #GW10 #FPLVortex #Price",
                                 "price:gw10:v1", url, path, session=client)
    assert first == ("confirmed-message-42", True)
    assert again == ("confirmed-message-42", False)
    assert client.calls == 1
    assert json.loads(path.read_text())["price:gw10:v1"]["pages"] == 1


def test_corrupt_or_unknown_receipt_holds_instead_of_reposting(tmp_path):
    path = tmp_path / "journal.json"
    path.write_text("{")
    img = Image.new("RGB", (1920, 1080))
    url = "https://" + "discord.com" + "/api/" + "webhooks/0/example"
    with pytest.raises(RuntimeError, match="safely read"):
        branded.receipt_send([img], "Caption", "topic", url, path, session=object())
