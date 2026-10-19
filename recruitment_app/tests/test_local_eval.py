"""Local corpus evaluation never calls the BOSS connector."""

from pathlib import Path

from recruitment_app.local_eval import (evaluate_local_cases, load_local_cases, recommend_threshold,
                                        make_proxy_card, score_detailed, summarize_tiers)

from .test_core import RUBRIC


def test_proxy_card_is_short_and_label_blind():
    text = "求职意向：数据分析师\n教育经历：计算机本科\n工作经历：使用 SQL 和 Python 处理数据。" * 12
    card = make_proxy_card(text)
    assert len(card) <= 200
    assert "数据分析师" in card
    assert "SQL" in card
    assert "strong_match" not in card


def test_invalid_citations_are_repaired_once_and_cached(tmp_path):
    from recruitment_app.local_eval import repair_judgement
    class Model:
        model = "fake-repair"
        calls = 0
        def repair_detailed_evidence(self, stage, rubric, text, judgement, issues):
            self.calls += 1
            assert issues and text == "负责数据接入；本科毕业"
            return {"corrected": True}
    model = Model()
    args = (model, tmp_path, RUBRIC, "full_resume", "负责数据接入；本科毕业", {"claims": {}}, ["invalid citation"])
    assert repair_judgement(*args) == {"corrected": True}
    assert repair_judgement(*args) == {"corrected": True}
    assert model.calls == 1


def test_proxy_card_keeps_late_technical_evidence_after_empty_heading():
    text = "求职意向：数据工程师\n教育经历：信息工程本科\n工作经历\n公司介绍\n专业技能\n熟悉 SQL 数据查询，使用 Python 编写数据清洗脚本。\n负责字段映射与实例导入。"
    text = text.replace("专业技能", "\n".join(["公司业务介绍与团队沟通"] * 12) + "\n专业技能")
    card = make_proxy_card(text)
    assert "SQL" in card and "Python" in card
    assert "字段映射" in card
    assert len(card) <= 200


def test_detailed_score_requires_supported_context_and_reason():
    text = "负责数据接入，使用 SQL 清洗数据，本科毕业。"
    judgement = {
        "claims": {
            "delivery": {"level": 4, "fit": 4, "evidence": "负责数据接入"},
            "sql": {"level": 3, "fit": 4, "evidence": "使用 SQL 清洗数据"},
        },
        "requirements": {"degree": {"status": "met", "evidence": "本科毕业"}},
        "reason": "有数据接入和 SQL 清洗经验，符合主要技术要求。",
        "gaps": [],
    }
    result = score_detailed(RUBRIC, text, judgement, "full_resume", "complete", 75)
    assert result["score"] == 90.0
    assert result["decision"] == "high_match"
    assert result["threshold_eligible"] is True
    assert "数据接入" in result["reason"]
    judgement["reason"] = "有数据接入和 SQL 清洗经验。" * 20
    verbose = score_detailed(RUBRIC, text, judgement, "full_resume", "complete", 75)
    assert verbose["decision"] == "high_match"
    assert len(verbose["reason"]) <= 160
    judgement["claims"]["sql"]["evidence"] = "不存在的经历"
    invalid = score_detailed(RUBRIC, text, judgement, "full_resume", "complete", 75)
    assert invalid["decision"] == "review"
    assert invalid["score"] < result["score"]


def test_domain_gap_places_hard_negative_above_unrelated():
    hard = score_detailed(RUBRIC, "实施数据接入，SQL 只略懂", {
        "claims": {"delivery": {"level": 3, "fit": 4, "evidence": "实施数据接入"},
                   "sql": {"level": 1, "fit": 2, "evidence": "SQL 只略懂"}},
        "requirements": {"degree": {"status": "unknown", "evidence": ""}},
        "reason": "有数据接入经历，但 SQL 证据较弱。", "gaps": ["SQL"],
    }, "full_resume", "complete", 75)
    unrelated = score_detailed(RUBRIC, "负责体育赛事推广及客户沟通", {
        "claims": {"delivery": {"level": 0, "fit": 0, "evidence": ""},
                   "sql": {"level": 0, "fit": 0, "evidence": ""}},
        "requirements": {"degree": {"status": "unknown", "evidence": ""}},
        "reason": "主要是体育推广，缺少数据实施与 SQL 证据。", "gaps": ["数据接入", "SQL"],
    }, "full_resume", "complete", 75)
    assert hard["score"] > unrelated["score"] + 10
    assert unrelated["decision"] == "not_fit"


