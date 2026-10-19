"""The new matcher is observable without changing the live contact decision."""

from recruitment_app.shadow_matching import ShadowMatcher

from .test_core import JOB, RUBRIC, FakeBoss, FakeModel
from recruitment_app.runner import RunStore, run_pipeline


def test_alias_and_whole_skill_matching():
    matcher = ShadowMatcher()
    judgement = {"claims": {
        "delivery": {"level": 2, "evidence": "数据接入"},
        "sql": {"level": 2, "evidence": "SQL"},
    }, "requirements": {"degree": {"status": "met", "evidence": "本科毕业"}}}
    result = matcher.score(RUBRIC, "负责数据接入；熟悉 SQL；本科毕业", judgement,
                           "full_resume", "complete", 75)
    assert result["engine"] == "recruiter_pro_rule_llm_v2"
    assert result["llm_evidence_score"] == 100
    assert "semantic_similarity" not in result
    assert "SQL" in result["matched_skills"]
    assert result["score"] >= 75
    assert result["decision"] == "high_match"


def test_java_does_not_match_javascript():
    matcher = ShadowMatcher()
    assert matcher.skill_matches("熟悉 JavaScript", "仅使用 Java")["matched"] == []


def test_shadow_score_does_not_change_greeting_decision(tmp_path):
    class RejectingShadow:
        def score(self, *_args):
            return {"score": 0, "decision": "not_fit", "engine": "test"}

    store = RunStore(tmp_path)
    boss = FakeBoss()
    run_id = store.create(JOB, 1, 30, 75, "你好")
    run_pipeline(store, run_id, FakeModel(), boss, shadow=RejectingShadow())
    candidate = store.get(run_id)["candidates"]["id-1"]
    assert candidate["shadow_fine"]["score"] == 0
    assert candidate["fine"]["decision"] == "high_match"
    assert boss.greeted == ["id-1"]
