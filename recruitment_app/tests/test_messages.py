import json

import httpx
import pytest

from recruitment_app.llm import JobModel
from recruitment_app.runner import RunStore, run_pipeline
from .test_core import JOB, RUBRIC, FakeBoss, FakeModel


MESSAGE = ('你好，我们正在招聘数据工程师，看到你有数据接入和SQL方面的经历，想进一步了解你的项目实践。'
           '方便介绍一次你参与的数据接入项目，以及你如何使用SQL核对数据、定位并解决问题吗？期待与你交流。')


def api_model(responses, calls):
    def handler(request):
        calls.append(json.loads(request.content))
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
            'content': json.dumps(result, ensure_ascii=False)}}]})
    return JobModel('test', 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                    transport=httpx.MockTransport(handler))


class MessagingModel(FakeModel):
    model = 'qwen-plus'

    def __init__(self, responses):
        self.calls = []
        self.api = api_model(responses, self.calls)

    def _ask(self, system, user):
        return self.api._ask(system, user)


class RecordingBoss(FakeBoss):
    def send_first(self, candidate_id, message):
        self.sent.append((candidate_id, message))
        return True


def test_llm_mode_allows_empty_template_and_sends_only_reviewed_text(tmp_path):
    store, boss = RunStore(tmp_path), RecordingBoss()
    model = MessagingModel([{'message': MESSAGE}, {'approved': True, 'reason': '原文支持，问题相关'}])
    run_id = store.create(JOB, 1, 30, 75, '', message_mode='llm')
    run_pipeline(store, run_id, model, boss)
    row = store.get(run_id)['candidates']['id-1']
    assert boss.sent == [('id-1', MESSAGE)]
    assert row['outreach']['status'] == 'approved'
    assert row['outreach']['attempts'][0]['review']['approved'] is True
    assert len(model.calls) == 2
    assert model.calls[0]['messages'][0] != model.calls[1]['messages'][0]
    assert json.loads(model.calls[1]['messages'][1]['content'])['message'] == MESSAGE


def test_failed_review_rewrites_once_and_sends_replacement(tmp_path):
    store, boss = RunStore(tmp_path), RecordingBoss()
    replacement = MESSAGE.replace('期待与你交流', '方便时欢迎回复')
    model = MessagingModel([{'message': MESSAGE}, {'approved': False, 'reason': '需要修改措辞'},
                            {'message': replacement}, {'approved': True, 'reason': '符合要求'}])
    run_id = store.create(JOB, 1, 30, 75, '', message_mode='llm')
    run_pipeline(store, run_id, model, boss)
    assert boss.sent == [('id-1', replacement)]
    assert '需要修改措辞' in model.calls[2]['messages'][1]['content']


def test_two_rejections_skip_candidate_without_consuming_quota(tmp_path):
    class TwoBoss(RecordingBoss):
        def cards(self):
            return [dict(super().cards()[0], candidate_id=cid) for cid in ('id-1', 'id-2')]
    store, boss = RunStore(tmp_path), TwoBoss()
    model = MessagingModel([{'message': MESSAGE}, {'approved': False, 'reason': '无依据'},
                            {'message': MESSAGE}, {'approved': False, 'reason': '仍无依据'},
                            {'message': MESSAGE}, {'approved': True, 'reason': '符合要求'}])
    run_id = store.create(JOB, 1, 30, 75, '', message_mode='llm')
    run_pipeline(store, run_id, model, boss)
    data = store.get(run_id)
    assert boss.greeted == ['id-2']
    assert data['candidates']['id-1']['state'] == 'message_rejected'
    assert not data['candidates']['id-1'].get('greeting_attempted')
    assert data['contacted'] == 1


@pytest.mark.parametrize('review', [{'approved': 'true', 'reason': 'ok'}, {},
                                  httpx.ReadTimeout('test timeout')])
def test_reviewer_failure_pauses_without_greeting_and_can_resume(tmp_path, review):
    store, boss = RunStore(tmp_path), RecordingBoss()
    model = MessagingModel([{'message': MESSAGE}, review])
    run_id = store.create(JOB, 1, 30, 75, '', message_mode='llm')
    run_pipeline(store, run_id, model, boss)
    assert store.get(run_id)['status'] == 'paused'
    assert boss.greeted == []
    resumed = MessagingModel([{'approved': True, 'reason': '符合要求'}])
    run_pipeline(store, run_id, resumed, boss)
    assert boss.sent == [('id-1', MESSAGE)]
    assert len(resumed.calls) == 1


