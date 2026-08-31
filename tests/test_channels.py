from githuber.channels import Channel
from githuber.prs import Note
from tests.helpers import make_snapshot as snap


class FakeChannel(Channel):
    id_key = "fake_id"
    card_key = "fake_card"
    notes_key = "fake_notes"

    def __init__(self, edit_ok=True):
        self.sent = []
        self.edited = []
        self.removed = []
        self.edit_ok = edit_ok
        self.counter = 0

    def render(self, s, notes):
        return f"{s.ci}|{notes}"

    def render_notes(self, events):
        return ",".join(e.kind for e in events)

    def digest(self, body):
        return body

    def create(self, body):
        self.counter += 1
        self.sent.append(body)
        return self.counter

    def edit(self, message_id, body):
        if self.edit_ok:
            self.edited.append((message_id, body))
        return self.edit_ok

    def remove(self, message_id):
        self.removed.append(message_id)


def test_publish_replaces_message():
    channel = FakeChannel()
    record = {}
    channel.publish(record, snap(), [Note("green")])
    assert record["fake_id"] == 1
    channel.publish(record, snap(), [Note("conflict")])
    assert channel.removed == [1]
    assert record["fake_id"] == 2
    assert record["fake_notes"] == "conflict"


def test_refresh_edits_only_on_drift():
    channel = FakeChannel()
    record = {}
    channel.publish(record, snap(), [Note("green")])
    channel.refresh(record, snap())
    assert channel.edited == []
    channel.refresh(record, snap(ci="failed"))
    assert channel.edited == [(1, "failed|green")]


def test_refresh_resends_when_edit_fails():
    channel = FakeChannel(edit_ok=False)
    record = {}
    channel.publish(record, snap(), [Note("green")])
    channel.refresh(record, snap(ci="failed"))
    assert record["fake_id"] == 2


def test_refresh_bootstraps_when_other_channel_published():
    channel = FakeChannel()
    record = {"card": "existing telegram card"}
    channel.refresh(record, snap())
    assert record["fake_id"] == 1


def test_refresh_skips_untracked_record():
    channel = FakeChannel()
    record = {}
    channel.refresh(record, snap())
    assert "fake_id" not in record


def test_retire_deletes():
    channel = FakeChannel()
    record = {}
    channel.publish(record, snap(), [Note("green")])
    channel.retire(record)
    assert channel.removed == [1]
    assert "fake_id" not in record
