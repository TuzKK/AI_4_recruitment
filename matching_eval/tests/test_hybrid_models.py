from matching_eval import optimize_screening as opt


def test_hybrid_reuses_plus_rubrics_and_fine_but_not_coarse():
    tag = 'evidence-v3-hybrid'
    assert opt.rubric_path('job', tag) == opt.rubric_path('job', 'evidence-v3')
    assert opt.evidence_path('job', {}, 'text', 'full_resume', tag) == opt.evidence_path(
        'job', {}, 'text', 'full_resume', 'evidence-v3')
    assert opt.evidence_path('job', {}, 'text', 'precontact', tag) != opt.evidence_path(
        'job', {}, 'text', 'precontact', 'evidence-v3')


def test_stage_model_routing(monkeypatch):
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'test')
    assert opt.make_model('evidence-v3-hybrid', 'precontact').model == 'qwen-flash'
    assert opt.make_model('evidence-v3-hybrid', 'full_resume').model == 'qwen-plus'
    assert opt.make_model('evidence-v3-hybrid').model == 'qwen-plus'


def test_runtime_routing_does_not_mutate_shared_model(monkeypatch):
    from recruitment_app.hybrid_model import HybridGenericJobModel
    from recruitment_app.generic_model import GenericJobModel
    monkeypatch.setattr(GenericJobModel, 'assess', lambda self, *args: {'model': self.model, 'score': 80})
    model = HybridGenericJobModel('test', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
    assert model.assess('precontact', {}, 'text', 'partial', 50)['model'] == 'qwen-flash'
    assert model.assess('full_resume', {}, 'text', 'complete', 75)['model'] == 'qwen-plus'
    assert model.model == 'qwen-plus'


def test_flash_flat_fields_are_wrapped_without_inventing_evidence():
    from matching_eval.flash_format import normalize_fields
    rubric = {'criteria': [{'key': 'c'}], 'requirements': [{'key': 'r'}]}
    raw = {'c': {'status': 'unknown'}, 'r': {'status': 'unknown'}, 'reason': 'x'}
    fixed = normalize_fields(raw, rubric)
    assert fixed == {'claims': {'c': raw['c']}, 'requirements': {'r': raw['r']}, 'reason': 'x'}
    assert normalize_fields({'reason': 'x'}, rubric) == {'reason': 'x'}


def test_local_evaluation_cache_uses_stage_model(tmp_path, monkeypatch):
    from recruitment_app.hybrid_model import HybridJobModel
    from recruitment_app.local_eval import _cached_judgement
    from recruitment_app.llm import JobModel
    calls = []
    monkeypatch.setattr(JobModel, 'detailed_evidence',
                        lambda self, *args: calls.append(self.model) or {'claims': {}})
    model = HybridJobModel('test', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
    _cached_judgement(model, tmp_path, {}, 'precontact', 'text')
    plus = JobModel('test', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
    _cached_judgement(plus, tmp_path, {}, 'precontact', 'text')
    assert calls == ['qwen-flash', 'qwen-plus']


def test_reviewed_profile_has_separate_coarse_cache_and_reuses_fine():
    tag = 'evidence-v3-hybrid-reviewed1'
    assert opt.evidence_path('j', {}, 't', 'precontact', tag) != opt.evidence_path(
        'j', {}, 't', 'precontact', 'evidence-v3-hybrid')
    assert opt.evidence_path('j', {}, 't', 'full_resume', tag) == opt.evidence_path(
        'j', {}, 't', 'full_resume', 'evidence-v3')


def test_review_boundary_is_conservative():
    from recruitment_app.hybrid_model import needs_plus_review
    assert needs_plus_review({'score': 49, 'issues': []}, 50)
    assert needs_plus_review({'score': 80, 'issues': ['bad quote']}, 50)
    assert not needs_plus_review({'score': 20, 'issues': []}, 50)


def test_runtime_format_exception_falls_back_to_plus(monkeypatch):
    from recruitment_app.hybrid_model import HybridJobModel
    from recruitment_app.llm import JobModel
    def assess(self, *args):
        if self.model == 'qwen-flash':
            raise ValueError('Invalid JSON structure')
        return {'score': 80}
    monkeypatch.setattr(JobModel, 'assess', assess)
    model = HybridJobModel('test', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
    assert model.assess('precontact', {}, 'text', 'partial', 50)['reviewed_from'] == 'qwen-flash'


def test_combined_failure_is_retained_for_aggregation(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr(opt, 'OUT', tmp_path)
    monkeypatch.setattr(opt, 'ensure_extractor_identity', lambda tag: None)
    monkeypatch.setattr(opt.time, 'sleep', lambda seconds: None)
    class InvalidModel:
        def evidence_generic(self, *args):
            raise ValueError('Invalid evidence')
    monkeypatch.setattr(opt, 'make_model', lambda *args: InvalidModel())
    tag = 'evidence-v3-hybrid-reviewed2'
    with pytest.raises(ValueError):
        opt.get_evidence('job', {}, 'text', 'precontact', tag)
    path = opt.evidence_path('job', {}, 'text', 'precontact', tag)
    assert opt.cached_evidence(path)['extraction_error']


def test_adapter_cache_is_separate_from_original_flash():
    assert opt.evidence_path('j', {}, 't', 'precontact', 'evidence-v3-hybrid-format1') != (
        opt.evidence_path('j', {}, 't', 'precontact', 'evidence-v3-hybrid'))