def test_invalid_length_is_rewritten_and_never_sent(tmp_path):
    store, boss = RunStore(tmp_path), RecordingBoss()
    model = MessagingModel([{'message': '你好'}, {'message': '仍然太短'}])
    run_id = store.create(JOB, 1, 30, 75, '', message_mode='llm')
    run_pipeline(store, run_id, model, boss)
    assert boss.greeted == []
    assert store.get(run_id)['candidates']['id-1']['outreach']['status'] == 'rejected'


def test_stop_during_review_prevents_greeting_and_resume_reuses_approval(tmp_path):
    store, boss = RunStore(tmp_path), RecordingBoss()
    run_id = store.create(JOB, 1, 30, 75, '', message_mode='llm')
    class StopModel(MessagingModel):
        def _ask(self, system, user):
            result = super()._ask(system, user)
            if 'approved' in result:
                store.update(run_id, status='stop_requested')
            return result
    model = StopModel([{'message': MESSAGE}, {'approved': True, 'reason': '符合要求'}])
    run_pipeline(store, run_id, model, boss)
    assert store.get(run_id)['status'] == 'paused'
    assert boss.greeted == []
    run_pipeline(store, run_id, MessagingModel([]), boss)
    assert boss.sent == [('id-1', MESSAGE)]


def test_changed_resume_on_resume_requires_rescoring_before_contact(tmp_path):
    store, boss = RunStore(tmp_path), RecordingBoss()
    run_id = store.create(JOB, 1, 30, 75, '', message_mode='llm')
    model = MessagingModel([{'message': MESSAGE}, httpx.ReadTimeout('timeout')])
    run_pipeline(store, run_id, model, boss)
    class ChangedBoss(RecordingBoss):
        def full_resume(self, cid):
            return dict(super().full_resume(cid), text='改为市场营销岗位的完整简历')
    changed = ChangedBoss()
    run_pipeline(store, run_id, MessagingModel([]), changed)
    assert changed.greeted == []
    assert store.get(run_id)['candidates']['id-1']['state'] == 'coarse_done'


def test_rejected_screening_never_calls_message_model(tmp_path):
    class RejectModel(MessagingModel):
        def assess(self, stage, *args):
            return {'decision': 'contact' if stage == 'precontact' else 'reject', 'score': 10,
                    'scoring_version': 'test'}
    store, boss = RunStore(tmp_path), RecordingBoss()
    run_id = store.create(JOB, 1, 30, 75, '', message_mode='llm')
    model = RejectModel([])
    run_pipeline(store, run_id, model, boss)
    assert not model.calls and not boss.greeted


def test_invalid_mode_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        RunStore(tmp_path).create(JOB, 1, 30, 75, '你好', message_mode='unknown')


def test_changed_approved_message_cannot_reuse_review():
    from recruitment_app.messages import MessageComposer
    calls = []
    model = api_model([{'message': MESSAGE}, {'approved': True, 'reason': '符合要求'},
                       {'message': MESSAGE}, {'approved': True, 'reason': '重新复核'}], calls)
    composer = MessageComposer(model)
    result = composer.prepare(JOB, '负责数据接入和SQL', [])
    result['message'] = MESSAGE.replace('SQL', 'ABC')
    renewed = composer.prepare(JOB, '负责数据接入和SQL', [], result)
    assert renewed['message'] == MESSAGE
    assert len(calls) == 4


def test_uncertain_send_never_replays_after_resume(tmp_path):
    class UncertainBoss(RecordingBoss):
        def send_first(self, cid, message):
            self.sent.append((cid, message))
            raise RuntimeError('unknown send result')
    store, boss = RunStore(tmp_path), UncertainBoss()
    run_id = store.create(JOB, 1, 30, 75, '', message_mode='llm')
    run_pipeline(store, run_id, MessagingModel([{'message': MESSAGE}, {'approved': True, 'reason': '符合要求'}]), boss)
    assert store.get(run_id)['status'] == 'paused'
    run_pipeline(store, run_id, MessagingModel([]), boss)
    assert boss.greeted == ['id-1']
    assert boss.sent == [('id-1', MESSAGE)]
