import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

OK_CONCLUSIONS = {"success", "neutral", "skipped"}


@dataclass(frozen=True)
class Config:
    github_token: str
    telegram_bot_token: str
    telegram_chat_id: str
    github_api: str = "https://api.github.com"
    poll_interval: int = 60
    state_file: str = "/state/state.json"

    @classmethod
    def from_env(cls):
        return cls(
            github_token=os.environ["GITHUB_TOKEN"],
            telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
            telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
            github_api=os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/"),
            poll_interval=int(os.environ.get("POLL_INTERVAL", "60")),
            state_file=os.environ.get("STATE_FILE", "/state/state.json"),
        )


def github(cfg, path, params=None):
    url = f"{cfg.github_api}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {cfg.github_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "githuber",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def telegram_send(cfg, text):
    body = json.dumps(
        {
            "chat_id": cfg.telegram_chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
    ).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{cfg.telegram_bot_token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def is_green(check_runs, combined_status):
    runs = check_runs.get("check_runs", [])
    statuses_total = combined_status.get("total_count", 0)
    if not runs and statuses_total == 0:
        return False
    for run in runs:
        if run.get("status") != "completed":
            return False
        if run.get("conclusion") not in OK_CONCLUSIONS:
            return False
    return not (statuses_total > 0 and combined_status.get("state") != "success")


def load_state(cfg):
    try:
        with open(cfg.state_file) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(cfg, state):
    tmp = cfg.state_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, cfg.state_file)


def poll(cfg, login, state):
    result = github(cfg, "/search/issues", {"q": f"is:pr is:open author:{login}", "per_page": "50"})
    seen = set()
    for item in result.get("items", []):
        repo = item["repository_url"].split("/repos/")[1]
        number = item["number"]
        pr = github(cfg, f"/repos/{repo}/pulls/{number}")
        sha = pr["head"]["sha"]
        key = f"{repo}#{number}@{sha}"
        seen.add(key)
        if state.get(key):
            continue
        check_runs = github(cfg, f"/repos/{repo}/commits/{sha}/check-runs", {"per_page": "100"})
        combined = github(cfg, f"/repos/{repo}/commits/{sha}/status")
        if is_green(check_runs, combined):
            telegram_send(cfg, f"\u2705 CI green: {repo}#{number} \u2014 {item['title']}\n{item['html_url']}")
            state[key] = True
            print(f"notified {key}", flush=True)
    for key in list(state):
        if key not in seen:
            del state[key]
    return state


def main():
    cfg = Config.from_env()
    login = github(cfg, "/user")["login"]
    print(f"watching PRs by {login} on {cfg.github_api}", flush=True)
    state = load_state(cfg)
    while True:
        try:
            state = poll(cfg, login, state)
            save_state(cfg, state)
        except (urllib.error.URLError, OSError, KeyError, json.JSONDecodeError) as e:
            print(f"poll failed: {e}", flush=True)
        time.sleep(cfg.poll_interval)
