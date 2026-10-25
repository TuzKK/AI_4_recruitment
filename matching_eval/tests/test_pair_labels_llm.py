import math
import pytest
from matching_eval.pair_labels_llm import label_for_score, validate_labels, model_payload, restore_quotes


@pytest.mark.parametrize('score,label', [(0,0),(49.9,0),(50,1),(74.9,1),(75,2),(100,2)])
def test_stage_boundaries(score,label):
    assert label_for_score(score) == label


@pytest.mark.parametrize('score', [True, -1, 101, math.nan, math.inf, '75'])
def test_invalid_scores(score):
    with pytest.raises(ValueError):
        label_for_score(score)


def fixture():
    payload={'resume_full':'熟悉SQL，负责数据清洗和报表。',
             'resume_short':'熟悉SQL，负责数据清洗。',
             'pairs':[{'pair_id':'G1_J1','job_text':'要求熟悉SQL及数据清洗。'}]}
    item={'pair_id':'G1_J1','label_3':2,'score':80.5,'hard_requirements':'met',
          'hard_negative':False,'resume_quote':'负责数据清洗','job_quote':'要求熟悉SQL',
          'reason':'SQL和数据清洗与岗位要求一致。','gaps':[]}
    return payload,{'labels':[item]}


def test_valid_label_and_derived_decisions():
    payload,result=fixture()
    item=validate_labels(result,payload)[0]
    assert item['coarse_pass'] and item['fine_pass']


@pytest.mark.parametrize('change', [
    {'label_3':0}, {'hard_requirements':'failed'}, {'hard_requirements':'unknown'},
    {'resume_quote':'负责机器学习训练'}, {'job_quote':'要求Python'}, {'hard_negative':True},
])
def test_inconsistent_or_fabricated_labels_rejected(change):
    payload,result=fixture()
    result['labels'][0].update(change)
    with pytest.raises(ValueError):
        validate_labels(result,payload)


def test_duplicate_pair_rejected():
    payload,result=fixture()
    result['labels'] *= 2
    with pytest.raises(ValueError):
        validate_labels(result,payload)


def test_restore_source_quotes_and_reject_invalid_ids():
    payload,result=fixture()
    numbered=model_payload(payload)
    item=result['labels'][0]
    item.update(resume_quote_id=1,job_quote_id=1,hard_failure_quote_id=0)
    restored=restore_quotes(result,numbered)
    assert restored['labels'][0]['resume_quote'] in payload['resume_full']
    validate_labels(restored,payload)
    item['resume_quote_id']=999
    with pytest.raises(ValueError):
        validate_labels(restore_quotes(result,numbered),payload)


def test_explicit_failure_requires_quoted_source():
    payload,result=fixture()
    result['labels'][0].update(label_3=0,score=40,hard_requirements='failed')
    with pytest.raises(ValueError):
        validate_labels(result,payload)