def test_partial_coarse_card_accepts_one_relevant_skill_without_inventing_core():
    j = {"claims": {"delivery": {"level": 0, "fit": 0, "evidence": ""},
                    "sql": {"level": 3, "fit": 4, "evidence": "使用 SQL 清洗数据"}},
         "requirements": {"degree": {"status": "unknown", "evidence": ""}},
         "reason": "有 SQL 清洗经验，其余经历待完整简历核实。", "gaps": []}
    result = score_detailed(RUBRIC, "使用 SQL 清洗数据", j, "precontact", "partial", 20)
    assert result["decision"] == "contact"
    assert result["threshold_eligible"]
    assert result["breakdown"]["delivery"] == 0


def test_related_engineering_major_is_verified_from_education_evidence():
    import copy
    rubric = copy.deepcopy(RUBRIC)
    rubric["requirements"].append({"key": "major", "name": "相关专业", "stage": "resume",
                                   "jd_quote": "计算机、软件工程等相关专业"})
    text = "负责数据接入，使用 SQL 清洗数据。本科，专业：通信工程。"
    j = {"claims": {"delivery": {"level": 4, "fit": 4, "evidence": "负责数据接入"},
                    "sql": {"level": 4, "fit": 4, "evidence": "使用 SQL 清洗数据"}},
         "requirements": {"degree": {"status": "met", "evidence": "本科，专业：通信工程"},
                          "major": {"status": "unknown", "evidence": ""}},
         "reason": "有数据接入和SQL实践，专业关系需核验。", "gaps": []}
    result = score_detailed(rubric, text, j, "full_resume", "complete", 75)
    assert result["decision"] == "high_match"
    assert result["rule_adjustments"]
    j["requirements"]["degree"]["evidence"] = "本科，专业：市场营销"
    result = score_detailed(rubric, text.replace("通信工程", "市场营销"), j, "full_resume", "complete", 75)
    assert result["decision"] == "review"


def test_skill_list_does_not_receive_delivery_evidence_strength():
    j = {"claims": {"delivery": {"level": 0, "fit": 0, "evidence": ""},
                    "sql": {"level": 4, "fit": 4, "evidence": "熟悉 SQL"}},
         "requirements": {"degree": {"status": "met", "evidence": "本科毕业"}},
         "reason": "仅有SQL技能自述，没有实践证据。", "gaps": []}
    result = score_detailed(RUBRIC, "熟悉 SQL，本科毕业", j, "full_resume", "complete", 75)
    assert result["levels"]["sql"]["level"] == 1
    assert result["score"] == 10


