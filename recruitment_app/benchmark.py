"""Offline comparison of the live and shadow full-resume scorers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from matching_eval.evaluation import evaluate_predictions
from matching_eval.samples import extract_pdf_text, load_manifest

from .core import score_evidence, validate_rubric
from .llm import JobModel
from .shadow_matching import ShadowMatcher


def benchmark_full_resumes(job: str, cases: list[dict], model, threshold: int = 75) -> dict:
    """Use one hosted LLM judgement per resume for both score variants."""
    if type(threshold) is not int or not 0 <= threshold <= 100:
        raise ValueError("threshold must be an integer from 0 to 100")
    rubric = validate_rubric(job, model.rubric(job))
    shadow = ShadowMatcher()
    labels: dict[str, dict[str, str]] = {"private": {}, "external_negative": {}}
    legacy: dict[str, dict[str, str]] = {"private": {}, "external_negative": {}}
    proposed: dict[str, dict[str, str]] = {"private": {}, "external_negative": {}}
    rows: list[dict] = []
    for case in cases:
        candidate_id, label, group, text = (case[key] for key in ("id", "label", "group", "text"))
        if group not in labels or label not in {"high_match", "rejected"}:
            raise ValueError("unknown benchmark group or label")
        if group == "external_negative" and label != "rejected":
            raise ValueError("external corpus contains only negative examples")
        if candidate_id in labels[group]:
            raise ValueError("duplicate benchmark ID")
        labels[group][candidate_id] = label
        if not isinstance(text, str) or not 0 < len(text) <= 30000:
            rows.append({"id": candidate_id, "group": group, "error": "text_length"})
            continue
        try:
            judgement = model.evidence("full_resume", rubric, text)
            current = score_evidence(rubric, text, judgement, "full_resume", "complete", threshold)
            candidate = shadow.score(rubric, text, judgement, "full_resume", "complete", threshold)
        except Exception as exc:
            rows.append({"id": candidate_id, "group": group, "error": type(exc).__name__})
            continue
        legacy[group][candidate_id] = current["decision"]
        proposed[group][candidate_id] = candidate["decision"]
        rows.append({"id": candidate_id, "group": group, "label": label,
                     "legacy_score": current["score"], "legacy_decision": current["decision"],
                     "shadow_score": candidate["score"], "shadow_decision": candidate["decision"],
                     "skill_ratio": candidate["skill_ratio"]})
    private = {name: evaluate_predictions(labels["private"], decisions, "full_resume")
               for name, decisions in (("legacy", legacy["private"]), ("shadow", proposed["private"]))}
    negatives = {"total": len(labels["external_negative"]),
                 "evaluated": len(proposed["external_negative"]),
                 "legacy_false_positives": sum(v == "high_match" for v in legacy["external_negative"].values()),
                 "shadow_false_positives": sum(v == "high_match" for v in proposed["external_negative"].values()),
                 "status": ("complete" if len(proposed["external_negative"]) == len(labels["external_negative"])
                            else "incomplete_data")}
    return {"job_title": rubric["title"], "threshold": threshold, "private": private,
            "external_negative": negatives, "cases": rows}


def load_cases(sample_root: Path) -> list[dict]:
    """Validate private PDF hashes and the separately licensed text negatives."""
    sample_root = Path(sample_root).resolve()
    cases = []
    for sample in load_manifest(sample_root):
        cases.append({"id": sample["id"], "label": sample["label"], "group": "private",
                      "text": extract_pdf_text(sample_root / sample["file"])})
    external_root = sample_root / "external_negative"
    manifest = json.loads((external_root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or not manifest.get("source_commit"):
        raise ValueError("external negative provenance missing")
    for sample in manifest["samples"]:
        path = (external_root / sample["file"]).resolve()
        if not path.is_relative_to(external_root) or path.suffix.lower() != ".txt":
            raise ValueError("external sample path escapes directory")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != sample["sha256"]:
            raise ValueError("external sample hash changed")
        cases.append({"id": sample["id"], "label": "rejected", "group": "external_negative",
                      "text": content.decode("utf-8")})
    return cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare live and shadow scoring using DashScope API")
    parser.add_argument("--sample-root", type=Path, default=Path("Samples_for_optimization"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=int, default=75)
    args = parser.parse_args(argv)
    job = (args.sample_root / "recruitment_request.txt").read_text(encoding="utf-8")
    report = benchmark_full_resumes(job, load_cases(args.sample_root), JobModel.from_environment(), args.threshold)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"private": report["private"], "external_negative": report["external_negative"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
