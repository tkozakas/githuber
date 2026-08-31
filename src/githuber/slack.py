import contextlib
import json
import time
import urllib.error
import urllib.request

API_BASE = "https://slack.com/api"
RETRIES = 3
DEFAULT_RETRY_AFTER = 3


class SlackError(Exception):
    pass


class Slack:
    def __init__(self, cfg):
        self.token = cfg.slack_bot_token
        self.channel = cfg.slack_channel

    def call(self, method, payload):
        for attempt in range(RETRIES):
            req = urllib.request.Request(
                f"{API_BASE}/{method}",
                data=json.dumps(payload).encode(),
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body = json.load(resp)
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < RETRIES - 1:
                    time.sleep(int(e.headers.get("Retry-After", DEFAULT_RETRY_AFTER)))
                    continue
                raise
            if not body.get("ok"):
                raise SlackError(body.get("error", "unknown"))
            return body
        raise SlackError("rate limited")

    def post(self, text, blocks):
        result = self.call("chat.postMessage", {"channel": self.channel, "text": text, "blocks": blocks})
        return result["ts"]

    def update(self, ts, text, blocks):
        self.call("chat.update", {"channel": self.channel, "ts": ts, "text": text, "blocks": blocks})

    def delete(self, ts):
        with contextlib.suppress(SlackError, urllib.error.HTTPError):
            self.call("chat.delete", {"channel": self.channel, "ts": ts})
