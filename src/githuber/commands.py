from dataclasses import dataclass

from githuber import prs
from githuber.blocks import mrkdwn_escape

TOGGLES = {"green": "green", "conflicts": "conflict", "comments": "comment", "verdicts": "verdict"}

COMMANDS = [
    ("status", "List open PRs with CI and review state"),
    ("mute", "Mute a repo or PR: mute org/repo or org/repo#7"),
    ("unmute", "Unmute a repo or PR"),
    ("mutes", "List active mutes"),
    ("disable", "Turn a notification off: disable comments"),
    ("enable", "Turn a notification back on"),
    ("settings", "Show notification toggles"),
    ("help", "Show available commands"),
]


@dataclass(frozen=True)
class Line:
    text: str
    url: str = ""
    prefix: str = ""
    detail: str = ""


def parse(text):
    cleaned = text.strip()
    if cleaned.startswith("/"):
        cleaned = cleaned[1:]
    name, _, arg = cleaned.partition(" ")
    return name.partition("@")[0].lower(), arg.strip()


def dispatch(store, snapshots, name, arg):
    handler = _HANDLERS.get(name)
    if not handler:
        return None
    return handler(store, snapshots, arg)


def _status(store, snapshots, arg):
    ordered = sorted(snapshots.values(), key=lambda s: (s.repo, s.number))
    if not ordered:
        return [Line(text="No open PRs.")]
    return [
        Line(
            prefix=prs.overall_icon(snap),
            text=f"{snap.repo.partition('/')[2] or snap.repo} #{snap.number}",
            url=snap.url,
            detail=snap.title,
        )
        for snap in ordered
    ]


def _mute(store, snapshots, arg):
    if not arg:
        return [Line(text="Usage: mute org/repo or org/repo#7")]
    if arg not in store.mutes:
        store.mutes.append(arg)
        store.save()
    return [Line(text=f"Muted {arg}")]


def _unmute(store, snapshots, arg):
    if arg in store.mutes:
        store.mutes.remove(arg)
        store.save()
    return [Line(text=f"Unmuted {arg}")]


def _mutes(store, snapshots, arg):
    if not store.mutes:
        return [Line(text="No mutes.")]
    return [Line(text=mute) for mute in store.mutes]


def _toggle(store, snapshots, arg, action):
    if arg not in TOGGLES:
        return [Line(text=f"Unknown notification. Options: {', '.join(TOGGLES)}")]
    if action == "disable" and arg not in store.disabled:
        store.disabled.append(arg)
    if action == "enable" and arg in store.disabled:
        store.disabled.remove(arg)
    store.save()
    return _settings(store, snapshots, "")


def _settings(store, snapshots, arg):
    return [Line(text=f"{name}: {'off' if name in store.disabled else 'on'}") for name in TOGGLES]


def _help(store, snapshots, arg):
    return [Line(text=f"{name}: {description}") for name, description in COMMANDS]


_HANDLERS = {
    "status": _status,
    "mute": _mute,
    "unmute": _unmute,
    "mutes": _mutes,
    "disable": lambda s, n, a: _toggle(s, n, a, "disable"),
    "enable": lambda s, n, a: _toggle(s, n, a, "enable"),
    "settings": _settings,
    "help": _help,
}


def to_html(lines):
    rendered = []
    for line in lines:
        text = prs.html_escape(line.text)
        if line.url:
            text = f'<a href="{line.url}">{text}</a>'
        parts = [p for p in (line.prefix, text) if p]
        body = " ".join(parts)
        if line.detail:
            body = f"{body} \u2014 {prs.html_escape(line.detail)}"
        rendered.append(body)
    return "\n".join(rendered)


def to_mrkdwn(lines):
    rendered = []
    for line in lines:
        text = mrkdwn_escape(line.text)
        if line.url:
            text = f"<{line.url}|{text}>"
        parts = [p for p in (line.prefix, text) if p]
        body = " ".join(parts)
        if line.detail:
            body = f"{body} - {mrkdwn_escape(line.detail)}"
        rendered.append(body)
    return "\n".join(rendered)
