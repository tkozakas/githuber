from githuber.prs import (
    CI_ICONS,
    CI_LABELS,
    CONFLICT_ICON,
    VERDICT_ICONS,
    VERDICT_VERBS,
    clip,
    latest_verdicts,
    overall_icon,
)

NOTE_ICONS = {"green": "\U0001f389", "comment": "\U0001f4ac"}


def mrkdwn_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _quote(body):
    if not body.strip():
        return ""
    quoted = "\n".join(f">{line}" for line in mrkdwn_escape(clip(body)).splitlines())
    return f"\n{quoted}"


def render_notes_mrkdwn(notes):
    lines = []
    for note in notes:
        if note.kind == "green":
            lines.append(f"{NOTE_ICONS['green']} CI passed")
        elif note.kind == "conflict":
            lines.append(f"{CONFLICT_ICON} Merge conflicts with base branch")
        elif note.kind == "comment":
            lines.append(f"{NOTE_ICONS['comment']} *{mrkdwn_escape(note.author)}*{_quote(note.body)}")
        elif note.kind == "verdict":
            icon = VERDICT_ICONS[note.verdict]
            verb = VERDICT_VERBS[note.verdict]
            lines.append(f"{icon} *{mrkdwn_escape(note.author)}* {verb}{_quote(note.body)}")
    return "\n".join(lines)


def _title_lines(snap):
    name = snap.repo.partition("/")[2] or snap.repo
    link = f"<{snap.url}|{mrkdwn_escape(name)} #{snap.number}>"
    return f"{overall_icon(snap)} *{link}*\n*{mrkdwn_escape(snap.title)}*"


def _status_lines(snap):
    verdicts = latest_verdicts(snap.reviews)
    review = (
        " \u00b7 ".join(f"{VERDICT_ICONS[state]} {mrkdwn_escape(author)}" for author, state in verdicts.items())
        if verdicts
        else "\u2796 none yet"
    )
    merge = f"{CONFLICT_ICON} conflicts" if snap.conflicts else "\u2705 clean"
    return "\n".join(
        (
            f"`CI     `{CI_ICONS[snap.ci]} {CI_LABELS[snap.ci]}",
            f"`Review `{review}",
            f"`Merge  `{merge}",
        )
    )


def card_blocks(snap, notes_mrkdwn=""):
    text = f"{_title_lines(snap)}\n\n{_status_lines(snap)}"
    if notes_mrkdwn:
        text = f"{text}\n\n{notes_mrkdwn}"
    return [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]


def card_fallback(snap):
    name = snap.repo.partition("/")[2] or snap.repo
    return f"{name} #{snap.number}: CI {CI_LABELS[snap.ci]}"
