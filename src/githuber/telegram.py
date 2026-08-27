import contextlib
import json
import time
import urllib.error
import urllib.request

RETRIES = 3


class Telegram:
    def __init__(self, cfg):
        self.base = f"https://api.telegram.org/bot{cfg.telegram_bot_token}"
        self.chat_id = cfg.telegram_chat_id

    def call(self, method, payload, timeout=35):
        for attempt in range(RETRIES):
            req = urllib.request.Request(
                f"{self.base}/{method}",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.load(resp).get("result")
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < RETRIES - 1:
                    time.sleep(self._retry_after(e))
                    continue
                raise

    def send(self, text):
        result = self.call(
            "sendMessage",
            {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )
        return result["message_id"]

    def delete(self, message_id):
        with contextlib.suppress(urllib.error.HTTPError):
            self.call("deleteMessage", {"chat_id": self.chat_id, "message_id": message_id})

    def updates(self, offset, timeout):
        return (
            self.call(
                "getUpdates",
                {"offset": offset, "timeout": timeout, "allowed_updates": ["message"]},
                timeout=timeout + 10,
            )
            or []
        )

    def register_commands(self, commands):
        self.call(
            "setMyCommands",
            {"commands": [{"command": name, "description": desc} for name, desc in commands]},
        )

    @staticmethod
    def _retry_after(error):
        try:
            return json.load(error).get("parameters", {}).get("retry_after", 3)
        except (json.JSONDecodeError, AttributeError):
            return 3
