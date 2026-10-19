import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from rpa.chrome_connection import profile_matches_version, inspect_during_login
from rpa.extension_bridge import BridgeHub, extension_endpoint


class LifecycleTests(unittest.TestCase):
    def test_stale_port_must_match_browser_identity(self):
        with tempfile.TemporaryDirectory() as root:
            profile = Path(root)
            (profile/'DevToolsActivePort').write_text('9222\n/devtools/browser/owned-id\n')
            self.assertTrue(profile_matches_version(profile, {'webSocketDebuggerUrl':'ws://127.0.0.1:9222/devtools/browser/owned-id'}))
            self.assertFalse(profile_matches_version(profile, {'webSocketDebuggerUrl':'ws://127.0.0.1:9222/devtools/browser/other-id'}))
            self.assertFalse(profile_matches_version(profile, {}))

    def test_extension_endpoint_only_accepts_client_ids(self):
        self.assertEqual(extension_endpoint('extension:abc-123'), 'abc-123')
        for endpoint in ['extension:', 'extension:../bad', 'http://evil.test', 'extension:abc/123']:
            with self.assertRaises(ValueError): extension_endpoint(endpoint)


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_fails_pending_commands(self):
        hub = BridgeHub()
        socket = AsyncMock()
        await hub.register('test-client', socket)
        task = asyncio.create_task(hub.call('test-client', 'inspect', '1:doc'))
        await asyncio.sleep(0)
        await hub.remove('test-client', socket)
        with self.assertRaises(RuntimeError): await task

    async def test_response_routed_to_only_own_client(self):
        hub = BridgeHub()
        socket = AsyncMock()
        await hub.register('test-client', socket)
        task = asyncio.create_task(hub.call('test-client', 'inspect', '1:doc'))
        await asyncio.sleep(0)
        command = socket.send_json.call_args.args[0]
        hub.receive('other-client', {'id':command['id'], 'result':{'state':'logged_in'}})
        self.assertFalse(task.done())
        hub.receive('test-client', {'id':command['id'], 'result':{'state':'logged_in'}})
        self.assertEqual((await task)['state'], 'logged_in')
        await hub.remove('test-client', socket)

    async def test_arbitrary_commands_not_supported(self):
        hub=BridgeHub()
        with self.assertRaises(ValueError): await hub.call('test', 'eval', '1')


class LoginNavigationTests(unittest.IsolatedAsyncioTestCase):
    async def test_redirect_is_transient_but_other_errors_are_not_hidden(self):
        from playwright.async_api import Error
        with patch('rpa.chrome_connection.inspect_page',new_callable=AsyncMock) as probe:
            probe.side_effect=[Error('Execution context was destroyed, most likely because of a navigation'),{'state':'logged_in'}]
            self.assertEqual((await inspect_during_login(object()))['state'],'unknown')
            self.assertEqual((await inspect_during_login(object()))['state'],'logged_in')
            probe.side_effect=Error('Target closed')
            with self.assertRaises(Error): await inspect_during_login(object())
