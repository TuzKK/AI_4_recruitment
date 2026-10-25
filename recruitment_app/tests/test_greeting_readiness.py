import pytest

from recruitment_app.boss import BossBrowser
from recruitment_app.runner import RunStore, run_pipeline
from .test_core import JOB, FakeBoss, FakeModel


def test_greet_waits_for_cards_before_dispatch(monkeypatch):
    monkeypatch.setattr('recruitment_app.boss.time.sleep', lambda seconds: None)
    class Session:
        reads = 0
        writes = 0
        def rpc(self, route): return {'connected': True, 'allow_writes': True}
        def navigate(self, page): pass
        def call(self, operation, args=None):
            if operation == 'cards':
                self.reads += 1
                return [] if self.reads < 3 else [{'geek_id': 'c1'}]
            assert self.reads >= 3
            self.writes += 1
            return {'status': 'observed'}
    session = Session()
    assert BossBrowser(session).greet('c1') is True
    assert session.writes == 1


def test_missing_target_never_dispatches_greeting(monkeypatch):
    from recruitment_app.boss import GreetingNotSent
    class Session:
        def rpc(self, route): return {'connected': True, 'allow_writes': True}
        def navigate(self, page): pass
        def call(self, operation, args=None):
            assert operation == 'cards'
            return [{'geek_id': 'other'}]
    with pytest.raises(GreetingNotSent):
        BossBrowser(Session()).greet('c1')


def test_proven_preflight_failure_keeps_reason_and_does_not_use_quota(tmp_path):
    from recruitment_app.boss import GreetingNotSent
    class NotReady(FakeBoss):
        def greet(self, cid):
            raise GreetingNotSent('candidate list not ready')
    store = RunStore(tmp_path)
    run = store.create(JOB, 1, 30, 75, '你好')
    run_pipeline(store, run, FakeModel(), NotReady())
    row = store.get(run)['candidates']['id-1']
    assert row['state'] == 'greet_not_sent' and not row['greeting_attempted']
    assert 'candidate list not ready' in row['greeting_error']
    assert store.get(run)['status'] == 'paused'


def test_unknown_post_dispatch_failure_keeps_quota_and_original_error(tmp_path):
    class Unknown(FakeBoss):
        def greet(self, cid):
            raise RuntimeError('response timeout after dispatch')
    store = RunStore(tmp_path)
    run = store.create(JOB, 1, 30, 75, '你好')
    run_pipeline(store, run, FakeModel(), Unknown())
    row = store.get(run)['candidates']['id-1']
    assert row['state'] == 'needs_review' and row['greeting_attempted']
    assert 'response timeout after dispatch' in row['greeting_error']


def test_greeting_does_not_refresh_away_from_current_candidate():
    class Session:
        def rpc(self, route): return {'connected': True, 'allow_writes': True}
        def navigate(self, page):
            assert page == 'recommend', 'Navigating through chat rotates the recommendation list'
        def call(self, operation, args=None):
            return [{'geek_id': 'c1'}] if operation == 'cards' else {'status': 'observed'}
    assert BossBrowser(Session()).greet('c1')


def test_receipt_matches_bound_sender_and_recipient_not_received_flag():
    import hashlib
    account = hashlib.sha256(b'uid:100').hexdigest()
    history = [{'received': True, 'from': {'uid': 100}, 'to': {'uid': 200},
                'body': {'text': 'test message'}}]
    assert BossBrowser._sent_message(history, 'test message', 200, account)
    assert not BossBrowser._sent_message(history, 'test message', 300, account)
    history[0]['from']['uid'] = 200
    history[0]['to']['uid'] = 100
    history[0]['received'] = False
    assert not BossBrowser._sent_message(history, 'test message', 200, account)


def test_receipt_rejects_unidentified_sender():
    assert not BossBrowser._sent_message(
        [{'received': False, 'body': {'text': 'test message'}}],
        'test message', 200, 'account')


def test_missing_candidate_is_skipped_without_pausing_next_contact(tmp_path):
    from recruitment_app.boss import CandidateUnavailable
    from .test_sequential_pipeline import OrderedBoss
    class Moved(OrderedBoss):
        def greet(self, cid):
            if cid == 'id-1':
                raise CandidateUnavailable('candidate moved')
            return super().greet(cid)
    store = RunStore(tmp_path)
    run = store.create(JOB, 1, 30, 75, '你好')
    boss = Moved([])
    run_pipeline(store, run, FakeModel(), boss)
    assert boss.greeted == ['id-2']
    assert store.get(run)['candidates']['id-1']['state'] == 'candidate_unavailable'
    assert store.get(run)['contacted'] == 1


