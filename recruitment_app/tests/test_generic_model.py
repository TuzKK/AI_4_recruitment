import json
import httpx


def test_generic_api_extracts_source_spans_and_uses_fixed_weights():
    from recruitment_app.generic_model import GenericJobModel
    responses = [
        {'title': '实施工程师', 'criteria': [
            {'key': 'delivery', 'name': '实施', 'category': 'core', 'weight': 60, 'jd_quote': '负责实施'},
            {'key': 'tool', 'name': '工具', 'category': 'skill', 'weight': 40, 'jd_quote': '使用工具'}],
         'requirements': []},
        {'claims': {'delivery': {'status': 'known', 'match': 75, 'strength': 3, 'start_line': 1, 'end_line': 1},
                    'tool': {'status': 'known', 'match': 100, 'strength': 3, 'start_line': 2, 'end_line': 2}},
         'requirements': {}, 'reason': '有明确实施与工具经验。'}]
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(responses.pop(0))}}]})
    model = GenericJobModel('test', 'https://dashscope.aliyuncs.com/compatible-mode/v1', transport=httpx.MockTransport(handler))
    rubric = model.rubric('招聘实施工程师，负责实施，要求能够使用工具完成具体项目。')
    result = model.assess('full_resume', rubric, '负责实施\n使用工具', 'complete', 75)
    assert result['score'] == 83.3
    assert result['decision'] == 'high_match'
    assert result['breakdown']['delivery']['evidence'] == '负责实施'
    assert all(c['model'] == 'qwen-plus' and c['enable_thinking'] is False for c in calls)


def test_malformed_evidence_retries_then_returns_review():
    from recruitment_app.generic_model import GenericJobModel
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(200,json={'choices':[{'message':{'content':'{}'}}]})
    model=GenericJobModel('test','https://dashscope.aliyuncs.com/compatible-mode/v1',transport=httpx.MockTransport(handler))
    result=model.assess('precontact',{'criteria':[{'key':'task','name':'任务','category':'core'}],
                                      'requirements':[]},'参与项目任务','partial',50)
    assert len(calls)==2
    assert result['decision']=='review' and result['issues']


def test_rubric_cannot_add_unquoted_proof_requirements_in_name():
    from recruitment_app.generic_model import GenericJobModel
    response={'title':'实施工程师','criteria':[
        {'key':'delivery','name':'负责实施并提供外部证明','category':'core','weight':60,'jd_quote':'负责实施'},
        {'key':'tool','name':'使用工具','category':'skill','weight':40,'jd_quote':'使用工具'}],
        'requirements':[{'key':'proof','name':'必须提供平台提交记录','stage':'resume','jd_quote':'使用工具'}]}
    def handler(request):
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(response)}}]})
    model=GenericJobModel('test','https://dashscope.aliyuncs.com/compatible-mode/v1',transport=httpx.MockTransport(handler))
    rubric=model.rubric('招聘实施工程师，负责实施，要求能够使用工具完成具体项目。')
    assert rubric['criteria'][0]['name']=='负责实施'
    assert rubric['requirements'][0]['name']=='使用工具'
