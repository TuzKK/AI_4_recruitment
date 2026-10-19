import json
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from boss_cli.browser_bridge import BridgeState, make_server, validate_request
from boss_cli.browser_session import BrowserSession, select_page
from boss_cli.client import BossClient
from boss_cli.exceptions import BossApiError


def test_only_fixed_boss_routes_and_methods_allowed():
    validate_request('POST', '/wapi/zprelation/friend/filterByLabel', False)
    for method, path in [('GET', 'https://evil.test/'), ('GET', '//evil.test/'),
                         ('GET', '/wapi/zpchat/fastReply/sendReplyMsg')]:
        with pytest.raises(ValueError):
            validate_request(method, path, True)
    with pytest.raises(ValueError):
        validate_request('POST', '/wapi/zpchat/fastReply/sendReplyMsg', False)


def test_disconnected_is_not_not_logged_in():
    with pytest.raises(BossApiError, match='连接'):
        select_page({'connected': False}, [])


def test_multiple_accounts_require_selection_and_no_name_matching():
    pages = [{'target': '1:doc-a', 'state': 'logged_in'}, {'target': '2:doc-b', 'state': 'logged_in'}]
    with pytest.raises(BossApiError, match='多个'):
        select_page({'connected': True}, pages)
    assert select_page({'connected': True}, pages, '2:doc-b')['target'] == '2:doc-b'


def test_browser_request_does_not_retry_unknown_send_result(monkeypatch):
    calls = []
    session = BrowserSession('http://127.0.0.1:17891', 'token', '1:doc')
    def fail(*args, **kwargs):
        calls.append(args)
        raise BossApiError('结果未知')
    monkeypatch.setattr(session, 'request', fail)
    with BossClient(session, request_delay=0) as client, pytest.raises(BossApiError, match='结果未知'):
        client.boss_send_message(1, 'test')
    assert len(calls) == 1


def test_bridge_auth_queue_result_and_expiry():
    state = BridgeState('secret', command_timeout=0.15)
    server = make_server(state, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    headers = {'Authorization': 'Bearer secret'}
    try:
        with httpx.Client(base_url=base, trust_env=False) as client:
            assert client.get('/status').status_code == 401
            assert client.get('/status', headers={**headers, 'Origin': 'https://evil.test'}).status_code == 403
            assert client.get('/status', headers=headers).json()['connected'] is False
            state.touch('extension-a')
            with ThreadPoolExecutor() as pool:
                waiting = pool.submit(state.call, 'discover', '', {})
                command = state.poll('extension-a', 0.1)
                assert command['operation'] == 'discover'
                assert not state.complete('other', command['id'], {'pages': []}, None)
                assert state.complete('extension-a', command['id'], {'pages': []}, None)
                assert waiting.result() == {'pages': []}
            with pytest.raises(TimeoutError):
                state.call('inspect', '1:doc', {})
            assert state.poll('extension-a', 0.01) is None
    finally:
        server.shutdown()
        server.server_close()


def test_windows_profile_discovery_finds_network_cookie_path(tmp_path, monkeypatch):
    from boss_cli import auth
    file = tmp_path / 'Google/Chrome/User Data/Default/Network/Cookies'
    file.parent.mkdir(parents=True)
    file.touch()
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setattr(auth.sys, 'platform', 'win32')
    assert str(file) in auth._iter_chrome_cookie_files('chrome')


def test_remote_unknown_result_survives_http_bridge():
    state = BridgeState('secret', allow_writes=True, command_timeout=2)
    server = make_server(state, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state.touch('extension-a')
    def worker():
        command = state.poll('extension-a', 1)
        state.complete('extension-a', command['id'], None, '动作结果未知；不要直接重发')
    try:
        with ThreadPoolExecutor() as pool:
            pending = pool.submit(worker)
            response = httpx.post(f'http://127.0.0.1:{server.server_port}/command', trust_env=False,
                                  headers={'Authorization': 'Bearer secret'}, json={
                                      'operation': 'api', 'target': '1:doc', 'args': {
                                          'method': 'POST', 'path': '/wapi/zpchat/fastReply/sendReplyMsg'}})
            pending.result()
        assert response.json()['outcome_unknown'] is True
        assert '不要直接重发' in response.json()['error']
    finally:
        server.shutdown()
        server.server_close()


def test_cli_chat_uses_bridge_end_to_end_without_cookie_extraction(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from boss_cli.cli import cli
    state = BridgeState('test-only-local-token-12345678', command_timeout=2)
    server = make_server(state, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    config = tmp_path / 'bridge.json'
    config.write_text(json.dumps({'port': server.server_port, 'token': state.token}), encoding='utf-8')
    monkeypatch.setenv('BOSS_BRIDGE_FILE', str(config))
    state.touch('extension-a')
    def forbid_cookie():
        raise AssertionError('browser mode must not extract cookies')
    monkeypatch.setattr('boss_cli.commands._common.get_credential', forbid_cookie)
    def worker():
        command = state.poll('extension-a', 1)
        assert command['operation'] == 'discover'
        state.complete('extension-a', command['id'], {'pages': [
            {'target': '1:doc', 'state': 'logged_in', 'account_key': 'account-a'}]}, None)
        command = state.poll('extension-a', 1)
        assert command['args']['account_key'] == 'account-a'
        assert command['args']['params']['gid'] == 123
        state.complete('extension-a', command['id'], {
            'status': 200, 'body': {'code': 0, 'zpData': {'messages': [{'body': {'text': 'synthetic-test'}}]}}}, None)
    try:
        with ThreadPoolExecutor() as pool:
            pending = pool.submit(worker)
            result = CliRunner().invoke(cli, ['--transport', 'browser', 'recruiter', 'chat', '123', '--json'])
            pending.result()
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)['data']['messages'][0]['body']['text'] == 'synthetic-test'
    finally:
        server.shutdown()
        server.server_close()
