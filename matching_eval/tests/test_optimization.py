import pytest
from recruitment_app.generic_scoring import score_generic, validate_scoring_config


def test_configurable_scores_share_scale_and_coverages():
    rubric={'criteria':[{'key':'core','name':'职责','category':'core'},
                        {'key':'skill','name':'技能','category':'skill'}],'requirements':[]}
    judgement={'claims':{'core':{'status':'known','match':100,'strength':3,'evidence':'完成交付'},
                         'skill':{'status':'unknown','match':None,'strength':0,'evidence':''}},
               'requirements':{},'reason':'完成交付，技能证据不足'}
    config={'weights':{'core':50,'skill':40,'bonus':10},'unknown_prior':45,
            'coarse_coverage':20,'fine_coverage':60}
    a=score_generic(rubric,'完成交付',judgement,'precontact','partial',50,config=config)
    b=score_generic(rubric,'完成交付',judgement,'full_resume','complete',75,config=config)
    assert a['score']==b['score']==75.6
    assert a['decision']=='contact'
    assert b['decision']=='review'


@pytest.mark.parametrize('config', [
    {'weights':{'core':100,'skill':-10,'bonus':10}},
    {'unknown_prior':float('nan')}, {'fine_coverage':101},
])
def test_invalid_configuration(config):
    with pytest.raises(ValueError):
        validate_scoring_config(config)


def test_pipeline_counts_coarse_false_negatives():
    from matching_eval.optimize_screening import metrics
    rows=[{'pair_id':'a','job_id':'j','label_3':2,'score':90},
          {'pair_id':'b','job_id':'j','label_3':1,'score':65},
          {'pair_id':'c','job_id':'j','label_3':0,'score':20}]
    result=metrics(rows,[False,True,False],[True,False,False],[80,60,20])
    assert result['pipeline']['recall']==0
    assert result['fine']['precision'] is None
    assert result['coarse']['recall']==.5
    assert result['coarse_high_fit_yield']==0


def test_holdout_requires_frozen_config(tmp_path):
    from matching_eval.optimize_screening import authorize_test
    with pytest.raises(ValueError):
        authorize_test(tmp_path,{'weights':{}},'data')


def test_artifact_ledger_rejects_modified_success(tmp_path, monkeypatch):
    import matching_eval.optimize_screening as evaluation
    monkeypatch.setattr(evaluation,'OUT',tmp_path)
    artifact=tmp_path/'evidence.json'
    artifact.write_text('original',encoding='utf-8')
    ledger={'evidence.json':evaluation.sha('original')}
    evaluation.verify_artifact_ledger(ledger)
    artifact.write_text('changed',encoding='utf-8')
    with pytest.raises(ValueError,match='changed'):
        evaluation.verify_artifact_ledger(ledger)


def test_frozen_implementation_mismatch_blocks_test(tmp_path, monkeypatch):
    import matching_eval.optimize_screening as evaluation
    monkeypatch.setattr(evaluation,'implementation_hashes',lambda:{'code':'new'})
    evaluation.write_json(tmp_path/'frozen_config.json',
        {'config':{},'data_hash':'same','implementation_hashes':{'code':'old'}})
    with pytest.raises(ValueError,match='Implementation changed'):
        evaluation.authorize_test(tmp_path,{},'same')
    assert not (tmp_path/'test_opened.json').exists()


def test_extractor_tag_rejects_changed_source(tmp_path, monkeypatch):
    import matching_eval.optimize_screening as evaluation
    monkeypatch.setattr(evaluation,'OUT',tmp_path/'output')
    monkeypatch.setattr(evaluation,'ROOT',tmp_path)
    for name in ('generic_model.py','core.py','llm.py'):
        p=tmp_path/'recruitment_app'/name
        p.parent.mkdir(exist_ok=True)
        p.write_text('original',encoding='utf-8')
    evaluation.ensure_extractor_identity.cache_clear()
    evaluation.ensure_extractor_identity('baseline')
    (tmp_path/'recruitment_app/core.py').write_text('modified',encoding='utf-8')
    evaluation.ensure_extractor_identity.cache_clear()
    with pytest.raises(ValueError,match='existing tag'):
        evaluation.ensure_extractor_identity('baseline')
    evaluation.ensure_extractor_identity.cache_clear()


def test_recovered_history_bound_to_original(tmp_path, monkeypatch):
    import matching_eval.optimize_screening as evaluation
    monkeypatch.setattr(evaluation,'OUT',tmp_path)
    case={'id':'R002','text':'watermark'}
    path=tmp_path/'history/recovered/H_R002.json'
    evaluation.write_json(path,{'full':'恢复正文','original_extraction_sha256':evaluation.sha('watermark'),
                                'sha256':evaluation.sha('恢复正文')})
    assert evaluation.history_full(case)=='恢复正文'
    with pytest.raises(ValueError):
        evaluation.history_full({'id':'R002','text':'changed'})


def test_failed_extraction_is_explicit_review_not_success(tmp_path):
    import matching_eval.optimize_screening as evaluation
    path=tmp_path/'evidence.json'
    evaluation.write_json(path.with_suffix('.error.json'),{'errors':['invalid quote']})
    result=evaluation.cached_evidence(path)
    assert result['extraction_error']==['invalid quote']
    assert result['claims']=={}
    with pytest.raises(ValueError):
        evaluation.cached_evidence(path,strict=True)


def test_final_report_requires_strict_evidence(monkeypatch):
    import matching_eval.optimize_screening as evaluation
    observed=[]
    def capture(*args,**kwargs):
        observed.append(kwargs.get('strict'))
        raise ValueError('stop before report')
    monkeypatch.setattr(evaluation,'compact',capture)
    with pytest.raises(ValueError,match='stop before report'):
        evaluation.report_rows([],{}, {'prompt_tag':'baseline','weights':{},'unknown_prior':35},'final_history')
    assert observed==[True]


def test_reweighting_matches_full_scorer():
    from matching_eval.optimize_screening import reweight_assessment
    rubric={'criteria':[{'key':'task','name':'任务','category':'core'},
                        {'key':'skill','name':'技能','category':'skill'}],'requirements':[]}
    judgement={'claims':{'task':{'status':'known','match':100,'strength':3,'evidence':'完成交付'},
                         'skill':{'status':'unknown','match':None,'strength':0,'evidence':''}},
               'requirements':{},'reason':'任务已证实，技能未提及'}
    zero_gates={'coarse_coverage':0,'fine_coverage':0}
    base=score_generic(rubric,'完成交付',judgement,'full_resume','complete',50,config=zero_gates)
    for prior in (25,35,45):
        weights={'core':50,'skill':40,'bonus':10}
        expected=score_generic(rubric,'完成交付',judgement,'full_resume','complete',50,
                               config={**zero_gates,'weights':weights,'unknown_prior':prior})
        assert reweight_assessment(rubric,base,weights,prior)==(
            expected['score'],expected['evidence_coverage'],expected['threshold_eligible'])
