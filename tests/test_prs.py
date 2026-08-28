from githuber.prs import (
    Note,
    Snapshot,
    ci_state,
    clip,
    diff_events,
    is_muted,
    latest_verdicts,
    render_card,
    render_notes,
    render_status,
)


def run(status="completed", conclusion="success"):
    return {"status": status, "conclusion": conclusion}


def snap(**overrides):
    fields = {
        "repo": "org/repo",
        "number": 7,
        "title": "Fix <thing>",
        "url": "https://github.com/org/repo/pull/7",
        "sha": "abc",
        "ci": "green",
        "conflicts": False,
        "reviews": (),
    }
    fields.update(overrides)
    return Snapshot(**fields)


def test_ci_state_none_without_checks():
    assert ci_state({"check_runs": []}, {"total_count": 0, "state": "pending"}) == "none"


def test_ci_state_green():
    assert ci_state({"check_runs": [run(), run(conclusion="skipped")]}, {"total_count": 0}) == "green"


def test_ci_state_pending_while_running():
    checks = {"check_runs": [run(), run(status="in_progress", conclusion=None)]}
    assert ci_state(checks, {"total_count": 0}) == "pending"


def test_ci_state_failed_beats_pending():
    checks = {"check_runs": [run(conclusion="failure"), run(status="queued", conclusion=None)]}
    assert ci_state(checks, {"total_count": 0}) == "failed"


def test_ci_state_legacy_statuses():
    assert ci_state({"check_runs": [run()]}, {"total_count": 1, "state": "failure"}) == "failed"
    assert ci_state({"check_runs": [run()]}, {"total_count": 1, "state": "pending"}) == "pending"
    assert ci_state({"check_runs": []}, {"total_count": 1, "state": "success"}) == "green"


def test_diff_events_green_once_per_sha():
    record = {}
    assert [e.kind for e in diff_events(record, snap(), [], [])] == ["green"]
    assert diff_events(record, snap(), [], []) == []
    assert [e.kind for e in diff_events(record, snap(sha="def"), [], [])] == ["green"]


def test_diff_events_conflicts_once_per_sha():
    record = {}
    events = diff_events(record, snap(ci="pending", conflicts=True), [], [])
    assert [e.kind for e in events] == ["conflict"]
    assert diff_events(record, snap(ci="pending", conflicts=True), [], []) == []


def test_diff_events_comments_deduped():
    record = {}
    comment = {"id": 1, "user": {"login": "alice"}, "body": "hi"}
    assert [e.kind for e in diff_events(record, snap(ci="pending"), [comment], [])] == ["comment"]
    assert diff_events(record, snap(ci="pending"), [comment], []) == []


def test_diff_events_drops_empty_comment():
    events = diff_events({}, snap(ci="pending"), [{"id": 1, "user": {"login": "a"}, "body": " "}], [])
    assert events == []


def test_diff_events_review_verdict():
    review = {"id": 5, "user": {"login": "bob"}, "state": "CHANGES_REQUESTED", "body": "fix it"}
    events = diff_events({}, snap(ci="pending"), [], [review])
    assert events == [Note("verdict", "bob", "fix it", "CHANGES_REQUESTED")]


def test_latest_verdict_wins_per_author():
    reviews = (
        {"user": {"login": "bob"}, "state": "CHANGES_REQUESTED", "submitted_at": "2026-01-01T00:00:00Z"},
        {"user": {"login": "bob"}, "state": "APPROVED", "submitted_at": "2026-01-02T00:00:00Z"},
    )
    assert latest_verdicts(reviews) == {"bob": "APPROVED"}


def test_render_card_escapes_and_quotes():
    card = render_card(snap(), render_notes([Note("comment", "alice", "looks <good> & bad")]))
    assert '<a href="https://github.com/org/repo/pull/7">org/repo#7</a>' in card
    assert "Fix &lt;thing&gt;" in card
    assert "<blockquote>looks &lt;good&gt; &amp; bad</blockquote>" in card


def test_render_card_verdict_line():
    card = render_card(snap(), render_notes([Note("verdict", "bob", "", "APPROVED")]))
    assert "<b>bob</b> approved" in card
    assert "<blockquote>" not in card


def test_render_card_status_line():
    reviews = ({"user": {"login": "bob"}, "state": "APPROVED", "submitted_at": "2026-01-01T00:00:00Z"},)
    card = render_card(snap(conflicts=True, reviews=reviews))
    assert "CI green" in card
    assert "\u2705bob" in card
    assert "conflicts" in card


def test_render_status_empty():
    assert render_status([]) == "No open PRs."


def test_is_muted():
    assert is_muted(["org/repo"], "org/repo", 7)
    assert is_muted(["org/repo#7"], "org/repo", 7)
    assert not is_muted(["org/repo#8"], "org/repo", 7)


def test_clip():
    assert clip("x" * 701) == "x" * 700 + "\u2026"
    assert clip("short") == "short"


def test_diff_events_respects_disabled():
    record = {}
    comment = {"id": 1, "user": {"login": "alice"}, "body": "hi"}
    events = diff_events(record, snap(), [comment], [], disabled={"green"})
    assert [e.kind for e in events] == ["comment"]
    assert record["green_sha"] == "abc"
    assert diff_events(record, snap(), [], []) == []


def test_render_card_reflects_state_drift():
    notes = render_notes([Note("green")])
    green = render_card(snap(), notes)
    red = render_card(snap(ci="failed"), notes)
    conflicted = render_card(snap(conflicts=True), notes)
    assert green != red
    assert "CI failed" in red
    assert "\u26a0\ufe0f conflicts".encode().decode("unicode_escape") in conflicted or "conflicts" in conflicted
    assert notes in red
