"""Local sample audit, evidence scoring, and stage metrics."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .evaluation import (
    calibrate_threshold,
    evaluate_predictions,
    high_match_yield,
    rank_contacts,
)
from .model import MODEL
from .samples import extract_pdf_text, load_manifest
from .workflow import evaluate_document, evaluate_records

SAMPLE_ROOT = Path(__file__).resolve().parents[1] / "Samples_for_optimization"
PROMPT_VERSION = 1


def _print_json(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _write_json(path: Path, value: dict) -> None:
    """Atomically write private results without printing resume contents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".tmp",
            prefix="matching-",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary = handle.name
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _remote_config() -> tuple[str, str] | None:
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    base_url = os.environ.get("MATCHING_BASE_URL", "")
    if not key or not base_url:
        print(
            "Set DASHSCOPE_API_KEY and MATCHING_BASE_URL locally before --remote.",
            file=sys.stderr,
        )
        return None
    return key, base_url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Private recruitment matching evaluation"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "audit-samples", help="verify hashes and local PDF text coverage"
    )

    benchmark = commands.add_parser(
        "benchmark", help="compare saved predictions with labels"
    )
    benchmark.add_argument(
        "--stage", choices=("precontact", "full_resume"), required=True
    )
    benchmark.add_argument("--predictions", type=Path, required=True)
    benchmark.add_argument("--baseline", type=Path)

    calibrate = commands.add_parser("calibrate")
    calibrate.add_argument(
        "--stage", choices=("precontact", "full_resume"), required=True
    )
    calibrate.add_argument("--predictions", type=Path, required=True)

    rank = commands.add_parser("rank-contacts")
    rank.add_argument("--predictions", type=Path, required=True)
    rank.add_argument("--quota", type=int, required=True)

    daily = commands.add_parser("daily-yield")
    daily.add_argument("--greeted", type=Path, required=True)
    daily.add_argument("--labels", type=Path, required=True)

    batch = commands.add_parser("score-samples", help="score all full-resume PDFs")
    batch.add_argument(
        "--remote",
        action="store_true",
        help="send resume text to configured Alibaba model",
    )
    batch.add_argument("--output", type=Path, required=True)
    batch.add_argument("--threshold", type=int)

    records = commands.add_parser("score-records")
    records.add_argument("--input", type=Path, required=True)
    records.add_argument("--output", type=Path, required=True)
    records.add_argument("--threshold", type=int)
    records.add_argument("--remote", action="store_true")

    one = commands.add_parser("score", help="score a supplied stage-specific text file")
    one.add_argument("--stage", choices=("precontact", "full_resume"), required=True)
    one.add_argument("--candidate-id", required=True)
    one.add_argument("--text-file", type=Path, required=True)
    one.add_argument(
        "--coverage", choices=("complete", "partial", "unknown"), required=True
    )
    one.add_argument("--remote", action="store_true")
    one.add_argument("--output", type=Path)
    one.add_argument("--threshold", type=int)

    args = parser.parse_args(argv)
    samples = None
    labels = None
    if args.command in ("audit-samples", "score-samples", "benchmark", "calibrate"):
        samples = load_manifest(SAMPLE_ROOT)
        labels = {sample["id"]: sample["label"] for sample in samples}
    if args.command == "daily-yield":
        greeted = json.loads(args.greeted.read_text(encoding="utf-8"))
        reviewed_labels = json.loads(args.labels.read_text(encoding="utf-8"))
        share = high_match_yield(greeted, reviewed_labels)
        _print_json(
            {
                "greeted": len(greeted),
                "high_match_share": share,
                "target": 0.10,
                "target_met": share >= 0.10 if share is not None else None,
            }
        )
        return 0
    if args.command == "audit-samples":
        lengths = {
            sample["id"]: len(extract_pdf_text(SAMPLE_ROOT / sample["file"]))
            for sample in samples
        }
        _print_json(
            {
                "high_match": sum(label == "high_match" for label in labels.values()),
                "rejected": sum(label == "rejected" for label in labels.values()),
                "text_characters": lengths,
            }
        )
        return 0
    if args.command == "benchmark":
        predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
        if predictions.get("stage") != args.stage:
            print("Prediction stage does not match --stage.", file=sys.stderr)
            return 2
        decisions = {
            candidate_id: value["decision"] if isinstance(value, dict) else value
            for candidate_id, value in predictions["predictions"].items()
        }
        current_report = evaluate_predictions(labels, decisions, args.stage)
        if args.baseline:
            baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
            if baseline.get("stage") != args.stage:
                print("Baseline stage does not match --stage.", file=sys.stderr)
                return 2
            baseline_decisions = {
                candidate_id: value["decision"] if isinstance(value, dict) else value
                for candidate_id, value in baseline["predictions"].items()
            }
            if set(decisions) != set(baseline_decisions):
                print("Baseline and current candidate IDs must match.", file=sys.stderr)
                return 2
            baseline_report = evaluate_predictions(
                labels, baseline_decisions, args.stage
            )
            _print_json(
                {
                    "current": current_report,
                    "baseline": baseline_report,
                    "delta_weighted_score": current_report["weighted_score"]
                    - baseline_report["weighted_score"]
                    if current_report["weighted_score"] is not None
                    and baseline_report["weighted_score"] is not None
                    else None,
                }
            )
        else:
            _print_json(current_report)
        return 0
    if args.command == "calibrate":
        predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
        if predictions.get("stage") != args.stage:
            print("Prediction stage does not match --stage.", file=sys.stderr)
            return 2
        _print_json(calibrate_threshold(labels, predictions["predictions"], args.stage))
        return 0
    if args.command == "rank-contacts":
        predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
        if predictions.get("stage") != "precontact":
            print("Contact ranking requires precontact predictions.", file=sys.stderr)
            return 2
        _print_json(
            {"candidate_ids": rank_contacts(predictions["predictions"], args.quota)}
        )
        return 0
    if args.command == "score-records" and not args.remote:
        print("Remote model scoring requires explicit --remote.", file=sys.stderr)
        return 2
    if not args.remote:
        print("Remote model scoring requires explicit --remote.", file=sys.stderr)
        return 2
    config = _remote_config()
    if config is None:
        return 2
    key, base_url = config
    job = (SAMPLE_ROOT / "recruitment_request.txt").read_text(encoding="utf-8")
    if args.command == "score-records":
        source = json.loads(args.input.read_text(encoding="utf-8"))
        report = evaluate_records(
            source["stage"],
            job,
            source["records"],
            key,
            base_url=base_url,
            threshold=args.threshold,
        )
        report.update({"model": MODEL, "prompt_version": PROMPT_VERSION})
        _write_json(args.output, report)
        _print_json(
            {"output": str(args.output), "evaluated": len(report["predictions"])}
        )
        return 0
    if args.command == "score-samples":
        predictions = {}
        for sample in samples:
            text = extract_pdf_text(SAMPLE_ROOT / sample["file"])
            result = evaluate_document(
                "full_resume",
                job,
                text,
                "complete",
                key,
                base_url=base_url,
                threshold=args.threshold,
            )
            result["source"] = "sample_pdf"
            result["source_sha256"] = sample["sha256"]
            predictions[sample["id"]] = result
        report = {
            "stage": "full_resume",
            "model": MODEL,
            "prompt_version": PROMPT_VERSION,
            "predictions": predictions,
        }
        _write_json(args.output, report)
        _print_json({"output": str(args.output), "evaluated": len(predictions)})
        return 0
    if args.text_file.suffix.lower() not in (".txt", ".md"):
        print(
            "--text-file must be .txt or .md stage-specific evidence.", file=sys.stderr
        )
        return 2
    text = args.text_file.read_text(encoding="utf-8")
    result = evaluate_document(
        args.stage,
        job,
        text,
        args.coverage,
        key,
        base_url=base_url,
        threshold=args.threshold,
    )
    report = {
        "stage": args.stage,
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "candidate_id": args.candidate_id,
        "result": result,
    }
    if args.output:
        _write_json(args.output, report)
        _print_json({"output": str(args.output), "decision": result["decision"]})
    else:
        _print_json(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
