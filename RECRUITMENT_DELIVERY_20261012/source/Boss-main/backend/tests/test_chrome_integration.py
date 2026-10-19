"""Integration checks against isolated Chrome and fake DOM; no BOSS network/messages."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from playwright.async_api import async_playwright
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI
import httpx

from database.db import Base, migrate_browser_accounts, get_db
from database.models import BossAccount
from rpa.chrome_connection import (find_chrome, profile_port, inspect_page, target_id,
                                   ChromeConnection, probe_endpoint)
from rpa.page_actions import get_candidate_cards, click_greet_button
from web.routes import boss_accounts

URL = 'https://www.zhipin.com/web/chat/recommend'
CARD = '''<div class="recommend-main"><ul><li class="card-item">
<div class="card-inner" data-geekid="fixture-1"><span class="name">测试候选人</span></div>
<button onclick="window.clicks=(window.clicks||0)+1;this.textContent='继续沟通'">打招呼</button>
</li></ul></div>'''


class MigrationTests(unittest.TestCase):
    def test_additive_idempotent_migration_keeps_account(self):
        engine = create_engine('sqlite://')
        with engine.begin() as conn:
            conn.execute(text('CREATE TABLE boss_accounts (id INTEGER PRIMARY KEY, name TEXT)'))
            conn.execute(text("INSERT INTO boss_accounts VALUES (7, 'existing')"))
        migrate_browser_accounts(engine)
        migrate_browser_accounts(engine)
        with engine.connect() as conn:
            row = conn.execute(text('SELECT name, connection_type, cdp_url FROM boss_accounts')).one()
            self.assertEqual(tuple(row), ('existing', 'managed', ''))
        engine.dispose()


class ChromeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='boss-cdp-test-')
        self.pw = await async_playwright().start()
        self.context = await self.pw.chromium.launch_persistent_context(
            self.temp.name, executable_path=find_chrome(), headless=True,
            args=['--remote-debugging-port=0', '--remote-debugging-address=127.0.0.1'])
        async def fixture(route):
            await route.fulfill(status=200, content_type='text/html; charset=utf-8', body=self.html)
        self.html = CARD
        await self.context.route('**/*', fixture)
        self.page = self.context.pages[0]
        await self.page.goto(URL)
        self.endpoint = f'http://127.0.0.1:{profile_port(Path(self.temp.name))}'
        self.selected = await target_id(self.page)

    async def asyncTearDown(self):
        await self.context.close()
        await self.pw.stop()
        self.temp.cleanup()

    async def extension_dom(self, operation, args=None):
        script = (Path(__file__).resolve().parents[2] / 'chrome-extension' / 'page-dom.js').read_text(encoding='utf-8-sig')
        script = script[script.index('export async function'):].replace('export ', '', 1)
        return await self.page.evaluate('async ([op,args]) => { const run = ' + script + '; return await run(op,args); }', [operation, args or {}])

    async def test_extension_packaged_dom_clicks_once_and_rejects_login(self):
        import time
        cards = await self.extension_dom('cards')
        self.assertEqual(cards[0]['geek_id'],'fixture-1')
        state = await self.extension_dom('inspect')
        self.assertTrue(state['content'])
        self.assertIsNone(await self.page.evaluate('window.clicks'))
        args = {'geek_id':'fixture-1','deadline':int(time.time()*1000)+5000}
        self.assertTrue(await self.extension_dom('greet',args))
        self.assertFalse(await self.extension_dom('greet',args))
        self.assertEqual(await self.page.evaluate('window.clicks'),1)
        await self.page.set_content(CARD + '<div class="login-dialog">Login</div>')
        with self.assertRaises(Exception):
            await self.extension_dom('greet',args)
        self.assertEqual(await self.page.evaluate('window.clicks'),1)

    async def test_attach_exact_tab_detach_leaves_browser_alive(self):
        other = await self.context.new_page()
        await other.goto('https://www.zhipin.com/web/chat')
        connection = ChromeConnection(self.endpoint, self.selected)
        try:
            attached = await connection.open()
            self.assertEqual(await target_id(attached), self.selected)
            self.assertEqual((await inspect_page(attached))['state'], 'logged_in')
        finally:
            await connection.close()
        self.assertEqual(await self.page.evaluate('2+2'), 4)
        self.assertFalse(other.is_closed())
        ambiguous = ChromeConnection(self.endpoint)
        with self.assertRaises(RuntimeError):
            await ambiguous.open()
        missing = ChromeConnection(self.endpoint, 'missing-target')
        with self.assertRaises(RuntimeError):
            await missing.open()

    async def test_login_verification_role_and_url_only_rejected(self):
        await self.page.set_content('<h1>Loading</h1>')
        self.assertEqual((await inspect_page(self.page))['state'], 'unknown')
        await self.page.set_content(CARD + '<div class="login-dialog">登录</div>')
        self.assertEqual((await inspect_page(self.page))['state'], 'not_logged_in')
        await self.page.set_content(CARD + '<div class="verify-dialog">验证</div>')
        self.assertEqual((await inspect_page(self.page))['state'], 'verification_required')
        await self.page.goto('https://www.zhipin.com/web/geek/recommend')
        self.assertEqual((await inspect_page(self.page))['state'], 'wrong_role')
        await self.page.goto('https://www.zhipin.com/web/user/?from=chat')
        self.assertEqual((await inspect_page(self.page))['state'], 'not_logged_in')

    async def test_card_reader_and_greeting_click_once(self):
        cards = await get_candidate_cards(self.page, force_refresh=True)
        self.assertEqual(cards[0]['geek_id'], 'fixture-1')
        self.assertTrue(await click_greet_button(self.page, 'fixture-1', greet_btn_index=999))
        self.assertFalse(await click_greet_button(self.page, 'fixture-1'))
        self.assertEqual(await self.page.evaluate('window.clicks'), 1)
        self.assertFalse(await click_greet_button(self.page, 'missing'))

    async def test_iframe_auth_and_cards(self):
        self.html = CARD
        await self.page.set_content('<iframe src="https://www.zhipin.com/web/frame/recommend"></iframe>')
        for _ in range(30):
            if len(self.page.frames) > 1 and await self.page.frames[1].locator('li.card-item').count():
                break
            await asyncio.sleep(.1)
        self.assertEqual((await inspect_page(self.page))['state'], 'logged_in')
        self.assertEqual(len(await get_candidate_cards(self.page)), 1)

    async def test_discovery_is_read_only(self):
        before = self.page.url
        found = await probe_endpoint(self.endpoint)
        self.assertEqual(found[0]['state'], 'logged_in')
        self.assertEqual(found[0]['target_id'], self.selected)
        self.assertEqual(self.page.url, before)
        self.assertIsNone(await self.page.evaluate('window.clicks'))

    async def test_connect_deduplicates_refresh_and_delete_preserve_browser(self):
        engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
        Base.metadata.create_all(engine)
        sessions = sessionmaker(engine, expire_on_commit=False)
        def database():
            with sessions() as db:
                yield db
        app = FastAPI()
        app.include_router(boss_accounts.router)
        app.dependency_overrides[get_db] = database
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                payload = {'cdp_url': self.endpoint, 'target_id': self.selected}
                first = await client.post('/api/boss-accounts/connect', json=payload)
                self.assertEqual(first.status_code, 200, first.text)
                account_id = first.json()['id']
                second = await client.post('/api/boss-accounts/connect', json=payload)
                self.assertEqual(second.json()['id'], account_id)
                await self.page.set_content('<div class="login-dialog">登录</div>')
                status = (await client.get(f'/api/boss-accounts/{account_id}/status')).json()
                self.assertFalse(status['is_logged_in'])
                rejected = await client.post('/api/boss-accounts/connect', json=payload)
                self.assertEqual(rejected.status_code, 409)
                response = await client.delete(f'/api/boss-accounts/{account_id}')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(await self.page.evaluate('3+3'), 6)
                remote = await client.post('/api/boss-accounts/connect', json={'cdp_url': 'http://example.com:9222', 'target_id': 'x'})
                self.assertEqual(remote.status_code, 400)
        finally:
            engine.dispose()


if __name__ == '__main__':
    unittest.main()
