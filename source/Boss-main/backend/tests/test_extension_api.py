"""Pairing authentication and extension account persistence, using only fakes."""
import unittest
from unittest.mock import patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database.db import Base, get_db
from web.routes import browser_extension, boss_accounts


class ExtensionApiTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
        Base.metadata.create_all(self.engine)
        sessions=sessionmaker(self.engine)
        def database():
            with sessions() as db: yield db
        app=FastAPI()
        app.include_router(browser_extension.router)
        app.include_router(boss_accounts.router)
        app.dependency_overrides[get_db]=database
        self.client=TestClient(app,base_url='http://127.0.0.1:8000')
        self.token_patch=patch('web.routes.browser_extension.pairing_token',return_value='test-local-token-long-enough')
        self.token_patch.start()

    def tearDown(self):
        self.client.close()
        self.token_patch.stop()
        self.engine.dispose()

    def test_pairing_only_local_origin(self):
        valid=self.client.get('/api/browser-extension/pairing')
        self.assertEqual(valid.status_code,200)
        self.assertEqual(valid.headers['cache-control'],'no-store')
        bad=self.client.get('/api/browser-extension/pairing',headers={'Origin':'https://evil.test'})
        self.assertEqual(bad.status_code,403)
        rebound=self.client.get('/api/browser-extension/pairing',headers={'Host':'evil.test:8000'})
        self.assertEqual(rebound.status_code,403)

    def test_websocket_token_and_origin(self):
        from starlette.websockets import WebSocketDisconnect
        headers={'origin':'chrome-extension://'+'a'*32}
        with self.client.websocket_connect('/api/browser-extension/ws',headers=headers) as ws:
            ws.send_json({'type':'hello','token':'test-local-token-long-enough','client_id':'fixture-browser'})
            self.assertEqual(ws.receive_json()['type'],'ready')
            ws.send_json({'type':'ping'})
            self.assertEqual(ws.receive_json()['type'],'pong')
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect('/api/browser-extension/ws',headers=headers) as ws:
                ws.send_json({'type':'hello','token':'wrong','client_id':'fixture-browser'})
                ws.receive_json()
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect('/api/browser-extension/ws',headers={'origin':'https://evil.test'}):
                pass

    def test_extension_binding_never_launches_chrome(self):
        state={'state':'logged_in','name':'Fixture','company':'','url':'https://www.zhipin.com/web/chat/recommend'}
        with patch('rpa.extension_bridge.bridge.call',new_callable=AsyncMock,return_value=state) as call, \
             patch('web.routes.boss_accounts.launch_managed',new_callable=AsyncMock) as launch:
            data={'cdp_url':'extension:fixture-browser','target_id':'1:doc'}
            response=self.client.post('/api/boss-accounts/connect',json=data)
            self.assertEqual(response.status_code,200,response.text)
            result=response.json()
            self.assertEqual(result['connection_type'],'extension')
            account_id=result['id']
            duplicate=self.client.post('/api/boss-accounts/connect',json=data).json()
            self.assertEqual(duplicate['id'],account_id)
            self.assertEqual(self.client.post(f'/api/boss-accounts/{account_id}/relogin').status_code,200)
            launch.assert_not_awaited()
            call.assert_awaited()
            self.assertEqual(self.client.delete(f'/api/boss-accounts/{account_id}').status_code,200)