def test_ontology_profile_requires_all_four_competencies_for_high_match():
    rubric = {"criteria": [
        {"key": "modeling", "name": "建模概念", "category": "core", "weight": 25, "jd_quote": "了解本体对象属性关系"},
        {"key": "sql", "name": "SQL", "category": "skill", "weight": 25, "jd_quote": "熟悉 SQL"},
        {"key": "code", "name": "编程", "category": "skill", "weight": 25, "jd_quote": "熟悉 Python 或 JavaScript"},
        {"key": "delivery", "name": "实施交付", "category": "core", "weight": 25, "jd_quote": "具备系统实施与项目交付经验"}],
        "requirements": []}
    text = "参与对象关系建模；使用 SQL 清洗数据；Python；负责系统实施与交付。"
    j = {"claims": {
        "modeling": {"level": 2, "fit": 3, "evidence": "参与对象关系建模"},
        "sql": {"level": 2, "fit": 3, "evidence": "使用 SQL 清洗数据"},
        "code": {"level": 1, "fit": 2, "evidence": "Python"},
        "delivery": {"level": 3, "fit": 4, "evidence": "负责系统实施与交付"}},
        "requirements": {}, "reason": "四项基础能力有证据，编程深度较弱。", "gaps": []}
    result = score_detailed(rubric, text, j, "full_resume", "complete", 75)
    assert result["decision"] == "high_match"
    assert result["competency_gates"]["sql"]
    j["claims"]["sql"] = {"level": 0, "fit": 0, "evidence": ""}
    result = score_detailed(rubric, text, j, "full_resume", "complete", 10)
    assert result["decision"] != "high_match"
    assert 20 <= result["score"] < 50
    for key in j["claims"]:
        j["claims"][key] = {"level": 0, "fit": 0, "evidence": ""}
    related = score_detailed(rubric, "负责 Java 软件开发", j, "full_resume", "complete", 75)
    distant = score_detailed(rubric, "体育教练，未使用 SQL 或 Python，不从事软件开发。", j, "full_resume", "complete", 75)
    assert related["score"] >= 20
    assert distant["score"] < 20
    from recruitment_app.local_eval import _has_technical_context
    assert not _has_technical_context("未从事 SQL 查询、Python/JavaScript 开发、数据平台实施或程序开发。")
    assert _has_technical_context("负责数据清洗，优化数据处理流程。")


def test_tier_summary_reports_order_and_exceptions():
    rows = [
        {"id": "s", "tier": "strong_match", "fine": {"score": 85}},
        {"id": "b", "tier": "borderline", "fine": {"score": 68}},
        {"id": "h", "tier": "hard_negative", "fine": {"score": 48}},
        {"id": "u", "tier": "unrelated", "fine": {"score": 9}},
        {"id": "r", "tier": "private_rejected", "fine": {"score": 22}},
    ]
    report = summarize_tiers(rows)
    assert report["ordered_medians"] is True
    assert report["hard_unrelated_margin"] == 39
    assert report["unscored"] == []
    assert report["quantiles"]["hard_negative"]["p10"] == 48
    assert report["adjacent_band_gaps"]["strong_match>borderline"] == 17
    assert report["inversion_ids"] == []


def test_pipeline_metrics_count_a_positive_lost_in_coarse_as_false_negative():
    from recruitment_app.local_eval import pipeline_metrics
    rows = [
        {"id": "positive", "expected_fine": "pass", "coarse": {"decision": "hold"}, "fine": {"decision": "high_match"}},
        {"id": "negative", "expected_fine": "reject", "coarse": {"decision": "contact"}, "fine": {"decision": "not_fit"}}]
    result = pipeline_metrics(rows)
    assert result["fn"] == 1 and result["tn"] == 1
    assert result["accuracy"] == .5
    assert result["mismatch_ids"] == ["positive"]


def test_local_corpus_has_reviewed_sources_and_domain_stress_cases():
    root = Path(__file__).parents[2] / "Samples_for_optimization"
    cases = load_local_cases(root)
    assert len(cases) == 120
    assert len({case["id"] for case in cases}) == 120
    assert {case["id"] for case in cases if case["group"] == "stress"} == {"T001", "T002"}
    assert next(case for case in cases if case["id"] == "S022")["tier"] == "strong_match"
    assert next(case for case in cases if case["id"] == "S024")["tier"] == "hard_negative"
    assert all(len(make_proxy_card(case["text"])) <= 200 for case in cases)
    assert "SQL" in make_proxy_card(next(case for case in cases if case["id"] == "S003")["text"])
    assert "孙飞" not in make_proxy_card(next(case for case in cases if case["id"] == "S022")["text"])


