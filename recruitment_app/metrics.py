"""Human-label evaluation for arbitrary job rubrics."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from matching_eval.evaluation import evaluate_predictions, high_match_yield


def run_metrics(candidates: dict, labels: dict[str, str]) -> dict:
    if any(value not in {"high_match", "rejected"} for value in labels.values()):
        raise ValueError("人工标签只能是 high_match 或 rejected")
    reports = {}
    missing_labels = sorted(set(candidates) - set(labels))
    for key, stage in (("coarse", "precontact"), ("fine", "full_resume")):
        decisions = {cid: item[key]["decision"] for cid, item in candidates.items()
                     if cid in labels and isinstance(item.get(key), dict) and item[key].get("decision")}
        report = evaluate_predictions(labels, decisions, stage)
        if not decisions:
            report["status"] = "insufficient_data"
            report["weighted_score"] = None
        elif missing_labels:
            report["status"] = "incomplete_labels"
            report["weighted_score"] = None
        report["unlabeled_ids"] = missing_labels
        reports[stage] = report
    greeted = [cid for cid, item in candidates.items() if item.get("greet_verified")]
    if all(cid in labels for cid in greeted):
        yield_value = high_match_yield(greeted, labels)
    else:
        yield_value = None
    reports["daily_yield"] = yield_value
    reports["meets_10_percent"] = None if yield_value is None else yield_value >= 0.10
    return reports


def daily_yield(root: Path, day: str, labels: dict[str, str]) -> dict:
    date.fromisoformat(day)
    greeted = set()
    for path in (Path(root) / "runs").glob("*.json"):
        run = json.loads(path.read_text(encoding="utf-8"))
        if run.get("created_at", "")[:10] == day:
            greeted.update(cid for cid, candidate in run.get("candidates", {}).items()
                           if candidate.get("greet_verified"))
    share = high_match_yield(sorted(greeted), labels) if greeted and greeted <= labels.keys() else None
    return {"greeted": len(greeted), "high_match_share": share,
            "meets_10_percent": None if share is None else share >= 0.10}
