import pytest

from matching_eval.evaluation import (
    calibrate_threshold,
    evaluate_predictions,
    high_match_yield,
    rank_contacts,
)


def test_stage_metrics_use_high_match_as_positive_and_weight_recall():
    labels = {
        "A001": "high_match",
        "A002": "high_match",
        "R001": "rejected",
        "R002": "rejected",
    }
    decisions = {"A001": "contact", "A002": "hold", "R001": "contact", "R002": "hold"}
    report = evaluate_predictions(labels, decisions, "precontact")
    assert report["tp"] == 1
    assert report["fp"] == 1
    assert report["fn"] == 1
    assert report["tn"] == 1
    assert report["recall"] == 0.5
    assert report["precision"] == 0.5
    assert report["weighted_score"] == 0.5


def test_missing_predictions_are_reported_not_counted_as_negative():
    labels = {"A001": "high_match", "R001": "rejected"}
    report = evaluate_predictions(labels, {"A001": "high_match"}, "full_resume")
    assert report["evaluated"] == 1
    assert report["missing_ids"] == ["R001"]
    assert report["weighted_score"] is None
    assert report["status"] == "incomplete_data"


def test_unknown_decision_cannot_silently_be_counted_as_negative():
    with pytest.raises(ValueError, match="unknown decision"):
        evaluate_predictions({"A001": "high_match"}, {"A001": "conatct"}, "precontact")


def test_daily_yield_uses_greeted_people_as_denominator():
    labels = {"A001": "high_match", "R001": "rejected", "R002": "rejected"}
    assert high_match_yield(["A001", "R001"], labels) == 0.5
    assert high_match_yield([], labels) is None


def test_daily_yield_rejects_unreviewed_greeted_label():
    with pytest.raises(ValueError, match="reviewed label"):
        high_match_yield(["c1"], {"c1": "pending"})


def test_contact_queue_keeps_unspent_capacity_when_only_two_qualify():
    results = {
        "R001": {"decision": "hold", "score": 99},
        "A001": {"decision": "contact", "score": 82, "eligible": True},
        "A002": {"decision": "contact", "score": 93, "eligible": True},
        "R002": {"decision": "review", "score": None},
    }
    assert rank_contacts(results, quota=5) == ["A002", "A001"]


def test_contact_queue_excludes_ineligible_or_unverified_results():
    results = {
        "A001": {"decision": "contact", "score": 93, "eligible": False},
        "A002": {"decision": "contact", "score": 82},
        "A003": {"decision": "contact", "score": 70, "eligible": True},
    }
    assert rank_contacts(results, quota=5) == ["A003"]


def test_threshold_calibration_respects_contact_precision_floor():
    labels = {"A001": "high_match", "A002": "high_match", "R001": "rejected"}
    results = {
        "A001": {
            "score": 82,
            "eligible": True,
            "decision": "contact",
            "coverage": "partial",
        },
        "A002": {
            "score": 68,
            "eligible": True,
            "decision": "contact",
            "coverage": "partial",
        },
        "R001": {
            "score": 55,
            "eligible": True,
            "decision": "contact",
            "coverage": "partial",
        },
    }
    report = calibrate_threshold(labels, results, "precontact")
    assert report["threshold"] == 68
    assert report["recall"] == 1.0
    assert report["precision"] == 1.0


def test_calibration_preserves_review_for_unknown_coverage():
    labels = {"A001": "high_match", "R001": "rejected"}
    results = {
        "A001": {
            "score": 95,
            "eligible": True,
            "decision": "review",
            "coverage": "unknown",
        },
        "R001": {
            "score": 75,
            "eligible": True,
            "decision": "contact",
            "coverage": "partial",
        },
    }
    report = calibrate_threshold(labels, results, "precontact")
    assert report["status"] == "insufficient_data"


def test_calibration_rejects_results_without_decision_or_coverage():
    labels = {"A001": "high_match", "R001": "rejected"}
    results = {
        "A001": {"score": 95, "eligible": True},
        "R001": {
            "score": 75,
            "eligible": True,
            "decision": "hold",
            "coverage": "partial",
        },
    }
    report = calibrate_threshold(labels, results, "precontact")
    assert report["status"] == "insufficient_data"
    assert "A001" in report["unusable_ids"]


def test_threshold_calibration_reports_missing_stage_inputs():
    labels = {"A001": "high_match", "R001": "rejected"}
    report = calibrate_threshold(labels, {}, "precontact")
    assert report["status"] == "incomplete_data"
    assert report["missing_ids"] == ["A001", "R001"]
