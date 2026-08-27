import json
import threading
import time
import urllib.error
from datetime import UTC, datetime, timedelta

from githuber import prs
from githuber.config import Config
from githuber.github import GitHub
from githuber.store import Store
from githuber.telegram import Telegram
from githuber.webhook import WebhookServer

FRESH_WINDOW = timedelta(minutes=15)
UPDATES_TIMEOUT = 10

COMMANDS = [
    ("status", "List open PRs with CI and review state"),
    ("mute", "Mute a repo or PR: /mute org/repo or org/repo#7"),
    ("unmute", "Unmute a repo or PR"),
    ("mutes", "List active mutes"),
    ("help", "Show available commands"),
]


def parse_command(text):
    if not text.startswith("/"):
        return "", ""
    name, _, arg = text[1:].partition(" ")
    return name.partition("@")[0].lower(), arg.strip()


class Bot:
    def __init__(self, cfg, gh, tg, store):
        self.cfg = cfg
        self.gh = gh
        self.tg = tg
        self.store = store
        self.login = ""
        self.snapshots = {}
        self.wake = threading.Event()

    def run(self):
        self.login = self.gh.login()
        self.tg.register_commands(COMMANDS)
        if self.cfg.webhook_secret and self.cfg.webhook_port:
            WebhookServer(self.cfg.webhook_secret, self.cfg.webhook_port, self.wake.set).start()
        print(f"watching PRs by {self.login} on {self.cfg.github_api}", flush=True)
        next_poll = 0.0
        while True:
            if time.monotonic() >= next_poll or self.wake.is_set():
                self.wake.clear()
                self._guarded(self.refresh)
                next_poll = time.monotonic() + self.cfg.poll_interval
            self._guarded(self.process_updates)

    def refresh(self):
        now = datetime.now(UTC)
        cutoff = (now - FRESH_WINDOW).strftime("%Y-%m-%dT%H:%M:%SZ")
        items = self._search(cutoff)
        live = set()
        snapshots = {}
        for item in items:
            repo = item["repository_url"].split("/repos/")[1]
            number = item["number"]
            key = prs.pr_key(repo, number)
            live.add(key)
            if prs.is_muted(self.store.mutes, repo, number):
                continue
            snap, fresh_comments, fresh_reviews = self._inspect(repo, number, item, cutoff)
            snapshots[key] = snap
            events = prs.diff_events(self.store.record(key), snap, fresh_comments, fresh_reviews)
            if events:
                self._publish(key, snap, events)
        self.snapshots = snapshots
        self.store.prune(live)
        self.store.save()

    def process_updates(self):
        updates = self.tg.updates(self.store.offset, UPDATES_TIMEOUT)
        for update in updates:
            self.store.offset = update["update_id"] + 1
            message = update.get("message") or {}
            if str(message.get("chat", {}).get("id")) == self.tg.chat_id:
                self._handle(message.get("text") or "")
        if updates:
            self.store.save()

    def _search(self, cutoff):
        items = {}
        for query in (
            f"is:pr is:open author:{self.login}",
            f"is:pr author:{self.login} is:merged merged:>={cutoff}",
        ):
            for item in self.gh.search_prs(query):
                items[item["repository_url"] + str(item["number"])] = item
        return items.values()

    def _inspect(self, repo, number, item, cutoff):
        pull = self.gh.pull(repo, number)
        sha = pull["head"]["sha"]
        snap = prs.Snapshot(
            repo=repo,
            number=number,
            title=item["title"],
            url=item["html_url"],
            sha=sha,
            ci=prs.ci_state(self.gh.check_runs(repo, sha), self.gh.combined_status(repo, sha)),
            conflicts=pull.get("mergeable_state") == "dirty",
            reviews=tuple(self.gh.reviews(repo, number)),
        )
        fresh_comments = [
            c
            for c in self.gh.issue_comments(repo, number, cutoff) + self.gh.review_comments(repo, number, cutoff)
            if prs.is_foreign(self.login, c.get("user") or {}) and (c.get("created_at") or "") >= cutoff
        ]
        fresh_reviews = [
            r
            for r in snap.reviews
            if prs.is_foreign(self.login, r.get("user") or {}) and (r.get("submitted_at") or "") >= cutoff
        ]
        return snap, fresh_comments, fresh_reviews

    def _publish(self, key, snap, events):
        record = self.store.record(key)
        if record.get("message_id"):
            self.tg.delete(record["message_id"])
        record["message_id"] = self.tg.send(prs.render_card(snap, events))
        print(f"notified {key}: {[e.kind for e in events]}", flush=True)

    def _handle(self, text):
        name, arg = parse_command(text)
        if name == "status":
            self.tg.send(prs.render_status(sorted(self.snapshots.values(), key=lambda s: (s.repo, s.number))))
        elif name == "mute" and arg:
            if arg not in self.store.mutes:
                self.store.mutes.append(arg)
                self.store.save()
            self.tg.send(f"Muted {prs.html_escape(arg)}")
        elif name == "unmute" and arg:
            if arg in self.store.mutes:
                self.store.mutes.remove(arg)
                self.store.save()
            self.tg.send(f"Unmuted {prs.html_escape(arg)}")
        elif name == "mutes":
            body = "\n".join(prs.html_escape(m) for m in self.store.mutes) or "No mutes."
            self.tg.send(body)
        elif name == "help":
            self.tg.send("\n".join(f"/{cmd} \u2014 {desc}" for cmd, desc in COMMANDS))

    def _guarded(self, step):
        try:
            step()
        except (urllib.error.URLError, OSError, KeyError, json.JSONDecodeError) as e:
            print(f"{step.__name__} failed: {e}", flush=True)
            time.sleep(3)


def main():
    cfg = Config.from_env()
    Bot(cfg, GitHub(cfg), Telegram(cfg), Store(cfg.state_file)).run()
