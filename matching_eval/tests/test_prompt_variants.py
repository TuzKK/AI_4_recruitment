from matching_eval.screening_prompt_variants import OptimizedModel, source_segments


def test_segments_preserve_exact_source_spans():
    text='SQL 查询；Python 开发。交付验收\n支持客户'
    parts=source_segments(text)
    assert len(parts)>=3
    for start,end in parts:
        assert text[start:end].strip()


def test_single_line_resume_uses_segment_ids_not_invented_lines():
    model=OptimizedModel('test','https://dashscope.aliyuncs.com/compatible-mode/v1')
    model.variant='evidence-v1'
    model._ask=lambda system,user:{
        'claims':{'task':{'status':'known','match':100,'strength':3,'start_line':2,'end_line':2}},
        'requirements':{},'reason':'完成交付'}
    output=model.evidence_generic({},'SQL 查询；Python 开发。交付验收')
    assert output['claims']['task']['evidence']=='Python 开发。'


def test_second_variant_uses_atomic_job_quotes_and_stable_keys():
    from matching_eval.screening_prompt_v2 import AtomicJobModel
    model=AtomicJobModel('test','https://dashscope.aliyuncs.com/compatible-mode/v1')
    model._ask=lambda system,user:{'title':'工程师','criteria':[
        {'key':'duplicate','name':'开发','category':'core','weight':60,'jd_quote_id':1},
        {'key':'duplicate','name':'SQL','category':'skill','weight':40,'jd_quote_id':2}],
        'requirements':[]}
    result=model.rubric('负责系统开发和实施交付，熟悉SQL查询与数据清洗，了解Python脚本。')
    assert result['criteria'][0]['jd_quote']=='负责系统开发和实施交付，'
    assert result['criteria'][1]['jd_quote']=='熟悉SQL查询与数据清洗，'
    assert len({x['key'] for x in result['criteria']})==2


def test_unpunctuated_resume_gets_bounded_exact_spans():
    from matching_eval.screening_prompt_v3 import bounded_segments
    text=('SQL 开发 数据建模 ETL 实施 ' * 30).strip()
    spans=bounded_segments(text)
    assert len(spans)>3
    assert ''.join(text[a:b] for a,b in spans)==text
    assert all(b-a<=180 for a,b in spans)
