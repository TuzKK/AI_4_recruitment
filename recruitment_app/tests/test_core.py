import json
from datetime import datetime, timedelta, timezone

import pytest

from recruitment_app.core import safe_title, score_evidence, validate_rubric
from recruitment_app.runner import RunStore, run_pipeline

JOB = "招聘数据工程师。负责数据接入和 SQL 查询。本科以上。"
RUBRIC = {
    "title": "数据工程师",
    "criteria": [
        {"key": "delivery", "name": "数据接入", "category": "core", "weight": 60, "jd_quote": "数据接入"},
        {"key": "sql", "name": "SQL", "category": "skill", "weight": 40, "jd_quote": "SQL"},
    ],
    "requirements": [{"key": "degree", "name": "本科学历", "stage": "resume", "jd_quote": "本科以上"}],
}


def judgement(text="负责数据接入；熟悉 SQL；本科毕业"):
    return {"claims": {"delivery": {"level": 2, "evidence": "数据接入"},
                       "sql": {"level": 2, "evidence": "SQL"}},
            "requirements": {"degree": {"status": "met", "evidence": "本科毕业"}}}


def test_rubric_requires_job_quotes_and_weight_sum():
    assert validate_rubric(JOB, RUBRIC)["title"] == "数据工程师"
    bad = json.loads(json.dumps(RUBRIC))
    bad["criteria"][0]["weight"] = 50
    with pytest.raises(ValueError, match="100"):
        validate_rubric(JOB, bad)
    bad = json.loads(json.dumps(RUBRIC))
    bad["criteria"][0]["jd_quote"] = "并不存在的职责"
    with pytest.raises(ValueError, match="原文"):
        validate_rubric(JOB, bad)


def test_fine_screen_needs_complete_source_and_hard_evidence():
    rubric = validate_rubric(JOB, RUBRIC)
    text = "负责数据接入；熟悉 SQL；本科毕业"
    assert score_evidence(rubric, text, judgement(), "full_resume", "complete", 75)["decision"] == "high_match"
    assert score_evidence(rubric, text, judgement(), "full_resume", "partial", 75)["decision"] == "review"
    claim = judgement()
    claim["requirements"]["degree"] = {"status": "unknown", "evidence": ""}
    assert score_evidence(rubric, text, claim, "full_resume", "complete", 75)["decision"] == "review"


def test_unsupported_resume_quote_cannot_increase_score():
    claim = judgement()
    claim["claims"]["sql"]["evidence"] = "凭空编造"
    result = score_evidence(validate_rubric(JOB, RUBRIC), "负责数据接入；本科毕业", claim, "full_resume", "complete", 75)
    assert result["decision"] == "review"
    assert result["score"] == 60


def test_safe_title_blocks_path_traversal():
    assert safe_title(" ../数据/工程师:*? ") == "数据_工程师"


def test_scoring_rubric_is_not_tied_to_ontology_role():
    job = "招聘客户成功经理。负责客户续约与商务谈判，要求熟悉 CRM 系统。"
    rubric = validate_rubric(job, {"title": "客户成功经理", "criteria": [
        {"key": "renewal", "name": "续约", "category": "core", "weight": 70, "jd_quote": "客户续约"},
        {"key": "crm", "name": "CRM", "category": "skill", "weight": 30, "jd_quote": "CRM 系统"},
    ], "requirements": []})
    result = score_evidence(rubric, "负责客户续约，熟悉 CRM 系统", {"claims": {
        "renewal": {"level": 2, "evidence": "客户续约"},
        "crm": {"level": 2, "evidence": "CRM 系统"}}, "requirements": {}},
        "full_resume", "complete", 75)
    assert result["decision"] == "high_match"


def test_citation_accepts_chinese_pdf_line_wrap_but_not_changed_content():
    from recruitment_app.core import _contains
    assert _contains("使用 Python 和 SQL 进行数据清洗，协\n助团队优化产品功能。", "使用 Python 和 SQL 进行数据清洗，协助团队优化产品功能。")
    assert not _contains("未使用 SQL，协\n助团队沟通。", "使用 SQL，协助团队开发。")
    assert not _contains("Java Script", "JavaScript")
    assert _contains("State Schema、Policy、\n  Prompt", "State Schema、Policy、Prompt")


