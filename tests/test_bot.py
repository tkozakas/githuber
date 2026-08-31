import hashlib
import hmac

from githuber.commands import parse as parse_command
from githuber.store import Store
from githuber.webhook import github_signature_valid


def test_parse_command_forms():
    assert parse_command("/status") == ("status", "")
    assert parse_command("/mute org/repo#7") == ("mute", "org/repo#7")
    assert parse_command("/status@githuber_bot") == ("status", "")
    assert parse_command("plain text") == ("plain", "text")


def test_store_round_trip(tmp_path):
    path = str(tmp_path / "state.json")
    store = Store(path)
    store.record("org/repo#1")["green_sha"] = "abc"
    store.mutes.append("org/repo")
    store.offset = 42
    store.save()
    reloaded = Store(path)
    assert reloaded.prs["org/repo#1"] == {"green_sha": "abc"}
    assert reloaded.mutes == ["org/repo"]
    assert reloaded.offset == 42


def test_store_discards_legacy_format(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"org/repo#1@abc": true}')
    assert Store(str(path)).prs == {}


def test_store_prune(tmp_path):
    store = Store(str(tmp_path / "state.json"))
    store.record("a#1")
    store.record("b#2")
    store.prune({"a#1"})
    assert list(store.prs) == ["a#1"]


def test_webhook_signature():
    body = b'{"action": "completed"}'
    good = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert github_signature_valid(b"secret", good, body)
    assert not github_signature_valid(b"secret", "sha256=bad", body)


def test_toggles_cover_all_note_kinds():
    from githuber.commands import TOGGLES

    assert set(TOGGLES.values()) == {"green", "conflict", "comment", "verdict"}


def test_store_disabled_round_trip(tmp_path):
    path = str(tmp_path / "state.json")
    store = Store(path)
    store.disabled.append("comments")
    store.save()
    assert Store(path).disabled == ["comments"]
