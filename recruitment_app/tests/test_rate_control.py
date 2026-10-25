import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'source/boss-cli-main'))
from boss_cli.browser_bridge import BridgeState

def test_settings_validate_and_heartbeat_preserves_connection(monkeypatch):
    state=BridgeState('secret')
    with pytest.raises(ValueError): state.configure_rates({'request_seconds':1,'greet_seconds':20})
    state.configure_rates({'request_seconds':10,'greet_seconds':30})
    state.heartbeat('extension-a',{'rate_limit_version':1,'rate_limit':{'state':'waiting','until':123456}})
    assert state.status()['connected']
    assert state.status()['rate_limit']['state']=='waiting'
    assert state.status()['rate_limits']=={'request_seconds':10,'greet_seconds':30}

def test_expired_undispatched_command_is_distinct_from_unknown_write():
    state=BridgeState('secret',allow_writes=True,command_timeout=.01)
    state.touch('extension-a')
    with pytest.raises(TimeoutError) as error: state.call('greet','1:doc',{'geek_id':'c1'})
    assert error.value.not_dispatched is True

def test_rate_settings_are_saved_on_job_and_cannot_disable_limits(tmp_path):
    from recruitment_app.runner import RunStore
    from .test_core import JOB
    store=RunStore(tmp_path)
    with pytest.raises(ValueError): store.create(JOB,1,30,75,'你好',rate_limits={'request_seconds':0,'greet_seconds':20})
    run=store.create(JOB,1,30,75,'你好')
    assert store.get(run)['rate_limits']=={'request_seconds':5,'greet_seconds':20}

def test_waiting_for_greeting_does_not_use_quota(tmp_path):
    from recruitment_app.runner import RunStore, run_pipeline
    from recruitment_app.boss import GreetingNotSent
    from .test_core import JOB, FakeBoss, FakeModel
    store=RunStore(tmp_path); run=store.create(JOB,1,30,75,'你好')
    class WaitingBoss(FakeBoss):
        def greet(self,cid):
            assert store.get(run)['candidates'][cid]['greeting_attempted'] is False
            raise GreetingNotSent('限速等待，未发送')
    run_pipeline(store,run,FakeModel(),WaitingBoss())
    row=store.get(run)['candidates']['id-1']
    assert row['state']=='greet_not_sent' and not row['greeting_attempted']

def test_unsent_message_cooldown_resumes_without_another_greeting(tmp_path):
    from recruitment_app.runner import RunStore, run_pipeline
    from boss_cli.exceptions import BrowserCommandError
    from .test_core import JOB, FakeBoss, FakeModel
    store=RunStore(tmp_path); run=store.create(JOB,1,30,75,'你好')
    class CoolingBoss(FakeBoss):
        cooling=True
        def send_first(self,cid,message):
            if self.cooling: raise BrowserCommandError('冷却',not_dispatched=True,rate_limited=True)
            return super().send_first(cid,message)
    boss=CoolingBoss(); run_pipeline(store,run,FakeModel(),boss)
    assert store.get(run)['status']=='paused'
    assert store.get(run)['candidates']['id-1']['state']=='greet_verified'
    boss.cooling=False
    run_pipeline(store,run,FakeModel(),boss)
    assert boss.greeted==['id-1'] and boss.sent==['id-1']

def test_heartbeat_updates_pending_write_evidence():
    import threading
    state=BridgeState('secret');state.touch('extension-a')
    state.pending['job']={'owner':'extension-a','write_started':False,'event':threading.Event()}
    state.heartbeat('extension-a',{'id':'job','write_started':True,'rate_limit_version':1})
    assert state.pending['job']['write_started']
