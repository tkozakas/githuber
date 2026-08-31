import json

from githuber.blocks import card_blocks, card_fallback, mrkdwn_escape, render_notes_mrkdwn
from githuber.prs import Note, Snapshot


def snap(**overrides):
    fields = {
        "repo": "org/repo",
        "number": 7,
        "title": "Title",
        "url": "https://x/7",
        "sha": "abc",
        "ci": "green",
        "conflicts": False,
        "reviews": (),
    }
    fields.update(overrides)
    return Snapshot(**fields)


def test_card_blocks_structure():
    blocks = card_blocks(snap(), "note line")
    assert blocks[0]["text"]["text"].startswith(":large_green_circle: *<https://x/7|repo #7>*")
    fields = {f["text"].split("\n")[0] for f in blocks[1]["fields"]}
    assert fields == {"*CI*", "*Review*", "*Merge*"}
    assert blocks[-1]["text"]["text"] == "note line"
    json.dumps(blocks)


def test_card_blocks_conflicts_and_failure():
    blocks = card_blocks(snap(ci="failed", conflicts=True))
    assert blocks[0]["text"]["text"].startswith(":warning:")
    assert ":x: failed" in blocks[1]["fields"][0]["text"]
    assert ":warning: conflicts" in blocks[1]["fields"][2]["text"]


def test_render_notes_mrkdwn_quotes_and_escapes():
    text = render_notes_mrkdwn([Note("comment", "alice", "a <b> & c\nsecond")])
    assert "*alice*" in text
    assert ">a &lt;b&gt; &amp; c" in text
    assert ">second" in text


def test_verdict_note():
    text = render_notes_mrkdwn([Note("verdict", "bob", "", "CHANGES_REQUESTED")])
    assert text == ":octagonal_sign: *bob* requested changes"


def test_fallback_and_escape():
    assert card_fallback(snap()) == "repo #7: CI green"
    assert mrkdwn_escape("<&>") == "&lt;&amp;&gt;"
