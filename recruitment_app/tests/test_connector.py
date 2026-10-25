import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "source" / "boss-cli-main"))
from boss_cli.browser_bridge import BridgeState


def test_app_defaults_to_project_bridge_without_launcher(monkeypatch):
    from recruitment_app.boss import BossBrowser, CLI_ROOT
    import boss_cli.browser_session as sessions
    monkeypatch.delenv('BOSS_BRIDGE_FILE', raising=False)
    monkeypatch.delenv('BOSS_TRANSPORT', raising=False)
    class Session:
        account_key = 'verified'
        def rpc(self, route):
            return {'allow_writes': True}
    def resolve():
        assert Path(os.environ['BOSS_BRIDGE_FILE']) == CLI_ROOT / '.runtime' / 'browser-bridge.json'
        assert os.environ['BOSS_TRANSPORT'] == 'browser'
        return Session()
    monkeypatch.setattr(sessions, 'resolve_browser_session', resolve)
    assert BossBrowser.connected().session.account_key == 'verified'


def test_app_preserves_explicit_bridge_path(monkeypatch):
    from recruitment_app.boss import BossBrowser
    import boss_cli.browser_session as sessions
    monkeypatch.setenv('BOSS_BRIDGE_FILE', 'E:/custom/bridge.json')
    monkeypatch.setenv('BOSS_TRANSPORT', 'browser')
    class Session:
        account_key = 'verified'
        def rpc(self, route):
            return {'allow_writes': True}
    def resolve():
        assert os.environ['BOSS_BRIDGE_FILE'] == 'E:/custom/bridge.json'
        return Session()
    monkeypatch.setattr(sessions, 'resolve_browser_session', resolve)
    BossBrowser.connected()


def test_greeting_requires_write_enabled_bridge():
    bridge = BridgeState("test-token", allow_writes=False)
    with pytest.raises(ValueError, match="未启用"):
        bridge.call("greet", "1:document", {"geek_id": "c1"})


def test_write_enabled_bridge_recognizes_greeting_operation():
    bridge = BridgeState("test-token", allow_writes=True)
    with pytest.raises(ValueError, match="尚未连接"):
        bridge.call("greet", "1:document", {"geek_id": "c1"})


def test_cards_waits_for_delayed_list(monkeypatch):
    from recruitment_app.boss import BossBrowser
    monkeypatch.setattr('recruitment_app.boss.time.sleep', lambda seconds: None)
    class Session:
        calls = 0
        def call(self, operation):
            self.calls += 1
            return [] if self.calls < 3 else [{'geek_id': 'c1'}]
    session = Session()
    assert BossBrowser(session)._loaded_cards() == [{'geek_id': 'c1'}]
    assert session.calls == 3


def test_empty_cards_has_explicit_error(monkeypatch):
    from recruitment_app.boss import BossBrowser
    monkeypatch.setattr('recruitment_app.boss.time.sleep', lambda seconds: None)
    class Session:
        def call(self, operation):
            return []
    with pytest.raises(RuntimeError, match='未读取到候选人'):
        BossBrowser(Session())._loaded_cards()


def test_refreshed_recommendations_do_not_drop_captured_candidates():
    from recruitment_app.boss import BossBrowser
    initial = [
        {'geek_id': f'c{i}', 'name': f'Candidate {i}', 'text': f'Original card {i}'}
        for i in range(3)
    ]
    class Session:
        reads = 0
        opened = []
        def navigate(self, page):
            pass
        def call(self, operation, args=None):
            if operation == 'cards':
                self.reads += 1
                return initial if self.reads == 1 else [initial[0]]
            if operation == 'open_profile':
                self.opened.append(args['geek_id'])
                return {}
            if operation == 'profile_snapshot':
                return {}
            raise AssertionError(operation)
    session = Session()
    result = list(BossBrowser(session).iter_cards())
    assert [item['candidate_id'] for item in result] == ['c0', 'c1', 'c2']
    assert result[1]['text'] == 'Original card 1'
    assert result[2]['source'] == 'recommend_card'
    assert session.opened == ['c0']


