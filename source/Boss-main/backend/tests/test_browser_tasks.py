"""Task wiring tests: mocked browser and LLM, temporary database only."""
import json
import os
import unittest
from unittest.mock import AsyncMock, patch
os.environ.setdefault('OPENAI_API_KEY', 'test-no-network')
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.db import Base
from database.models import BossAccount, Position, RecruitTask
from pipeline.orchestrator import RecruitPipeline
from pipeline.task_manager import TaskControl
from web.routes.tasks import TaskCreateRequest, create_task, stop_task
from pipeline.task_manager import task_manager
import asyncio
from fastapi import HTTPException


class TaskBrowserTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine)
        with self.sessions() as db:
            db.add(Position(id=1, title='测试岗位', jd_json='{"title":"测试"}', keywords_json='{}', scorecard_json='{}'))
            db.add(BossAccount(id=1, name='fixture', profile_dir='external:fixture', cdp_url='http://127.0.0.1:9222', target_id='fixture-target', is_logged_in=True))
            db.commit()

    def tearDown(self):
        self.engine.dispose()

    async def test_task_uses_bound_browser_and_skips_unimplemented_chat(self):
        with self.sessions() as db:
            db.add(RecruitTask(id=1, position_id=1, config_json=json.dumps({'account_id': 1, 'greeting_daily_limit': 0})))
            db.commit()
        mock_engine = AsyncMock()
        emit = AsyncMock()
        with patch('pipeline.orchestrator.SessionLocal', self.sessions), \
             patch('rpa.browser_engine.BrowserEngine', return_value=mock_engine) as factory, \
             patch('rpa.page_actions.ensure_logged_in', new_callable=AsyncMock), \
             patch('rpa.page_actions.get_unread_messages', new_callable=AsyncMock) as unread, \
             patch('pipeline.orchestrator.analyze_position') as analyze:
            pipeline = RecruitPipeline(1, TaskControl(1), emit)
            await pipeline.run()
            factory.assert_called_once_with('http://127.0.0.1:9222', 'fixture-target')
            mock_engine.launch.assert_awaited_once()
            mock_engine.close.assert_awaited_once()
            unread.assert_not_awaited()
            analyze.assert_not_called()
        with self.sessions() as db:
            self.assertEqual(db.get(RecruitTask, 1).status, 'completed')

    async def test_missing_account_rejected_before_task_creation(self):
        with self.sessions() as db:
            with self.assertRaises(HTTPException) as caught:
                await create_task(TaskCreateRequest(position_id=1, config={}), db)
            self.assertEqual(caught.exception.status_code, 400)
            self.assertEqual(db.query(RecruitTask).count(), 0)

    async def test_disconnected_and_busy_account_rejected(self):
        with self.sessions() as db:
            account = db.get(BossAccount, 1)
            account.is_logged_in = False
            db.commit()
            with patch('web.routes.boss_accounts.refresh_account', new_callable=AsyncMock):
                with self.assertRaises(HTTPException) as caught:
                    await create_task(TaskCreateRequest(position_id=1, config={'account_id': 1}), db)
                self.assertEqual(caught.exception.status_code, 409)
                account.is_logged_in = True
                db.add(RecruitTask(id=2, position_id=1, status='running', config_json='{"account_id":1}'))
                db.commit()
                with self.assertRaises(HTTPException) as caught:
                    await create_task(TaskCreateRequest(position_id=1, config={'account_id': 1}), db)
                self.assertEqual(caught.exception.status_code, 409)
                self.assertEqual(db.query(RecruitTask).count(), 1)

    async def test_stop_reserves_browser_until_coroutine_finishes(self):
        with self.sessions() as db:
            db.add(RecruitTask(id=3, position_id=1, status='running', config_json='{"account_id":1}'))
            db.commit()
            ctrl = TaskControl(3)
            release = asyncio.Event()
            running = asyncio.create_task(release.wait())
            task_manager.register_task(3, ctrl, running)
            try:
                result = await stop_task(3, db)
                self.assertEqual(result['status'], 'stopping')
                self.assertTrue(ctrl.should_stop)
                self.assertEqual(db.get(RecruitTask,3).status, 'running')
                with patch('web.routes.boss_accounts.refresh_account', new_callable=AsyncMock):
                    with self.assertRaises(HTTPException) as caught:
                        await create_task(TaskCreateRequest(position_id=1,config={'account_id':1}),db)
                    self.assertEqual(caught.exception.status_code,409)
            finally:
                release.set()
                await running
                task_manager.cleanup(3)

    async def test_stop_during_scoring_never_clicks_greeting(self):
        with self.sessions() as db:
            db.add(RecruitTask(id=4, position_id=1, config_json='{"account_id":1}'))
            db.commit()
        ctrl=TaskControl(4)
        mock_engine=AsyncMock()
        def score(*args):
            ctrl.stop()
            return {'score':100}
        with patch('pipeline.orchestrator.SessionLocal', self.sessions), \
             patch('rpa.browser_engine.BrowserEngine', return_value=mock_engine), \
             patch('rpa.page_actions.ensure_logged_in',new_callable=AsyncMock), \
             patch('rpa.page_actions.get_candidate_cards',new_callable=AsyncMock,return_value=[{'geek_id':'1','name':'fixture'}]), \
             patch('rpa.page_actions.click_greet_button',new_callable=AsyncMock) as click, \
             patch('pipeline.orchestrator.pre_match_candidate',side_effect=score):
            with self.assertRaises(asyncio.CancelledError):
                await RecruitPipeline(4,ctrl,AsyncMock()).run()
            click.assert_not_awaited()
            mock_engine.close.assert_awaited_once()

    async def test_extension_account_uses_extension_engine(self):
        with self.sessions() as db:
            account=db.get(BossAccount,1)
            account.connection_type='extension'
            account.cdp_url='extension:browser-1'
            account.target_id='12:document-1'
            db.add(RecruitTask(id=5,position_id=1,config_json='{"account_id":1,"greeting_daily_limit":0}'))
            db.commit()
        engine=AsyncMock()
        with patch('pipeline.orchestrator.SessionLocal',self.sessions), \
             patch('rpa.extension_bridge.ExtensionEngine',return_value=engine) as factory, \
             patch('rpa.extension_actions.ensure_logged_in',new_callable=AsyncMock):
            await RecruitPipeline(5,TaskControl(5),AsyncMock()).run()
            factory.assert_called_once_with('extension:browser-1','12:document-1')
            engine.close.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
