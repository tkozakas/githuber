import hashlib
import hmac
import time

from githuber.commands import Line, dispatch, parse, to_html, to_mrkdwn
from githuber.webhook import slack_signature_valid
from tests.helpers import make_snapshot


class FakeStore:
    def __init__(self):
        self.mutes = []
        self.disabled = []
        self.saved = 0

    def save(self):
        self.saved += 1


def test_parse_variants():
    assert parse("/status") == ("status", "")
    assert parse("status") == ("status", "")
    assert parse("/mute org/repo#7") == ("mute", "org/repo#7")
    assert parse("/status@githuber_bot") == ("status", "")
    assert parse("  mute  org/repo ") == ("mute", "org/repo")


def test_dispatch_unknown_returns_none():
    assert dispatch(FakeStore(), {}, "bogus", "") is None


def test_status_lines():
    snaps = {"a": make_snapshot(ci="failed")}
    lines = dispatch(FakeStore(), snaps, "status", "")
    assert lines[0].url == "https://x/7"
    assert lines[0].detail == "Title"
    assert dispatch(FakeStore(), {}, "status", "") == [Line(text="No open PRs.")]


def test_mute_round_trip():
    store = FakeStore()
    assert dispatch(store, {}, "mute", "org/repo")[0].text == "Muted org/repo"
    assert store.mutes == ["org/repo"]
    assert dispatch(store, {}, "mutes", "")[0].text == "org/repo"
    dispatch(store, {}, "unmute", "org/repo")
    assert store.mutes == []
    assert store.saved == 2


def test_toggles_and_settings():
    store = FakeStore()
    lines = dispatch(store, {}, "disable", "comments")
    assert "comments: off" in [line.text for line in lines]
    lines = dispatch(store, {}, "enable", "comments")
    assert "comments: on" in [line.text for line in lines]
    assert dispatch(store, {}, "disable", "nope")[0].text.startswith("Unknown notification")


def test_renderers():
    lines = [Line(prefix="X", text="repo #7", url="https://x/7", detail="T <a>")]
    assert to_html(lines) == 'X <a href="https://x/7">repo #7</a> \u2014 T &lt;a&gt;'
    assert to_mrkdwn(lines) == "X <https://x/7|repo #7> - T &lt;a&gt;"


def test_slack_signature():
    secret = b"s3cr3t"
    ts = str(int(time.time()))
    body = b"text=status"
    sig = "v0=" + hmac.new(secret, f"v0:{ts}:{body.decode()}".encode(), hashlib.sha256).hexdigest()
    assert slack_signature_valid(secret, ts, sig, body)
    assert not slack_signature_valid(secret, ts, "v0=bad", body)
    assert not slack_signature_valid(secret, str(int(time.time()) - 999), sig, body)
