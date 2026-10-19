import json

from matching_eval.__main__ import main


def test_audit_samples_prints_counts_without_resume_body(capsys):
    assert main(["audit-samples"]) == 0
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["high_match"] == 2
    assert report["rejected"] == 6
    assert len(report["text_characters"]) == 8
    assert "客户" not in output


def test_benchmark_uses_prediction_file_and_reports_missing_ids(tmp_path, capsys):
    path = tmp_path / "predictions.json"
    path.write_text(
        json.dumps(
            {
                "stage": "full_resume",
                "predictions": {
                    "A001": {"decision": "high_match"},
                    "R001": {"decision": "not_fit"},
                },
            }
        ),
        encoding="utf-8",
    )
    assert (
        main(["benchmark", "--stage", "full_resume", "--predictions", str(path)]) == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["tp"] == 1
    assert report["tn"] == 1
    assert report["evaluated"] == 2
    assert len(report["missing_ids"]) == 6


def test_remote_scoring_requires_explicit_flag(capsys):
    assert main(["score-samples", "--output", "ignored.json"]) == 2
    assert "--remote" in capsys.readouterr().err


def test_calibrate_refuses_incomplete_sample_predictions(tmp_path, capsys):
    path = tmp_path / "predictions.json"
    path.write_text(
        json.dumps(
            {
                "stage": "precontact",
                "predictions": {
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
                },
            }
        ),
        encoding="utf-8",
    )
    assert main(["calibrate", "--stage", "precontact", "--predictions", str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "incomplete_data"
    assert len(report["missing_ids"]) == 5


def test_rank_contacts_does_not_fill_quota_with_holds(tmp_path, capsys):
    path = tmp_path / "predictions.json"
    path.write_text(
        json.dumps(
            {
                "stage": "precontact",
                "predictions": {
                    "A001": {"decision": "contact", "score": 82, "eligible": True},
                    "A002": {"decision": "contact", "score": 93, "eligible": True},
                    "R001": {"decision": "hold", "score": 99},
                },
            }
        ),
        encoding="utf-8",
    )
    assert main(["rank-contacts", "--predictions", str(path), "--quota", "5"]) == 0
    assert json.loads(capsys.readouterr().out)["candidate_ids"] == ["A002", "A001"]


def test_daily_yield_uses_reviewed_greeted_records(tmp_path, capsys):
    greeted = tmp_path / "greeted.json"
    labels = tmp_path / "labels.json"
    greeted.write_text('["c1", "c2"]', encoding="utf-8")
    labels.write_text('{"c1":"high_match","c2":"rejected"}', encoding="utf-8")
    assert (
        main(["daily-yield", "--greeted", str(greeted), "--labels", str(labels)]) == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["high_match_share"] == 0.5
    assert report["target_met"] is True


def test_daily_yield_does_not_require_sample_manifest(tmp_path, monkeypatch, capsys):
    greeted = tmp_path / "greeted.json"
    labels = tmp_path / "labels.json"
    greeted.write_text("[]", encoding="utf-8")
    labels.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("matching_eval.__main__.load_manifest", lambda root: 1 / 0)
    assert (
        main(["daily-yield", "--greeted", str(greeted), "--labels", str(labels)]) == 0
    )
    assert json.loads(capsys.readouterr().out)["target_met"] is None


def test_benchmark_compares_current_and_baseline_at_same_stage(tmp_path, capsys):
    current = tmp_path / "current.json"
    baseline = tmp_path / "baseline.json"
    current.write_text(
        json.dumps(
            {
                "stage": "full_resume",
                "predictions": {
                    "A001": {"decision": "high_match"},
                    "R001": {"decision": "not_fit"},
                },
            }
        ),
        encoding="utf-8",
    )
    baseline.write_text(
        json.dumps(
            {
                "stage": "full_resume",
                "predictions": {
                    "A001": {"decision": "not_fit"},
                    "R001": {"decision": "not_fit"},
                },
            }
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "benchmark",
                "--stage",
                "full_resume",
                "--predictions",
                str(current),
                "--baseline",
                str(baseline),
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["current"]["weighted_score"] is None
    assert report["baseline"]["weighted_score"] is None
    assert report["delta_weighted_score"] is None


def test_record_batch_requires_explicit_remote_flag(tmp_path, capsys):
    path = tmp_path / "records.json"
    path.write_text('{"stage":"precontact","records":[]}', encoding="utf-8")
    assert (
        main(
            [
                "score-records",
                "--input",
                str(path),
                "--output",
                str(tmp_path / "out.json"),
            ]
        )
        == 2
    )
    assert "--remote" in capsys.readouterr().err


def test_record_batch_command_scores_normalized_input(tmp_path, monkeypatch, capsys):
    text = "本科计算机专业。客户数据接入与字段映射，使用 SQL 核对数据，编写 Python Logic，参与交付验收。"
    source = tmp_path / "records.json"
    output = tmp_path / "predictions.json"
    source.write_text(
        json.dumps(
            {
                "stage": "precontact",
                "records": [
                    {
                        "candidate_id": "c1",
                        "text": text,
                        "coverage": "partial",
                        "source": "boss_api",
                        "captured_at": "2026-10-13T12:00:00+08:00",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    claim = {
        "education": {"status": "pass", "evidence": "本科计算机专业"},
        "travel": {"status": "unknown", "evidence": ""},
        "criteria": {
            "data_implementation": {"level": 2, "evidence": "客户数据接入与字段映射"},
            "delivery": {"level": 2, "evidence": "交付验收"},
            "sql": {"level": 2, "evidence": "SQL 核对数据"},
            "coding_logic": {"level": 2, "evidence": "Python Logic"},
            "modeling": {"level": 0, "evidence": ""},
            "preferred": {"level": 0, "evidence": ""},
        },
    }
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setenv(
        "MATCHING_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    monkeypatch.setattr(
        "matching_eval.workflow.call_model", lambda *args, **kwargs: claim
    )
    assert (
        main(
            [
                "score-records",
                "--input",
                str(source),
                "--output",
                str(output),
                "--remote",
            ]
        )
        == 0
    )
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["predictions"]["c1"]["decision"] == "contact"
    assert text not in output.read_text(encoding="utf-8")
    assert "evaluated" in capsys.readouterr().out
