import json
import pytest
from matching_eval.generic_batch import binary_metrics, proxy_card
from matching_eval.generic_pairs import split_groups


def test_identical_source_resumes_never_cross_partitions():
    rows=[{'id':f'G{i}', 'text_original':'same technical experience with source evidence '*20,
           'original_sha256':str(i)} for i in range(3)]
    assigned, counts=split_groups(rows)
    assert len({r['split'] for r in assigned.values()})==1
    assert sum(counts.values())==3


def test_end_to_end_metrics_count_coarse_missed_positive():
    rows=[{'label':'pass','coarse':{'decision':'hold'},'fine':{'decision':'high_match'}},
          {'label':'reject','coarse':{'decision':'contact'},'fine':{'decision':'not_fit'}}]
    result=binary_metrics(rows)
    assert result['fn']==1 and result['tn']==1 and result['recall']==0
    assert result['precision'] is None


def test_proxy_does_not_search_for_technology_words():
    text='\n'.join(f'经历{i}：'+('项目工作'*30) for i in range(10))
    assert proxy_card(text)==proxy_card(text.replace('经历8：','SQL项目8：'))


def test_evaluation_label_read_cannot_invoke_codex_for_missing_cache(tmp_path,monkeypatch):
    import matching_eval.generic_pairs as module
    monkeypatch.setattr(module,'CORPUS',tmp_path)
    def forbidden(*args):
        raise AssertionError('评测中禁止生成标准答案')
    monkeypatch.setattr(module,'codex_json',forbidden)
    (tmp_path/'translations').mkdir()
    data={'source_selection.json':{'resumes':[{'id':'G1','text_original':'source'}]},
          'translations/G1.json':{'text_zh':'履历正文'},
          'pairs.json':{'pairs':[{'id':'G1_J1','resume_id':'G1','job_id':'J1'}]},
          'jobs.json':{'jobs':[{'id':'J1','text':'招聘要求'}]}}
    for name,value in data.items():
        (tmp_path/name).write_text(json.dumps(value),encoding='utf-8')
    with pytest.raises(ValueError,match='没有经过独立标注'):
        module.label_resume('G1',allow_create=False)
