import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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


def telegram_send(cfg, text, html=False):
    payload = {
        "chat_id": cfg.telegram_chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if html:
        payload["parse_mode"] = "HTML"
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{cfg.telegram_bot_token}/sendMessage",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def html_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_comment(repo, number, title, comment):
    author = comment["user"]["login"]
    body = comment.get("body") or ""
    if len(body) > 700:
        body = body[:700] + "\u2026"
    return (
        f"\U0001f4ac <b>{html_escape(author)}</b> commented on "
        f'<a href="{comment["html_url"]}">{html_escape(f"{repo}#{number}")}</a>'
        f" \u2014 {html_escape(title)}\n"
        f"<blockquote>{html_escape(body)}</blockquote>"
    )


def should_notify_comment(login, comment, cutoff):
    user = comment.get("user") or {}
    if user.get("login") == login or user.get("type") == "Bot":
        return False
    if not (comment.get("body") or "").strip():
        return False
    return (comment.get("created_at") or comment.get("submitted_at") or "") >= cutoff


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


def search_queries(login, now):
    cutoff = (now - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [f"is:pr is:open author:{login}", f"is:pr author:{login} is:merged merged:>={cutoff}"]


def fetch_comments(cfg, repo, number, cutoff):
    comments = []
    for path in (f"/repos/{repo}/issues/{number}/comments", f"/repos/{repo}/pulls/{number}/comments"):
        comments.extend(github(cfg, path, {"since": cutoff, "per_page": "100"}))
    for review in github(cfg, f"/repos/{repo}/pulls/{number}/reviews", {"per_page": "100"}):
        comments.append(review)
    return comments


def notify_comments(cfg, login, state, seen, item, repo, number, cutoff):
    for comment in fetch_comments(cfg, repo, number, cutoff):
        key = f"comment:{repo}#{number}:{comment['id']}"
        if not should_notify_comment(login, comment, cutoff):
            continue
        seen.add(key)
        if state.get(key):
            continue
        telegram_send(cfg, format_comment(repo, number, item["title"], comment), html=True)
        state[key] = True
        print(f"notified {key}", flush=True)


def notify_green(cfg, state, seen, item, repo, number, sha):
    key = f"{repo}#{number}@{sha}"
    seen.add(key)
    if state.get(key):
        return
    check_runs = github(cfg, f"/repos/{repo}/commits/{sha}/check-runs", {"per_page": "100"})
    combined = github(cfg, f"/repos/{repo}/commits/{sha}/status")
    if is_green(check_runs, combined):
        telegram_send(cfg, f"\u2705 CI green: {repo}#{number} \u2014 {item['title']}\n{item['html_url']}")
        state[key] = True
        print(f"notified {key}", flush=True)


def poll(cfg, login, state):
    now = datetime.now(UTC)
    cutoff = (now - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    items = {}
    for query in search_queries(login, now):
        result = github(cfg, "/search/issues", {"q": query, "per_page": "50"})
        for item in result.get("items", []):
            items[item["repository_url"] + str(item["number"])] = item
    seen = set()
    for item in items.values():
        repo = item["repository_url"].split("/repos/")[1]
        number = item["number"]
        pr = github(cfg, f"/repos/{repo}/pulls/{number}")
        notify_green(cfg, state, seen, item, repo, number, pr["head"]["sha"])
        notify_comments(cfg, login, state, seen, item, repo, number, cutoff)
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
