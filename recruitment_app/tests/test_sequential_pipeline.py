from recruitment_app.runner import RunStore, run_pipeline
from .test_core import JOB, FakeBoss, FakeModel


class OrderedBoss(FakeBoss):
    def __init__(self, events, complete=True):
        super().__init__(complete)
        self.events = events

    def cards(self):
        return [dict(super().cards()[0], candidate_id=cid) for cid in ('id-1', 'id-2')]

    def greet(self, cid):
        self.events.append(('greet', cid))
        return super().greet(cid)

    def send_first(self, cid, message):
        self.events.append(('message', cid))
        return super().send_first(cid, message)

    def full_resume(self, cid):
        self.events.append(('resume', cid))
        assert cid in self.sent
        return super().full_resume(cid)


def test_contact_and_fine_screen_complete_before_next_candidate(tmp_path):
    events = []
    class Model(FakeModel):
        def evidence(self, stage, rubric, text):
            events.append((stage, ''))
            return super().evidence(stage, rubric, text)
    store = RunStore(tmp_path)
    run = store.create(JOB, 2, 30, 75, '你好')
    run_pipeline(store, run, Model(), OrderedBoss(events))
    assert events == [
        ('precontact', ''), ('greet', 'id-1'), ('message', 'id-1'), ('resume', 'id-1'), ('full_resume', ''),
        ('precontact', ''), ('greet', 'id-2'), ('message', 'id-2'), ('resume', 'id-2'), ('full_resume', '')]


def test_quota_stops_new_contact_but_waiting_resume_can_finish_without_cards(tmp_path):
    events = []
    store = RunStore(tmp_path)
    run = store.create(JOB, 1, 30, 75, '你好')
    boss = OrderedBoss(events, complete=False)
    run_pipeline(store, run, FakeModel(), boss)
    assert boss.greeted == ['id-1']
    assert store.get(run)['status'] == 'waiting_resume'
    assert store.get(run)['contacted'] == 1
    boss.complete = True
    boss.cards = lambda: (_ for _ in ()).throw(AssertionError('No new cards needed at quota'))
    run_pipeline(store, run, FakeModel(), boss)
    assert boss.greeted == ['id-1'] and boss.sent == ['id-1']
    assert store.get(run)['status'] == 'finished'
    assert store.get(run)['candidates']['id-1']['fine']['decision'] == 'high_match'


def test_fine_rejection_still_consumes_contact_quota_and_is_not_exported(tmp_path):
    class RejectFine(FakeModel):
        def assess(self, stage, *args):
            return {'score': 90 if stage == 'precontact' else 10,
                    'decision': 'contact' if stage == 'precontact' else 'not_fit'}
    store = RunStore(tmp_path)
    run = store.create(JOB, 1, 30, 75, '你好')
    boss = OrderedBoss([])
    run_pipeline(store, run, RejectFine(), boss)
    assert boss.greeted == ['id-1']
    assert store.get(run)['contacted'] == 1
    assert store.export(run).read_text(encoding='utf-8') == ''


def test_fine_api_failure_resume_does_not_repeat_messages(tmp_path):
    import pytest
    class FailFine(FakeModel):
        def evidence(self, stage, rubric, text):
            if stage == 'full_resume':
                raise RuntimeError('API timeout')
            return super().evidence(stage, rubric, text)
    store = RunStore(tmp_path)
    run = store.create(JOB, 1, 30, 75, '你好')
    boss = OrderedBoss([])
    with pytest.raises(RuntimeError):
        run_pipeline(store, run, FailFine(), boss)
    run_pipeline(store, run, FakeModel(), boss)
    assert boss.greeted == ['id-1'] and boss.sent == ['id-1']


def test_does_not_prefetch_next_candidate_after_quota(tmp_path):
    class LazyBoss(OrderedBoss):
        def iter_cards(self):
            yield super().cards()[0]
            raise AssertionError('Quota reached: must not open next candidate')
    store = RunStore(tmp_path)
    run = store.create(JOB, 1, 30, 75, '你好')
    run_pipeline(store, run, FakeModel(), LazyBoss([]))
    assert store.get(run)['status'] == 'finished'


def test_waiting_first_candidate_does_not_block_second(tmp_path):
    class WaitingBoss(OrderedBoss):
        def full_resume(self, cid):
            result = super().full_resume(cid)
            if cid == 'id-1':
                result['coverage'] = 'partial'
            return result
    store = RunStore(tmp_path)
    run = store.create(JOB, 2, 30, 75, '你好')
    boss = WaitingBoss([])
    run_pipeline(store, run, FakeModel(), boss)
    assert boss.greeted == ['id-1', 'id-2']
    assert store.get(run)['status'] == 'waiting_resume'
    output = store.export(run).read_text(encoding='utf-8')
    assert 'id-2' in output and 'id-1' not in output


def test_stop_after_greeting_resumes_message_without_second_greeting(tmp_path):
    store = RunStore(tmp_path)
    run = store.create(JOB, 1, 30, 75, '你好')
    class StopBoss(OrderedBoss):
        def greet(self, cid):
            value = super().greet(cid)
            store.update(run, status='stop_requested')
            return value
    boss = StopBoss([])
    run_pipeline(store, run, FakeModel(), boss)
    assert store.get(run)['status'] == 'paused' and not boss.sent
    run_pipeline(store, run, FakeModel(), boss)
    assert boss.greeted == ['id-1'] and boss.sent == ['id-1']


def test_stop_during_last_fine_is_preserved(tmp_path):
    store = RunStore(tmp_path)
    run = store.create(JOB, 1, 30, 75, '你好')
    class StopModel(FakeModel):
        def evidence(self, stage, rubric, text):
            if stage == 'full_resume':
                store.update(run, status='stop_requested')
            return super().evidence(stage, rubric, text)
    run_pipeline(store, run, StopModel(), OrderedBoss([]))
    assert store.get(run)['status'] == 'paused'


def test_same_process_pending_write_remains_reviewable(tmp_path):
    store = RunStore(tmp_path)
    run = store.create(JOB, 1, 30, 75, '你好')
    store.update(run, status='failed')
    store.candidate(run, 'id-1', name='test', state='message_pending',
                    greeting_attempted=True, greet_verified=True)
    boss = OrderedBoss([])
    run_pipeline(store, run, FakeModel(), boss)
    assert store.get(run)['status'] == 'paused'
    assert store.get(run)['candidates']['id-1']['state'] == 'needs_review'
    assert not boss.sent and not boss.greeted
