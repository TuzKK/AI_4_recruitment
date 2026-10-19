from matching_eval.scoring import score_candidate

TEXT = (
    "本科计算机专业。负责客户数据接入、字段映射和清洗，完成模型初始化。"
    "使用 SQL 核对数据，编写 Python Logic 并调试，参与客户上线验收。"
    "配置对象属性关系，调试 Agent 工作流。"
)


def judgement(**overrides):
    criteria = {
        "data_implementation": {"level": 2, "evidence": "数据接入、字段映射和清洗"},
        "delivery": {"level": 2, "evidence": "客户上线验收"},
        "sql": {"level": 2, "evidence": "SQL 核对数据"},
        "coding_logic": {"level": 2, "evidence": "Python Logic 并调试"},
        "modeling": {"level": 2, "evidence": "对象属性关系"},
        "preferred": {"level": 1, "evidence": "Agent 工作流"},
    }
    criteria.update(overrides)
    return {
        "education": {"status": "pass", "evidence": "本科计算机专业"},
        "travel": {"status": "unknown", "evidence": ""},
        "criteria": criteria,
    }


def test_full_resume_scores_job_evidence_and_marks_high_match():
    result = score_candidate("full_resume", TEXT, "complete", judgement())
    assert result["score"] == 95
    assert result["decision"] == "high_match"
    assert result["eligible"] is True
    assert result["breakdown"]["delivery"] == 25


def test_precontact_contacts_only_with_primary_and_technical_evidence():
    result = score_candidate("precontact", TEXT, "partial", judgement())
    assert result["decision"] == "contact"
    assert result["eligible"] is True

    weak = judgement(
        data_implementation={"level": 0, "evidence": ""},
        delivery={"level": 0, "evidence": ""},
    )
    weak_result = score_candidate("precontact", TEXT, "partial", weak)
    assert weak_result["decision"] == "hold"
    assert weak_result["eligible"] is False


def test_unquoted_skill_cannot_raise_score_or_reject_candidate():
    unsupported = judgement(sql={"level": 2, "evidence": "精通 SQL 性能优化"})
    result = score_candidate("full_resume", TEXT, "complete", unsupported)
    assert result["breakdown"]["sql"] == 0
    assert result["decision"] == "review"
    assert "unsupported evidence: sql" in result["issues"]


def test_missing_education_is_unknown_not_rejected():
    claim = judgement()
    claim["education"] = {"status": "unknown", "evidence": ""}
    result = score_candidate("precontact", TEXT, "partial", claim)
    assert result["decision"] == "contact"
    assert "education" in result["unknowns"]


def test_explicit_education_failure_rejects_even_with_high_score():
    claim = judgement()
    claim["education"] = {"status": "fail", "evidence": "大专"}
    result = score_candidate(
        "full_resume",
        "大专。" + TEXT.replace("本科计算机专业。", ""),
        "complete",
        claim,
    )
    assert result["decision"] == "not_fit"


def test_conflicting_degree_evidence_goes_to_review():
    claim = judgement()
    claim["education"] = {"status": "fail", "evidence": "大专"}
    result = score_candidate("full_resume", "大专。" + TEXT, "complete", claim)
    assert result["decision"] == "review"
    assert "conflicting education evidence" in result["issues"]


def test_education_pass_requires_degree_in_its_quoted_evidence():
    claim = judgement()
    claim["education"] = {"status": "pass", "evidence": "客户上线验收"}
    result = score_candidate("full_resume", TEXT, "complete", claim)
    assert result["decision"] == "review"
    assert "unverified education pass" in result["issues"]


def test_hard_fail_requires_specific_negative_quote():
    claim = judgement()
    claim["travel"] = {"status": "fail", "evidence": "Agent 工作流"}
    result = score_candidate("precontact", TEXT, "partial", claim)
    assert result["decision"] == "review"
    assert "unverified hard failure: travel" in result["issues"]


def test_partial_full_resume_cannot_be_declared_high_match():
    result = score_candidate("full_resume", TEXT, "partial", judgement())
    assert result["decision"] == "review"


def test_unknown_precontact_coverage_is_ineligible_for_contact():
    result = score_candidate("precontact", TEXT, "unknown", judgement())
    assert result["decision"] == "review"
    assert result["eligible"] is False


def test_full_resume_rejects_reused_irrelevant_evidence_as_high_match():
    text = "本科美术专业，熟悉 SQL。"
    claim = {
        "education": {"status": "pass", "evidence": "本科美术专业"},
        "travel": {"status": "unknown", "evidence": ""},
        "criteria": {
            name: {"level": 2, "evidence": "SQL"}
            for name in (
                "data_implementation",
                "delivery",
                "sql",
                "coding_logic",
                "modeling",
                "preferred",
            )
        },
    }
    result = score_candidate("full_resume", text, "complete", claim)
    assert result["decision"] == "review"
    assert result["eligible"] is False


def test_precontact_does_not_contact_when_sql_is_reused_as_implementation():
    claim = judgement(
        data_implementation={"level": 2, "evidence": "SQL"},
        delivery={"level": 2, "evidence": "SQL"},
    )
    result = score_candidate("precontact", TEXT, "partial", claim)
    assert result["decision"] == "review"
    assert result["eligible"] is False
