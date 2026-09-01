import json

from githuber.blocks import card_blocks, card_fallback, mrkdwn_escape, render_notes_mrkdwn
from githuber.prs import Note
from tests.helpers import make_snapshot as snap


def test_card_matches_telegram_layout():
    blocks = card_blocks(snap(), "note line")
    assert len(blocks) == 1
    text = blocks[0]["text"]["text"]
    assert text.startswith("\U0001f7e2 *<https://x/7|repo #7>*\n*Title*")
    assert "`CI     `\u2705 green" in text
    assert "`Review `\u2796 none yet" in text
    assert "`Merge  `\u2705 clean" in text
    assert text.endswith("note line")
    json.dumps(blocks)


def test_card_conflicts_and_failure():
    text = card_blocks(snap(ci="failed", conflicts=True))[0]["text"]["text"]
    assert text.startswith("\u26a0\ufe0f ")
    assert "`CI     `\u274c failed" in text
    assert "`Merge  `\u26a0\ufe0f conflicts" in text


def test_card_reviews():
    reviews = ({"user": {"login": "bob"}, "state": "APPROVED", "submitted_at": "2026-01-01T00:00:00Z"},)
    text = card_blocks(snap(reviews=reviews))[0]["text"]["text"]
    assert "`Review `\u2705 bob" in text


def test_render_notes_mrkdwn_quotes_and_escapes():
    text = render_notes_mrkdwn([Note("comment", "alice", "a <b> & c\nsecond")])
    assert "*alice*" in text
    assert ">a &lt;b&gt; &amp; c" in text
    assert ">second" in text


def test_verdict_note():
    text = render_notes_mrkdwn([Note("verdict", "bob", "", "CHANGES_REQUESTED")])
    assert text == "\U0001f6d1 *bob* requested changes"


def test_fallback_and_escape():
    assert card_fallback(snap()) == "repo #7: CI green"
    assert mrkdwn_escape("<&>") == "&lt;&amp;&gt;"
