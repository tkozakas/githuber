from githuber.prs import (
    CI_LABELS,
    VERDICT_VERBS,
    clip,
    latest_verdicts,
)

CI_EMOJI = {
    "green": ":white_check_mark:",
    "failed": ":x:",
    "pending": ":large_yellow_circle:",
    "none": ":heavy_minus_sign:",
}
OVERALL_EMOJI = {
    "green": ":large_green_circle:",
    "failed": ":red_circle:",
    "pending": ":large_yellow_circle:",
    "none": ":white_circle:",
}
CONFLICT_EMOJI = ":warning:"
VERDICT_EMOJI = {"APPROVED": ":white_check_mark:", "CHANGES_REQUESTED": ":octagonal_sign:"}
NOTE_EMOJI = {"green": ":tada:", "conflict": ":warning:", "comment": ":speech_balloon:"}


def mrkdwn_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _overall_emoji(snap):
    if snap.conflicts:
        return CONFLICT_EMOJI
    return OVERALL_EMOJI[snap.ci]


def _quote(body):
    if not body.strip():
        return ""
    quoted = "\n".join(f">{line}" for line in mrkdwn_escape(clip(body)).splitlines())
    return f"\n{quoted}"


def render_notes_mrkdwn(notes):
    lines = []
    for note in notes:
        if note.kind == "green":
            lines.append(f"{NOTE_EMOJI['green']} CI passed")
        elif note.kind == "conflict":
            lines.append(f"{NOTE_EMOJI['conflict']} Merge conflicts with base branch")
        elif note.kind == "comment":
            lines.append(f"{NOTE_EMOJI['comment']} *{mrkdwn_escape(note.author)}*{_quote(note.body)}")
        elif note.kind == "verdict":
            emoji = VERDICT_EMOJI[note.verdict]
            verb = VERDICT_VERBS[note.verdict]
            lines.append(f"{emoji} *{mrkdwn_escape(note.author)}* {verb}{_quote(note.body)}")
    return "\n".join(lines)


def _review_field(snap):
    verdicts = latest_verdicts(snap.reviews)
    if not verdicts:
        return "none yet"
    return " ".join(f"{VERDICT_EMOJI[state]} {mrkdwn_escape(author)}" for author, state in verdicts.items())


def card_blocks(snap, notes_mrkdwn=""):
    name = snap.repo.partition("/")[2] or snap.repo
    merge = f"{CONFLICT_EMOJI} conflicts" if snap.conflicts else ":white_check_mark: clean"
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{_overall_emoji(snap)} *<{snap.url}|{mrkdwn_escape(name)} #{snap.number}>*"
                f"\n{mrkdwn_escape(snap.title)}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*CI*\n{CI_EMOJI[snap.ci]} {CI_LABELS[snap.ci]}"},
                {"type": "mrkdwn", "text": f"*Review*\n{_review_field(snap)}"},
                {"type": "mrkdwn", "text": f"*Merge*\n{merge}"},
            ],
        },
    ]
    if notes_mrkdwn:
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": notes_mrkdwn}})
    return blocks


def card_fallback(snap):
    name = snap.repo.partition("/")[2] or snap.repo
    return f"{name} #{snap.number}: CI {CI_LABELS[snap.ci]}"
