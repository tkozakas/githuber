import json
import threading
import time
import urllib.error
from datetime import UTC, datetime, timedelta

from githuber import commands, prs
from githuber.channels import SlackChannel, TelegramChannel
from githuber.config import Config
from githuber.github import GitHub
from githuber.slack import Slack
from githuber.store import Store
from githuber.telegram import Telegram
from githuber.webhook import HttpServer

FRESH_WINDOW = timedelta(minutes=15)
UPDATES_TIMEOUT = 10


class Bot:
    def __init__(self, cfg, gh, store, tg=None, slack=None):
        self.cfg = cfg
        self.gh = gh
        self.store = store
        self.tg = tg
        self.channels = []
        if tg:
            self.channels.append(TelegramChannel(tg))
        if slack:
            self.channels.append(SlackChannel(slack))
        self.login = ""
        self.snapshots = {}
        self.wake = threading.Event()
        self.lock = threading.Lock()

    def run(self):
        self.login = self.gh.login()
        if self.tg:
            self.tg.register_commands(commands.COMMANDS)
        if self.cfg.webhook_port and (self.cfg.webhook_secret or self.cfg.slack_signing_secret):
            HttpServer(
                self.cfg.webhook_port,
                self.cfg.webhook_secret,
                self.cfg.slack_signing_secret,
                self.wake.set,
                self.handle_slack_command,
            ).start()
        print(f"watching PRs by {self.login} on {self.cfg.github_api}", flush=True)
        next_poll = 0.0
        while True:
            if time.monotonic() >= next_poll or self.wake.is_set():
                self.wake.clear()
                with self.lock:
                    self._guarded(self.refresh)
                next_poll = time.monotonic() + self.cfg.poll_interval
            if self.tg:
                self._guarded(self.process_updates)
            else:
                self.wake.wait(UPDATES_TIMEOUT)

    def handle_slack_command(self, text):
        name, arg = commands.parse(text or "help")
        with self.lock:
            reply = commands.dispatch(self.store, self.snapshots, name or "help", arg)
        if reply is None:
            reply = commands.dispatch(self.store, self.snapshots, "help", "")
        return commands.to_mrkdwn(reply)

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
            disabled = {commands.TOGGLES[t] for t in self.store.disabled}
            events = prs.diff_events(self.store.record(key), snap, fresh_comments, fresh_reviews, disabled)
            if events:
                self._publish(key, snap, events)
            elif snap.closed:
                self._retire(key)
            else:
                self._refresh_card(key, snap)
        self.snapshots = {k: s for k, s in snapshots.items() if not s.closed}
        for key, record in self.store.prs.items():
            if key not in live and any(record.get(c.id_key) for c in self.channels):
                for channel in self.channels:
                    channel.retire(record)
                print(f"retired {key}", flush=True)
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
            f"is:pr is:open author:{self.login} draft:false archived:false",
            f"is:pr author:{self.login} is:merged archived:false merged:>={cutoff}",
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
            closed=pull.get("state") != "open",
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
        for channel in self.channels:
            channel.publish(record, snap, events)
        print(f"notified {key}: {[e.kind for e in events]}", flush=True)

    def _refresh_card(self, key, snap):
        record = self.store.record(key)
        before = dict(record)
        for channel in self.channels:
            channel.refresh(record, snap)
        if record != before:
            print(f"updated {key}", flush=True)

    def _retire(self, key):
        record = self.store.record(key)
        had_message = any(record.get(c.id_key) for c in self.channels)
        for channel in self.channels:
            channel.retire(record)
        if had_message:
            print(f"retired {key}", flush=True)

    def _handle(self, text):
        name, arg = commands.parse(text)
        with self.lock:
            reply = commands.dispatch(self.store, self.snapshots, name, arg)
        if reply is not None:
            self.tg.send(commands.to_html(reply))

    def _guarded(self, step):
        try:
            step()
        except (urllib.error.URLError, OSError, KeyError, json.JSONDecodeError) as e:
            print(f"{step.__name__} failed: {e}", flush=True)
            time.sleep(3)


def main():
    cfg = Config.from_env()
    tg = Telegram(cfg) if cfg.telegram_bot_token and cfg.telegram_chat_id else None
    slack = Slack(cfg) if cfg.slack_bot_token and cfg.slack_channel else None
    if not tg and not slack:
        raise SystemExit("configure TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID or SLACK_BOT_TOKEN/SLACK_CHANNEL")
    Bot(cfg, GitHub(cfg), Store(cfg.state_file), tg=tg, slack=slack).run()
