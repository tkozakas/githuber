import json

from githuber import blocks, prs
from githuber.slack import SlackError

CARD_KEYS = ("card", "slack_card")


class Channel:
    id_key = ""
    card_key = ""
    notes_key = ""

    def publish(self, record, snap, events):
        notes = self.render_notes(events)
        body = self.render(snap, notes)
        old = record.get(self.id_key)
        if old:
            self.remove(old)
        record[self.id_key] = self.create(body)
        record[self.notes_key] = notes
        record[self.card_key] = self.digest(body)

    def refresh(self, record, snap):
        body = self.render(snap, record.get(self.notes_key, ""))
        digest = self.digest(body)
        message_id = record.get(self.id_key)
        if not message_id:
            if any(record.get(key) for key in CARD_KEYS) or self.notes_key in record:
                record[self.id_key] = self.create(body)
                record[self.card_key] = digest
            return
        if digest == record.get(self.card_key):
            return
        if self.edit(message_id, body):
            record[self.card_key] = digest
        else:
            record[self.id_key] = self.create(body)
            record[self.card_key] = digest

    def retire(self, record):
        message_id = record.pop(self.id_key, None)
        if message_id:
            self.remove(message_id)
            record[self.card_key] = ""


class TelegramChannel(Channel):
    id_key = "message_id"
    card_key = "card"
    notes_key = "notes"

    def __init__(self, telegram):
        self.tg = telegram

    def render(self, snap, notes):
        return prs.render_card(snap, notes)

    def render_notes(self, events):
        return prs.render_notes(events)

    def digest(self, body):
        return body

    def create(self, body):
        return self.tg.send(body)

    def edit(self, message_id, body):
        return self.tg.edit(message_id, body)

    def remove(self, message_id):
        self.tg.delete(message_id)


class SlackChannel(Channel):
    id_key = "slack_ts"
    card_key = "slack_card"
    notes_key = "slack_notes"
    channel_key = "slack_channel"

    def __init__(self, slack):
        self.slack = slack

    def publish(self, record, snap, events):
        self._relocate(record, snap)
        super().publish(record, snap, events)
        record[self.channel_key] = self.slack.channel

    def refresh(self, record, snap):
        self._relocate(record, snap)
        super().refresh(record, snap)
        if record.get(self.id_key):
            record[self.channel_key] = self.slack.channel

    def retire(self, record):
        record.pop(self.channel_key, None)
        super().retire(record)

    def _relocate(self, record, snap):
        stored = record.get(self.channel_key)
        if record.get(self.id_key) and stored and stored != self.slack.channel:
            self.slack.delete(record[self.id_key], stored)
            body = self.render(snap, record.get(self.notes_key, ""))
            record[self.id_key] = self.create(body)
            record[self.card_key] = self.digest(body)
            record[self.channel_key] = self.slack.channel

    def render(self, snap, notes):
        return (blocks.card_fallback(snap), blocks.card_blocks(snap, notes))

    def render_notes(self, events):
        return blocks.render_notes_mrkdwn(events)

    def digest(self, body):
        return json.dumps(body[1], sort_keys=True)

    def create(self, body):
        return self.slack.post(body[0], body[1])

    def edit(self, message_id, body):
        try:
            self.slack.update(message_id, body[0], body[1])
            return True
        except SlackError as e:
            if "message_not_found" in str(e):
                return False
            raise

    def remove(self, message_id):
        self.slack.delete(message_id)
