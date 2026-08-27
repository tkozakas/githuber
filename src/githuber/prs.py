from dataclasses import dataclass

OK_CONCLUSIONS = {"success", "neutral", "skipped"}
BODY_LIMIT = 700

CI_ICONS = {"green": "\u2705", "failed": "\u274c", "pending": "\u23f3", "none": "\u2b1c"}
VERDICT_ICONS = {"APPROVED": "\u2705", "CHANGES_REQUESTED": "\U0001f534"}
VERDICT_VERBS = {"APPROVED": "approved", "CHANGES_REQUESTED": "requested changes"}


@dataclass(frozen=True)
class Note:
    kind: str
    author: str = ""
    body: str = ""
    verdict: str = ""


@dataclass(frozen=True)
class Snapshot:
    repo: str
    number: int
    title: str
    url: str
    sha: str
    ci: str
    conflicts: bool
    reviews: tuple


def pr_key(repo, number):
    return f"{repo}#{number}"


def ci_state(check_runs, combined_status):
    runs = check_runs.get("check_runs", [])
    statuses_total = combined_status.get("total_count", 0)
    combined = combined_status.get("state")
    if not runs and statuses_total == 0:
        return "none"
    if any(r.get("status") == "completed" and r.get("conclusion") not in OK_CONCLUSIONS for r in runs):
        return "failed"
    if statuses_total > 0 and combined == "failure":
        return "failed"
    if any(r.get("status") != "completed" for r in runs):
        return "pending"
    if statuses_total > 0 and combined != "success":
        return "pending"
    return "green"


def is_muted(mutes, repo, number):
    return repo in mutes or pr_key(repo, number) in mutes


def is_foreign(login, actor):
    return actor.get("login") != login and actor.get("type") != "Bot"


def latest_verdicts(reviews):
    verdicts = {}
    for review in sorted(reviews, key=lambda r: r.get("submitted_at") or ""):
        if review.get("state") in VERDICT_ICONS:
            verdicts[review["user"]["login"]] = review["state"]
    return verdicts


def comment_note(comment):
    return Note("comment", comment["user"]["login"], comment.get("body") or "")


def review_note(review):
    state = review.get("state", "")
    author = review["user"]["login"]
    body = review.get("body") or ""
    if state in VERDICT_ICONS:
        return Note("verdict", author, body, state)
    return Note("comment", author, body)


def diff_events(record, snap, fresh_comments, fresh_reviews, disabled=frozenset()):
    events = []
    if snap.ci == "green" and record.get("green_sha") != snap.sha:
        record["green_sha"] = snap.sha
        events.append(Note("green"))
    if snap.conflicts and record.get("conflict_sha") != snap.sha:
        record["conflict_sha"] = snap.sha
        events.append(Note("conflict"))
    seen = record.setdefault("comment_ids", [])
    for comment in fresh_comments:
        if comment["id"] not in seen:
            seen.append(comment["id"])
            events.append(comment_note(comment))
    seen = record.setdefault("review_ids", [])
    for review in fresh_reviews:
        if review["id"] not in seen:
            seen.append(review["id"])
            events.append(review_note(review))
    substantial = (e for e in events if e.kind in ("green", "conflict", "verdict") or e.body.strip())
    return [e for e in substantial if e.kind not in disabled]


def html_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def clip(body):
    return body[:BODY_LIMIT] + "\u2026" if len(body) > BODY_LIMIT else body


def render_card(snap, notes=()):
    parts = [_title_line(snap), _status_line(snap)]
    parts.extend(filter(None, (_render_note(n) for n in notes)))
    return "\n".join(parts)


def render_status(snapshots):
    if not snapshots:
        return "No open PRs."
    return "\n".join(_title_line(s) for s in snapshots)


def _title_line(snap):
    link = f'<a href="{snap.url}">{html_escape(pr_key(snap.repo, snap.number))}</a>'
    return f"{CI_ICONS[snap.ci]} <b>{link}</b> \u2014 {html_escape(snap.title)}"


def _status_line(snap):
    verdicts = latest_verdicts(snap.reviews)
    review = (
        " ".join(f"{VERDICT_ICONS[state]}{html_escape(author)}" for author, state in verdicts.items())
        if verdicts
        else "no reviews"
    )
    merge = "\u26a0\ufe0f conflicts" if snap.conflicts else "merge clean"
    return f"CI {snap.ci} \u00b7 {review} \u00b7 {merge}"


def _quote(body):
    return f"\n<blockquote>{html_escape(clip(body))}</blockquote>" if body.strip() else ""


def _render_note(note):
    if note.kind == "green":
        return "\U0001f7e2 CI is green"
    if note.kind == "conflict":
        return "\u26a0\ufe0f Merge conflicts with base branch"
    if note.kind == "comment":
        return f"\U0001f4ac <b>{html_escape(note.author)}</b> commented:{_quote(note.body)}"
    if note.kind == "verdict":
        icon = VERDICT_ICONS[note.verdict]
        verb = VERDICT_VERBS[note.verdict]
        return f"{icon} <b>{html_escape(note.author)}</b> {verb}{_quote(note.body)}"
    return ""
