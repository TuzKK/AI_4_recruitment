import json

import pytest

from matching_eval.workflow import evaluate_document, evaluate_records

TEXT = (
    "本科计算机专业。负责客户数据接入、字段映射和清洗，完成模型初始化。"
    "使用 SQL 核对数据，编写 Python Logic 并调试，参与客户上线验收。"
    "配置对象属性关系，调试 Agent 工作流。"
)
CLAIM = {
    "education": {"status": "pass", "evidence": "本科计算机专业"},
    "travel": {"status": "unknown", "evidence": ""},
    "criteria": {
        "data_implementation": {"level": 2, "evidence": "数据接入、字段映射和清洗"},
        "delivery": {"level": 2, "evidence": "客户上线验收"},
        "sql": {"level": 2, "evidence": "SQL 核对数据"},
        "coding_logic": {"level": 2, "evidence": "Python Logic 并调试"},
        "modeling": {"level": 2, "evidence": "对象属性关系"},
        "preferred": {"level": 1, "evidence": "Agent 工作流"},
    },
}


class GoodResponse:
    status_code = 200

    def json(self):
        return {
            "choices": [
                {"finish_reason": "stop", "message": {"content": json.dumps(CLAIM)}}
            ]
        }


class GoodSession:
    def post(self, url, *, headers, json, timeout):
        return GoodResponse()


def test_document_workflow_returns_evidence_checked_decision():
    result = evaluate_document(
        "full_resume",
        "岗位",
        TEXT,
        "complete",
        "test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        session=GoodSession(),
    )
    assert result["decision"] == "high_match"
    assert result["score"] == 95
    assert result["evidence"]["sql"] == "SQL 核对数据"


def test_network_failure_becomes_review_not_negative_label():
    class FailedSession:
        def post(self, url, *, headers, json, timeout):
            raise TimeoutError

    result = evaluate_document(
        "precontact",
        "岗位",
        TEXT,
        "partial",
        "test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        session=FailedSession(),
    )
    assert result["decision"] == "review"
    assert result["score"] is None


def test_malformed_model_response_becomes_review():
    class MalformedResponse:
        status_code = 200

        def json(self):
            return {
                "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]
            }

    class MalformedSession:
        def post(self, url, *, headers, json, timeout):
            return MalformedResponse()

    result = evaluate_document(
        "full_resume",
        "岗位",
        TEXT,
        "complete",
        "test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        session=MalformedSession(),
    )
    assert result["decision"] == "review"


def test_calibrated_threshold_changes_decision_without_changing_evidence_score():
    result = evaluate_document(
        "full_resume",
        "岗位",
        TEXT,
        "complete",
        "test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        threshold=96,
        session=GoodSession(),
    )
    assert result["score"] == 95
    assert result["decision"] == "potential"


def test_record_batch_retains_provenance_without_copying_resume_body():
    batch = evaluate_records(
        "precontact",
        "岗位",
        [
            {
                "candidate_id": "c1",
                "text": TEXT,
                "coverage": "partial",
                "source": "boss_api",
                "captured_at": "2026-10-13T12:00:00+08:00",
            },
        ],
        "test-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        session=GoodSession(),
    )
    assert batch["predictions"]["c1"]["decision"] == "contact"
    assert batch["predictions"]["c1"]["source"] == "boss_api"
    assert TEXT not in json.dumps(batch, ensure_ascii=False)


def test_invalid_threshold_is_rejected_before_any_model_request():
    class UncalledSession:
        def post(self, *args, **kwargs):
            raise AssertionError("request must not be sent")

    with pytest.raises(ValueError, match="threshold"):
        evaluate_document(
            "full_resume",
            "岗位",
            TEXT,
            "complete",
            "test-key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            threshold=101,
            session=UncalledSession(),
        )


def test_record_batch_requires_source_and_timestamp_before_model_request():
    class UncalledSession:
        def post(self, *args, **kwargs):
            raise AssertionError("request must not be sent")

    with pytest.raises(ValueError, match="source or captured_at"):
        evaluate_records(
            "precontact",
            "岗位",
            [{"candidate_id": "c1", "text": TEXT, "coverage": "partial"}],
            "test-key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            session=UncalledSession(),
        )
