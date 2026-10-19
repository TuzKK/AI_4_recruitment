import json

from recruitment_app.metrics import daily_yield, run_metrics


def test_weighted_metric_and_daily_yield_need_complete_manual_labels():
    candidates = {
        "a": {"coarse": {"decision": "contact"}, "fine": {"decision": "high_match"},
              "state": "sent_verified", "greeting_attempted": True, "greet_verified": True},
        "b": {"coarse": {"decision": "hold"}, "state": "coarse_done", "greeting_attempted": True},
    }
    report = run_metrics(candidates, {"a": "high_match", "b": "rejected"})
    assert report["precontact"]["weighted_score"] == 1.0
    assert report["full_resume"]["weighted_score"] is None
    assert report["daily_yield"] == 1.0
    assert report["meets_10_percent"] is True
    partial = run_metrics(candidates, {"a": "high_match"})
    assert partial["precontact"]["weighted_score"] is None
    assert run_metrics({}, {})["precontact"]["weighted_score"] is None


def test_daily_yield_aggregates_only_confirmed_greetings(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "one.json").write_text(json.dumps({"created_at": "2026-10-13T09:00:00+08:00",
        "candidates": {"a": {"greet_verified": True}, "b": {"greeting_attempted": True}}}), encoding="utf-8")
    (runs / "two.json").write_text(json.dumps({"created_at": "2026-10-13T10:00:00+08:00",
        "candidates": {"a": {"greet_verified": True}, "c": {"greet_verified": True}}}), encoding="utf-8")
    report = daily_yield(tmp_path, "2026-10-13", {"a": "high_match", "c": "rejected"})
    assert report == {"greeted": 2, "high_match_share": 0.5, "meets_10_percent": True}
