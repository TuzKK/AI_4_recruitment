"""Offline comparison uses the same hosted LLM evidence for both scorers."""

import json

from recruitment_app.benchmark import benchmark_full_resumes

from .test_core import JOB, RUBRIC, judgement


def test_benchmark_keeps_private_and_unrelated_negatives_separate():
    class Model:
        def __init__(self):
            self.calls = []

        def rubric(self, job):
            assert job == JOB
            return RUBRIC

        def evidence(self, stage, rubric, text):
            self.calls.append((stage, text))
            if "SQL" in text:
                return judgement()
            return {"claims": {"delivery": {"level": 0, "evidence": ""},
                               "sql": {"level": 0, "evidence": ""}},
                    "requirements": {"degree": {"status": "unknown", "evidence": ""}}}

    cases = [
        {"id": "A001", "label": "high_match", "group": "private", "text": "负责数据接入；熟悉 SQL；本科毕业"},
        {"id": "R001", "label": "rejected", "group": "private", "text": "平面设计师"},
        {"id": "N001", "label": "rejected", "group": "external_negative", "text": "临床护士"},
    ]
    model = Model()
    report = benchmark_full_resumes(JOB, cases, model, threshold=75)
    assert len(model.calls) == 3
    assert report["private"]["legacy"]["tp"] == 1
    assert report["private"]["shadow"]["tp"] == 1
    assert report["external_negative"]["shadow_false_positives"] == 0
    assert "临床护士" not in json.dumps(report, ensure_ascii=False)