class FakeModel:
    def rubric(self, job):
        return RUBRIC

    def evidence(self, stage, rubric, text):
        return judgement()


class FakeBoss:
    def __init__(self, complete=True):
        self.complete = complete
        self.greeted = []
        self.sent = []

    def cards(self):
        return [{"candidate_id": "id-1", "name": "测试甲", "text": "负责数据接入；熟悉 SQL；本科毕业"}]

    def full_resume(self, candidate_id):
        return {"candidate_id": candidate_id, "text": "负责数据接入；熟悉 SQL；本科毕业",
                "coverage": "complete" if self.complete else "partial", "source": "test"}

    def greet(self, candidate_id):
        self.greeted.append(candidate_id)
        return True

    def send_first(self, candidate_id, message):
        self.sent.append(candidate_id)
        return True


def test_pipeline_exports_only_verified_contacts(tmp_path):
    store = RunStore(tmp_path)
    boss = FakeBoss()
    run_id = store.create(JOB, 1, 30, 75, "你好，我们在招「{职位名称}」。")
    run_pipeline(store, run_id, FakeModel(), boss)
    result = store.get(run_id)
    assert result["status"] == "finished"
    assert result["contacted"] == 1
    date = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    output = tmp_path / "results" / f"数据工程师_{date}" / "qualified_contacted.txt"
    assert "测试甲｜id-1｜100" in output.read_text(encoding="utf-8")


def test_incomplete_resume_never_greets(tmp_path):
    store = RunStore(tmp_path)
    boss = FakeBoss(complete=False)
    run_id = store.create(JOB, 1, 30, 75, "你好")
    run_pipeline(store, run_id, FakeModel(), boss)
    assert boss.greeted == []
    assert store.get(run_id)["contacted"] == 0


def test_pipeline_uses_detailed_assessment_and_persists_reason(tmp_path):
    class DetailedModel(FakeModel):
        def evidence(self, *args):
            raise AssertionError("Legacy scorer must not run")
        def assess(self, stage, rubric, text, coverage, threshold):
            return {"score": 92.5, "decision": "contact" if stage == "precontact" else "high_match",
                    "reason": "有数据接入和 SQL 实操证据。", "scoring_version": "detailed-v3-spans"}
    store, boss = RunStore(tmp_path), FakeBoss()
    run_id = store.create(JOB, 1, 30, 75, "你好")
    run_pipeline(store, run_id, DetailedModel(), boss)
    candidate = store.get(run_id)["candidates"]["id-1"]
    assert candidate["fine"]["score"] == 92.5
    assert candidate["fine"]["reason"]
    assert boss.greeted == ["id-1"]


def test_restart_marks_pending_write_for_review(tmp_path):
    store = RunStore(tmp_path)
    run_id = store.create(JOB, 1, 30, 75, "你好")
    store.update(run_id, status="running")
    store.candidate(run_id, "id-1", name="测试甲", state="greet_pending", greeting_attempted=True)
    store.recover()
    result = store.get(run_id)
    assert result["status"] == "paused"
    assert result["candidates"]["id-1"]["state"] == "needs_review"


def test_greeting_quota_counts_attempts_even_when_message_fails(tmp_path):
    class TwoCandidates(FakeBoss):
        def cards(self):
            return [{"candidate_id": f"id-{i}", "name": f"测试{i}",
                     "text": "负责数据接入；熟悉 SQL；本科毕业"} for i in (1, 2)]

        def send_first(self, candidate_id, message):
            raise RuntimeError("发送结果不明")

    store = RunStore(tmp_path)
    boss = TwoCandidates()
    run_id = store.create(JOB, 2, 30, 75, "你好")
    run_pipeline(store, run_id, FakeModel(), boss)
    assert len(boss.greeted) == 1
    assert store.get(run_id)["contacted"] == 0
    assert store.get(run_id)["status"] == "paused"
