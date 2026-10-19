import pytest


def score(stage='precontact', claims=None, requirements=None, threshold=None):
    from recruitment_app.generic_scoring import score_generic
    rubric = {'criteria': [
        {'key': 'delivery', 'name': '核心职责', 'category': 'core'},
        {'key': 'tool', 'name': '必备工具', 'category': 'skill'},
        {'key': 'extra', 'name': '优先条件', 'category': 'bonus'}],
        'requirements': [{'key': 'degree', 'name': '学历', 'stage': 'resume'}]}
    judgement = {'claims': claims or {
        'delivery': {'status': 'known', 'match': 75, 'strength': 3, 'evidence': '负责实施'},
        'tool': {'status': 'known', 'match': 100, 'strength': 3, 'evidence': '使用工具'},
        'extra': {'status': 'unknown', 'match': None, 'strength': 0, 'evidence': ''}},
        'requirements': requirements or {'degree': {'status': 'met', 'evidence': '本科'}},
        'reason': '核心职责有证据，优先条件未知。'}
    return score_generic(rubric, '负责实施；使用工具；本科', judgement, stage,
                         'partial' if stage == 'precontact' else 'complete',
                         threshold if threshold is not None else (50 if stage == 'precontact' else 75))


def test_identical_evidence_has_identical_scores_across_stages():
    a, b = score(), score('full_resume')
    assert a['score'] == b['score'] == 78.5
    assert a['evidence_coverage'] == b['evidence_coverage'] == 90
    assert a['decision'] == 'contact' and b['decision'] == 'high_match'


def test_unknown_not_misrepresented_as_failure():
    result = score(requirements={'degree': {'status': 'unknown', 'evidence': ''}})
    assert result['decision'] == 'contact'
    assert score('full_resume', requirements={'degree': {'status': 'unknown', 'evidence': ''}})['decision'] == 'review'


def test_explicit_hard_failure_blocks_even_high_scores():
    assert score(requirements={'degree': {'status': 'failed', 'evidence': '本科'}})['decision'] == 'reject'


def test_only_keywords_cannot_pass_practical_gate():
    claims = {key: {'status': 'known', 'match': 100, 'strength': 1, 'evidence': '使用工具'}
              for key in ('delivery', 'tool', 'extra')}
    result = score(claims=claims, threshold=10)
    assert result['score'] == 50
    assert result['decision'] == 'hold'


def test_no_evidence_is_not_a_numeric_score():
    claims = {key: {'status': 'unknown', 'match': None, 'strength': 0, 'evidence': ''}
              for key in ('delivery', 'tool', 'extra')}
    result = score(claims=claims)
    assert result['score'] is None and result['evidence_coverage'] == 0
    assert result['decision'] == 'hold'


def test_invalid_citation_cannot_be_used_to_pass():
    claims = {key: {'status': 'known', 'match': 100, 'strength': 3, 'evidence': '编造经历'}
              for key in ('delivery', 'tool', 'extra')}
    result = score(claims=claims)
    assert result['issues'] and result['decision'] == 'review'


def test_weight_redistribution_without_bonus():
    from recruitment_app.generic_scoring import criterion_weights
    weights = criterion_weights([{'key': 'a', 'category': 'core'}, {'key': 'b', 'category': 'skill'}])
    assert weights['a'] == pytest.approx(200 / 3)
    assert weights['b'] == pytest.approx(100 / 3)


def test_explicit_conversation_failure_blocks_both_stages():
    from recruitment_app.generic_scoring import score_generic
    rubric={'criteria':[{'key':'task','name':'任务','category':'core'}],
            'requirements':[{'key':'travel','name':'出差','stage':'conversation'}]}
    judgement={'claims':{'task':{'status':'known','match':100,'strength':3,'evidence':'完成项目'}},
               'requirements':{'travel':{'status':'failed','evidence':'不能出差'}},'reason':'无法出差'}
    for stage, expected in [('precontact','reject'),('full_resume','not_fit')]:
        assert score_generic(rubric,'完成项目；不能出差',judgement,stage,'complete',50)['decision']==expected


def test_versions_are_persisted_and_invalid_versions_rejected(tmp_path):
    from recruitment_app.runner import RunStore
    from .test_core import JOB
    store=RunStore(tmp_path)
    old=store.create(JOB,1,30,75,'你好')
    new=store.create(JOB,1,50,75,'你好',scoring_version='generic-v1')
    assert store.get(old)['scoring_version']=='legacy-v3'
    assert store.get(new)['scoring_version']=='generic-v1'
    with pytest.raises(ValueError):
        store.create(JOB,1,50,75,'你好',scoring_version='bad')