def test_iterator_loads_more_candidates_without_duplicate_scoring(monkeypatch):
    from recruitment_app.boss import BossBrowser
    monkeypatch.setattr('recruitment_app.boss.time.sleep', lambda _: None)
    class Session:
        extra = False
        def navigate(self, page):
            assert page == 'recommend'
        def call(self, operation, args=None):
            if operation == 'cards':
                if args and args.get('advance'):
                    self.extra = True
                ids = ['c1', 'c2'] if self.extra else ['c1']
                return [{'geek_id': cid, 'name': cid, 'text': 'SQL delivery'} for cid in ids]
            return {}
    boss = BossBrowser(Session())
    assert [c['candidate_id'] for c in boss.iter_cards()] == ['c1', 'c2']
    assert boss.end_reason == 'no_more_candidates'


def test_abstract_uses_current_open_event_not_old_same_candidate_messages():
    from recruitment_app.boss import fresh_resume_message
    def message(at, cid, intro):
        return {'type': 'IFRAME_DONE', 'at': at, 'data': {
            'abstractData': {'encryptGeekId': cid, 'geekBaseInfo': {'intro': intro}}}}
    snapshot = {'frames': [{'resumeTap': {'messages': [
        message(100, 'c1', 'old'), message(300, 'c2', 'wrong person'),
        message(301, 'c1', 'new'), message(302, 'c1', 'latest')]}}]}
    assert fresh_resume_message(snapshot, 'c1', 200)['geekBaseInfo']['intro'] == 'latest'
    assert fresh_resume_message(snapshot, 'c1', 400) is None


def test_resume_scrolls_past_previously_screened_pages(monkeypatch):
    from recruitment_app.boss import BossBrowser
    monkeypatch.setattr('recruitment_app.boss.time.sleep', lambda _: None)
    class Session:
        loaded = 1
        def navigate(self, page): pass
        def call(self, operation, args=None):
            if operation == 'cards':
                if args and args.get('advance'):
                    self.loaded = min(7, self.loaded + 1)
                return [{'geek_id': f'c{i}', 'name': f'c{i}', 'text': 'SQL delivery'}
                        for i in range(self.loaded)]
            return {}
    boss = BossBrowser(Session())
    boss.skip_candidate_ids = {f'c{i}' for i in range(6)}
    assert [c['candidate_id'] for c in boss.iter_cards()] == ['c6']


def test_postcontact_resume_uses_verified_chat_relation(monkeypatch):
    from recruitment_app.boss import BossBrowser
    import boss_cli.client as client
    seen = []
    class Session:
        def navigate(self, page):
            assert page == 'chat'
    class Client:
        def __init__(self, session): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get_boss_view_geek(self, **kwargs):
            seen.append(kwargs)
            return {'geekDetailInfo': {'encryptGeekId': 'c1',
                    'geekBaseInfo': {'name': 'test'}, 'geekWorkExpList': [{'description': 'SQL delivery'}],
                    'geekEduExpList': [], 'geekProjectExpList': []}}
    monkeypatch.setattr(client, 'BossClient', Client)
    boss = BossBrowser(Session())
    boss._relation = lambda cid: {'encryptFriendId': cid, 'encryptJobId': 'j1', 'securityId': 's'}
    result = boss.contacted_resume('c1')
    assert result['coverage'] == 'complete' and result['candidate_id'] == 'c1'
    assert seen[0]['encrypt_geek_id'] == 'c1' and seen[0]['encrypt_job_id'] == 'j1'


def test_postcontact_never_guesses_job_or_uses_unmatched_profile():
    from recruitment_app.boss import BossBrowser
    class Session:
        def navigate(self, page): pass
    boss = BossBrowser(Session())
    boss._relation = lambda cid: {'encryptFriendId': cid}
    assert boss.contacted_resume('c1')['coverage'] == 'partial'


def test_relation_accepts_uid_schema_only_when_encrypted_identity_matches(monkeypatch):
    from recruitment_app.boss import BossBrowser
    import boss_cli.client as client
    class Client:
        def __init__(self, session): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get_boss_friend_list(self, **kwargs):
            return {'result': [{'friendId': 123, 'encryptFriendId': 'c1'}]}
        def get_boss_friend_details(self, ids):
            return {'friendList': [{'uid': 123, 'encryptUid': 'c1', 'encryptJobId': 'j1'}]}
    monkeypatch.setattr(client, 'BossClient', Client)
    assert BossBrowser(object())._relation('c1')['encryptJobId'] == 'j1'
