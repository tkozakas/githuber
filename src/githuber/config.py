import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    github_token: str
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    github_api: str = "https://api.github.com"
    poll_interval: int = 60
    state_file: str = "/state/state.json"
    webhook_secret: str = ""
    webhook_port: int = 0
    slack_bot_token: str = ""
    slack_channel: str = ""
    slack_signing_secret: str = ""

    @classmethod
    def from_env(cls):
        return cls(
            github_token=os.environ["GITHUB_TOKEN"],
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
            github_api=os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/"),
            poll_interval=int(os.environ.get("POLL_INTERVAL", "60")),
            state_file=os.environ.get("STATE_FILE", "/state/state.json"),
            webhook_secret=os.environ.get("WEBHOOK_SECRET", ""),
            webhook_port=int(os.environ.get("WEBHOOK_PORT", "0")),
            slack_bot_token=os.environ.get("SLACK_BOT_TOKEN", ""),
            slack_channel=os.environ.get("SLACK_CHANNEL", ""),
            slack_signing_secret=os.environ.get("SLACK_SIGNING_SECRET", ""),
        )
