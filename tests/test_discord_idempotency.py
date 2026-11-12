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


def test_discord_rate_limit_retries_safely_with_fresh_attachment_bytes(monkeypatch, tmp_path):
    delays = []
    monkeypatch.setattr("time.sleep", delays.append)

    class Response:
        def __init__(self, code):
            self.status_code = code
            self.headers = {"Retry-After": "0.5"}
        def raise_for_status(self):
            assert self.status_code == 200
        def json(self):
            return {"id": "confirmed-429-recovery"}

    class Session:
        def __init__(self):
            self.attempts = 0
            self.payload_sizes = []
        def post(self, *args, **kwargs):
            self.attempts += 1
            self.payload_sizes.append(sum(len(info[1].read())
                                          for _, info in kwargs["files"]))
            return Response(429 if self.attempts == 1 else 200)

    client = Session()
    image = Image.new("RGB", (1920, 1080), (4, 21, 54))
    webhook = "https://" + "discord.com" + "/api/" + "webhooks/0/example"
    ledger = tmp_path / "receipts.json"
    result = branded.receipt_send([image], "Verified news", "unique-story",
                                  webhook, ledger, session=client)
    assert result == ("confirmed-429-recovery", True)
    assert client.attempts == 2
    assert all(size > 0 for size in client.payload_sizes)
    assert delays == [0.5]
    assert branded.receipt_send([image], "Verified news", "unique-story",
                                webhook, ledger, session=client)[1] is False
    assert client.attempts == 2


def test_duplicate_caption_with_different_identity_is_not_reposted(tmp_path):
    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"id": "one-message"}
    class Session:
        def __init__(self): self.calls = 0
        def post(self, *args, **kwargs):
            self.calls += 1
            return Response()
    client = Session()
    image = Image.new("RGB", (1920, 1080), (12, 20, 58))
    webhook = "https://discord.com/api/webhooks/0/unit-test"
    journal = tmp_path / "receipts.json"
    assert branded.receipt_send([image], "One verified caption", "version-one",
                                webhook, journal, session=client) == ("one-message", True)
    assert branded.receipt_send([image], " One   verified  caption  ", "version-two",
                                webhook, journal, session=client) == ("one-message", False)
    assert client.calls == 1


def test_unknown_discord_acceptance_stays_fenced_across_retry(tmp_path):
    import requests
    class Session:
        def __init__(self): self.calls = 0
        def post(self, *args, **kwargs):
            self.calls += 1
            raise requests.ReadTimeout("possibly accepted")
    client = Session()
    image = Image.new("RGB", (1920, 1080), (12, 20, 58))
    webhook = "https://discord.com/api/webhooks/0/unit-test"
    journal = tmp_path / "receipts.json"
    with pytest.raises(requests.ReadTimeout):
        branded.receipt_send([image], "One attempt only", "uncertain",
                             webhook, journal, session=client)
    assert json.loads(journal.read_text())["uncertain"]["send_pending"] is True
    with pytest.raises(RuntimeError, match="uncertain"):
        branded.receipt_send([image], "One attempt only", "uncertain",
                             webhook, journal, session=client)
    with pytest.raises(RuntimeError, match="pending"):
        branded.receipt_send([image], "One attempt only", "new-id",
                             webhook, journal, session=client)
    assert client.calls == 1


def test_confirmed_discord_rejection_allows_safe_retry(tmp_path):
    class Response:
        def __init__(self, status): self.status_code = status
        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError("confirmed 403")
        def json(self): return {"id": "accepted"}
    class Session:
        def __init__(self): self.calls = 0
        def post(self, *args, **kwargs):
            self.calls += 1
            return Response(403 if self.calls == 1 else 200)
    client = Session()
    image = Image.new("RGB", (1920, 1080), (12, 20, 58))
    webhook = "https://discord.com/api/webhooks/0/unit-test"
    journal = tmp_path / "receipts.json"
    with pytest.raises(RuntimeError, match="403"):
        branded.receipt_send([image], "Test confirmed rejection", "403-topic",
                             webhook, journal, session=client)
    assert "403-topic" not in json.loads(journal.read_text())
    assert branded.receipt_send([image], "Test confirmed rejection", "403-topic",
                                webhook, journal, session=client) == ("accepted", True)
    assert client.calls == 2
