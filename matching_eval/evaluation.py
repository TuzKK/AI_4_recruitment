"""Offline stage metrics and the daily greeted-candidate yield."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def evaluate_predictions(
    labels: Mapping[str, str], decisions: Mapping[str, str], stage: str
) -> dict:
    """Measure only candidates with an input for this stage."""
    positive_decision = {"precontact": "contact", "full_resume": "high_match"}.get(
        stage
    )
    if positive_decision is None:
        raise ValueError("unknown stage")
    allowed_decisions = (
        {"contact", "hold", "reject", "review"}
        if stage == "precontact"
        else {"high_match", "potential", "not_fit", "review"}
    )
    unknown_ids = sorted(set(decisions) - set(labels))
    if unknown_ids:
        raise ValueError(f"unlabeled predictions: {unknown_ids}")
    missing_ids = sorted(set(labels) - set(decisions))
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for candidate_id, decision in decisions.items():
        if labels[candidate_id] not in ("high_match", "rejected"):
            raise ValueError(f"unknown label: {candidate_id}")
        if decision not in allowed_decisions:
            raise ValueError(f"unknown decision: {candidate_id}")
        predicted = decision == positive_decision
        actual = labels[candidate_id] == "high_match"
        counts[("t" if predicted == actual else "f") + ("p" if predicted else "n")] += 1
    precision_denominator = counts["tp"] + counts["fp"]
    recall_denominator = counts["tp"] + counts["fn"]
    precision = counts["tp"] / precision_denominator if precision_denominator else 0.0
    recall = counts["tp"] / recall_denominator if recall_denominator else 0.0
    return {
        **counts,
        "status": "incomplete_data" if missing_ids else "complete",
        "evaluated": len(decisions),
        "missing_ids": missing_ids,
        "precision": precision,
        "recall": recall,
        "weighted_score": None if missing_ids else 0.75 * recall + 0.25 * precision,
    }


def high_match_yield(
    greeted_ids: Sequence[str], labels: Mapping[str, str]
) -> float | None:
    """Share of actually greeted, reviewed people labeled high match."""
    if not greeted_ids:
        return None
    if len(set(greeted_ids)) != len(greeted_ids):
        raise ValueError("duplicate greeted candidate")
    if any(candidate_id not in labels for candidate_id in greeted_ids):
        raise ValueError("greeted candidate lacks a reviewed label")
    if any(
        labels[candidate_id] not in ("high_match", "rejected")
        for candidate_id in greeted_ids
    ):
        raise ValueError("greeted candidate lacks a reviewed label")
    return sum(
        labels[candidate_id] == "high_match" for candidate_id in greeted_ids
    ) / len(greeted_ids)


def rank_contacts(results, quota):
    """Fill at most the quota with qualified contacts, never backfill holds."""
    if type(quota) is not int or quota < 0:
        raise ValueError("quota must be a nonnegative integer")
    candidates = [
        (candidate_id, result["score"])
        for candidate_id, result in results.items()
        if result.get("decision") == "contact"
        and result.get("eligible") is True
        and type(result.get("score")) in (int, float)
        and math.isfinite(result["score"])
    ]
    candidates.sort(key=lambda item: (-item[1], item[0]))
    return [candidate_id for candidate_id, _ in candidates[:quota]]


def calibrate_threshold(labels, results, stage):
    """Search integer cutoffs on labeled, valid inputs; report exploratory fit."""
    if stage not in ("precontact", "full_resume"):
        raise ValueError("unknown stage")
    missing_ids = sorted(set(labels) - set(results))
    if missing_ids:
        return {"status": "incomplete_data", "missing_ids": missing_ids}
    allowed_decisions = (
        {"contact", "hold", "reject", "review"}
        if stage == "precontact"
        else {"high_match", "potential", "not_fit", "review"}
    )
    usable = {
        candidate_id: result
        for candidate_id, result in results.items()
        if candidate_id in labels
        and type(result.get("score")) is int
        and 0 <= result["score"] <= 100
        and type(result.get("eligible")) is bool
        and result.get("decision") in allowed_decisions
        and result.get("coverage") in ("complete", "partial", "unknown")
        and result.get("stage", stage) == stage
    }
    unusable_ids = sorted(set(results) - set(usable))
    if not usable or not any(
        labels[candidate_id] == "high_match" for candidate_id in usable
    ):
        return {
            "status": "insufficient_data",
            "missing_ids": missing_ids,
            "unusable_ids": unusable_ids,
        }
    positive = "contact" if stage == "precontact" else "high_match"
    negative = "hold" if stage == "precontact" else "potential"
    best: tuple | None = None
    best_report: dict | None = None
    for threshold in range(101):
        decisions = {
            candidate_id: (
                "review"
                if result["decision"] == "review"
                or result["coverage"] == "unknown"
                or (stage == "full_resume" and result["coverage"] != "complete")
                else positive
                if result["eligible"]
                and result["score"] >= threshold
                and not result.get("issues")
                else negative
            )
            for candidate_id, result in usable.items()
        }
        metrics = evaluate_predictions(labels, decisions, stage)
        selected = metrics["tp"] + metrics["fp"]
        if stage == "precontact" and (not selected or metrics["precision"] < 0.10):
            continue
        # Threshold last: if equivalent, contact fewer people.
        rank = (
            metrics["weighted_score"],
            metrics["recall"] if stage == "precontact" else metrics["precision"],
            metrics["precision"] if stage == "precontact" else metrics["recall"],
            threshold,
        )
        if best is None or rank > best:
            best = rank
            best_report = {
                "status": "exploratory",
                "threshold": threshold,
                "selected": selected,
                "missing_ids": missing_ids,
                "unusable_ids": unusable_ids,
                **metrics,
            }
    return best_report or {
        "status": "insufficient_data",
        "missing_ids": missing_ids,
        "unusable_ids": unusable_ids,
    }