def test_local_evaluation_scores_both_stages_and_caches_api_calls(tmp_path):
    class Model:
        model = "fake-qwen"

        def __init__(self):
            self.calls = 0
            self.rubric_calls = 0
            self.inputs = []

        def rubric(self, job):
            self.rubric_calls += 1
            return RUBRIC

        def detailed_evidence(self, stage, rubric, text):
            self.calls += 1
            self.inputs.append(text)
            return {"claims": {
                "delivery": {"level": 4 if "数据接入" in text else 0,
                             "fit": 4 if "数据接入" in text else 0,
                             "evidence": "数据接入" if "数据接入" in text else ""},
                "sql": {"level": 4 if "SQL" in text else 0,
                        "fit": 4 if "SQL" in text else 0,
                        "evidence": "SQL" if "SQL" in text else ""}},
                "requirements": {"degree": {"status": "met" if "本科" in text else "unknown",
                                            "evidence": "本科" if "本科" in text else ""}},
                "reason": "有数据接入和 SQL 实操。" if "SQL" in text else "缺少岗位技术证据。",
                "gaps": []}

    cases = [{"id": "x", "tier": "strong_match", "group": "synthetic",
              "expected_coarse": "pass", "expected_fine": "pass",
              "text": "求职意向：数据工程师。负责数据接入和 SQL 查询，本科毕业。电话 13912345678 邮箱 test@example.com"}]
    model = Model()
    first = evaluate_local_cases("招聘数据工程师。负责数据接入和 SQL 查询。本科以上。",
                                 cases, model, tmp_path, coarse_threshold=30, fine_threshold=75)
    second = evaluate_local_cases("招聘数据工程师。负责数据接入和 SQL 查询。本科以上。",
                                  cases, model, tmp_path, coarse_threshold=30, fine_threshold=75)
    assert model.calls == 2
    assert model.rubric_calls == 1
    assert first["rows"][0]["coarse"]["decision"] == "contact"
    assert first["rows"][0]["fine"]["decision"] == "high_match"
    assert first["rows"][0]["show_in_web"] is True
    assert second["rows"][0]["fine"]["reason"]
    assert "text" not in first["rows"][0]
    assert first["status"] == "complete"
    assert all("13912345678" not in item and "test@example.com" not in item for item in model.inputs)


def test_local_evaluation_stops_on_invalid_api_key(tmp_path):
    import httpx
    import pytest

    class Model:
        model = "fake-qwen"

        def rubric(self, job):
            return RUBRIC

        def detailed_evidence(self, stage, rubric, text):
            response = httpx.Response(401, request=httpx.Request("POST", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"))
            raise httpx.HTTPStatusError("invalid key", request=response.request, response=response)

    case = {"id": "x", "tier": "strong_match", "group": "synthetic",
            "expected_coarse": "pass", "expected_fine": "pass", "text": "负责数据接入和 SQL 查询，本科毕业。"}
    with pytest.raises(httpx.HTTPStatusError):
        evaluate_local_cases("招聘数据工程师。负责数据接入和 SQL 查询。本科以上。",
                             [case], Model(), tmp_path)


def test_cached_judgement_retries_rate_limit(tmp_path, monkeypatch):
    import httpx
    from recruitment_app.local_eval import _cached_judgement

    monkeypatch.setattr("recruitment_app.local_eval.time.sleep", lambda _: None)

    class Model:
        model = "fake-qwen"
        calls = 0

        def detailed_evidence(self, stage, rubric, text):
            self.calls += 1
            if self.calls == 1:
                response = httpx.Response(429, request=httpx.Request("POST", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"))
                raise httpx.HTTPStatusError("rate limited", request=response.request, response=response)
            return {"reason": "ok"}

    model = Model()
    assert _cached_judgement(model, tmp_path, RUBRIC, "full_resume", "数据接入")["reason"] == "ok"
    assert model.calls == 2


def test_threshold_recommendation_uses_labels_without_new_model_calls():
    rows = [
        {"id": "a", "tier": "strong_match", "expected_coarse": "pass",
         "coarse": {"score": 85, "threshold_eligible": True}},
        {"id": "b", "tier": "ordinary_negative", "expected_coarse": "reject",
         "coarse": {"score": 25, "threshold_eligible": True}},
    ]
    result = recommend_threshold(rows, "precontact")
    assert result["status"] == "exploratory"
    assert 26 <= result["threshold"] <= 85
    assert result["precision"] == result["recall"] == 1
