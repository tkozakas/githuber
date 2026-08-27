import json

from githuber.notify import Config, is_green, load_state, save_state


def run(status="completed", conclusion="success"):
    return {"status": status, "conclusion": conclusion}


def test_no_checks_is_not_green():
    assert not is_green({"check_runs": []}, {"total_count": 0, "state": "pending"})


def test_all_check_runs_green():
    assert is_green({"check_runs": [run(), run(conclusion="skipped")]}, {"total_count": 0, "state": "pending"})


def test_pending_check_run_blocks():
    assert not is_green({"check_runs": [run(), run(status="in_progress", conclusion=None)]}, {"total_count": 0})


def test_failed_check_run_blocks():
    assert not is_green({"check_runs": [run(), run(conclusion="failure")]}, {"total_count": 0})


def test_legacy_statuses_must_succeed():
    assert not is_green({"check_runs": [run()]}, {"total_count": 1, "state": "failure"})
    assert is_green({"check_runs": [run()]}, {"total_count": 2, "state": "success"})


def test_legacy_statuses_alone_green():
    assert is_green({"check_runs": []}, {"total_count": 1, "state": "success"})


def test_state_round_trip(tmp_path):
    cfg = Config(
        github_token="x",
        telegram_bot_token="x",
        telegram_chat_id="1",
        state_file=str(tmp_path / "state.json"),
    )
    save_state(cfg, {"repo#1@sha": True})
    assert load_state(cfg) == {"repo#1@sha": True}


def test_missing_state_is_empty(tmp_path):
    cfg = Config(
        github_token="x",
        telegram_bot_token="x",
        telegram_chat_id="1",
        state_file=str(tmp_path / "missing.json"),
    )
    assert load_state(cfg) == {}


def test_corrupt_state_is_empty(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{broken")
    cfg = Config(github_token="x", telegram_bot_token="x", telegram_chat_id="1", state_file=str(path))
    assert load_state(cfg) == {}


def test_state_file_is_valid_json(tmp_path):
    cfg = Config(github_token="x", telegram_bot_token="x", telegram_chat_id="1", state_file=str(tmp_path / "s.json"))
    save_state(cfg, {"a": True})
    with open(cfg.state_file) as f:
        assert json.load(f) == {"a": True}


def test_search_queries_include_recent_merges():
    from datetime import UTC, datetime

    from githuber.notify import search_queries

    queries = search_queries("tom", datetime(2026, 8, 27, 13, 20, tzinfo=UTC))
    assert queries[0] == "is:pr is:open author:tom"
    assert queries[1] == "is:pr author:tom is:merged merged:>=2026-08-27T13:05:00Z"