def test_end_reason_distinguishes_exhausted_list_from_quota(tmp_path):
    store = RunStore(tmp_path)
    run = store.create(JOB, 2, 30, 75, '你好')
    run_pipeline(store, run, FakeModel(), FakeBoss())
    assert store.get(run)['end_reason'] == 'no_more_candidates'


def test_scan_limit_pauses_for_same_run_resume(tmp_path):
    class Bounded(FakeBoss):
        end_reason = 'scan_limit'
    store = RunStore(tmp_path)
    run = store.create(JOB, 2, 30, 75, '你好')
    run_pipeline(store, run, FakeModel(), Bounded())
    assert store.get(run)['status'] == 'paused'
    assert store.get(run)['end_reason'] == 'scan_limit'


def test_known_preclick_error_with_bridge_suffix_is_still_not_sent():
    from recruitment_app.boss import GreetingNotSent
    class Session:
        def rpc(self, route): return {'connected': True, 'allow_writes': True}
        def navigate(self, page): pass
        def call(self, operation, args=None):
            if operation == 'cards': return [{'geek_id': 'c1'}]
            raise RuntimeError('打招呼按钮不可用或不唯一，未发送；若已执行写动作，请核实，不要直接重发')
    with pytest.raises(GreetingNotSent):
        BossBrowser(Session()).greet('c1')


def test_dispatch_timeout_with_history_receipt_never_sends_twice(monkeypatch):
    import hashlib
    class Session:
        account_key = hashlib.sha256(b'uid:100').hexdigest()
        calls = 0
        def rpc(self, route): return {'connected': True, 'allow_writes': True}
        def navigate(self, page): pass
        def call(self, operation, args=None):
            self.calls += 1
            raise RuntimeError('timeout after send')
    class Boss(BossBrowser):
        def _relation(self, cid):
            return {'friendId': 200, 'uid': 200, 'encryptFriendId': cid, 'friendSource': 0}
        def _history(self, fid):
            return [{'from': {'uid': 100}, 'to': {'uid': 200}, 'body': {'text': 'hello'}}] if self.session.calls else []
    session = Session()
    assert Boss(session).send_first('candidate_12345', 'hello')
    assert session.calls == 1


def test_greeting_clicked_without_ui_ack_checks_relation_without_second_click(monkeypatch):
    monkeypatch.setattr('recruitment_app.boss.time.sleep', lambda _: None)
    class Session:
        writes = 0
        def rpc(self, route): return {'connected': True, 'allow_writes': True}
        def navigate(self, page): pass
        def call(self, operation, args=None):
            if operation == 'cards': return [{'geek_id': 'c1'}]
            self.writes += 1
            return {'status': 'clicked', 'candidate_id': 'c1', 'error': 'UI not updated'}
    class Boss(BossBrowser):
        def _relation(self, cid): return {'encryptFriendId': cid, 'friendId': 123}
    boss = Boss(Session())
    assert boss.greet('c1')
    assert boss.session.writes == 1
    assert boss.last_greeting_result['verification'] == 'chat_relation'


def test_structured_greeting_preflight_failure_never_uses_relation():
    from recruitment_app.boss import GreetingNotSent
    class Session:
        def rpc(self, route): return {'connected': True, 'allow_writes': True}
        def navigate(self, page): pass
        def call(self, operation, args=None):
            if operation == 'cards': return [{'geek_id': 'c1'}]
            return {'status': 'not_sent', 'candidate_id': 'c1', 'error': 'no unique button'}
    class Boss(BossBrowser):
        def _relation(self, cid): raise AssertionError('No write was dispatched')
    with pytest.raises(GreetingNotSent, match='no unique button'):
        Boss(Session()).greet('c1')


def test_already_contacted_card_is_skipped_without_consuming_a_new_greeting():
    from recruitment_app.boss import CandidateUnavailable
    class Session:
        def rpc(self, route): return {'connected': True, 'allow_writes': True}
        def navigate(self, page): pass
        def call(self, operation, args=None):
            if operation == 'cards': return [{'geek_id': 'c1'}]
            return {'status': 'not_sent', 'candidate_id': 'c1', 'clicked': False,
                    'controls': [{'label': '继续沟通'}], 'error': 'no greet button'}
    with pytest.raises(CandidateUnavailable, match='已建立会话'):
        BossBrowser(Session()).greet('c1')
