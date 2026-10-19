"""Join model evidence and deterministic scoring without changing source tools."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime, timezone

from .model import call_model
from .scoring import COVERAGES, STAGES, score_candidate


def evaluate_document(
    stage: str,
    job: str,
    text: str,
    coverage: str,
    api_key: str,
    *,
    base_url: str,
    threshold: int | None = None,
    session=None,
) -> dict:
    """Return review on model failure; never mislabel a failed request as negative."""
    if stage not in STAGES or coverage not in COVERAGES:
        raise ValueError("unknown stage or coverage")
    if threshold is not None and (
        type(threshold) is not int or not 0 <= threshold <= 100
    ):
        raise ValueError("threshold must be an integer from 0 to 100")
    provenance = {
        "coverage": coverage,
        "input_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        judgement = call_model(
            stage, job, text, api_key, base_url=base_url, session=session
        )
    except RuntimeError:
        return {
            "stage": stage,
            **provenance,
            "eligible": False,
            "score": None,
            "decision": "review",
            "breakdown": {},
            "unknowns": [],
            "issues": ["model evaluation unavailable"],
            "evidence": {},
        }
    threshold_args = {}
    if threshold is not None:
        key = "contact_threshold" if stage == "precontact" else "high_match_threshold"
        threshold_args[key] = threshold
    result = score_candidate(stage, text, coverage, judgement, **threshold_args)
    result.update(provenance)
    criteria = judgement.get("criteria")
    if not isinstance(criteria, dict):
        criteria = {}
    result["evidence"] = {
        name: claim["evidence"]
        for name, claim in criteria.items()
        if isinstance(claim, dict)
        and result["breakdown"].get(name, 0) > 0
        and isinstance(claim.get("evidence"), str)
    }
    return result


def evaluate_records(
    stage: str,
    job: str,
    records: Sequence[dict],
    api_key: str,
    *,
    base_url: str,
    threshold: int | None = None,
    session=None,
) -> dict:
    """Score normalized stage records without persisting their source text."""
    if stage not in STAGES:
        raise ValueError("unknown stage")
    if not isinstance(records, list):
        raise TypeError("records must be an array")
    if threshold is not None and (
        type(threshold) is not int or not 0 <= threshold <= 100
    ):
        raise ValueError("threshold must be an integer from 0 to 100")
    predictions: dict[str, dict] = {}
    seen_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise TypeError("record must be an object")
        candidate_id = record.get("candidate_id")
        text = record.get("text")
        coverage = record.get("coverage")
        if (
            not isinstance(candidate_id, str)
            or not candidate_id.strip()
            or candidate_id in seen_ids
        ):
            raise ValueError("candidate IDs must be unique nonempty strings")
        if not isinstance(text, str) or not text.strip() or coverage not in COVERAGES:
            raise ValueError(f"invalid text or coverage for {candidate_id}")
        source = record.get("source")
        captured_at = record.get("captured_at")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"invalid source or captured_at for {candidate_id}")
        try:
            captured_time = datetime.fromisoformat(captured_at)
            if captured_time.tzinfo is None or captured_time.utcoffset() is None:
                raise ValueError("timezone is required")
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"invalid source or captured_at for {candidate_id}"
            ) from exc
        seen_ids.add(candidate_id)
    for record in records:
        candidate_id = record["candidate_id"]
        result = evaluate_document(
            stage,
            job,
            record["text"],
            record["coverage"],
            api_key,
            base_url=base_url,
            threshold=threshold,
            session=session,
        )
        result["source"] = record["source"]
        result["captured_at"] = record["captured_at"]
        predictions[candidate_id] = result
    return {"stage": stage, "predictions": predictions}
