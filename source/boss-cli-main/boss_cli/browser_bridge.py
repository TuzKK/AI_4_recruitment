"""Authenticated loopback bridge. Browser cookies never leave Chrome."""
from __future__ import annotations

import json
import queue
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import constants as c

READ_ROUTES = {
    ('GET', c.BOSS_CHATTED_JOB_LIST_URL), ('POST', c.BOSS_FRIEND_LIST_URL),
    ('POST', c.BOSS_FRIEND_DETAIL_URL), ('POST', c.BOSS_LAST_MSG_URL),
    ('GET', c.BOSS_HISTORY_MSG_URL), ('GET', c.BOSS_CHAT_GEEK_INFO_URL),
    ('GET', c.BOSS_VIEW_GEEK_URL), ('GET', c.BOSS_FRIEND_LABELS_URL),
    ('GET', c.BOSS_FRIEND_NOTE_URL), ('GET', c.BOSS_GREET_SORT_LIST_URL),
    ('GET', c.BOSS_GREET_REC_SORT_URL), ('GET', c.BOSS_SEARCH_GEEK_URL),
    ('GET', c.BOSS_INTERVIEW_LIST_URL), ('GET', c.USER_INFO_URL),
}
WRITE_ROUTES = {('POST', c.BOSS_SEND_MSG_URL), ('POST', c.BOSS_SESSION_ENTER_URL)}


class BrowserExecutionError(Exception):
    """An extension error after dispatch: never assume a write did not happen."""
    def __init__(self, message, *, not_dispatched=False, rate_limited=False):
        super().__init__(message)
        self.not_dispatched = not_dispatched
        self.rate_limited = rate_limited


class BrowserCommandTimeout(TimeoutError):
    def __init__(self, *, not_dispatched):
        super().__init__('排队超时，操作尚未执行' if not_dispatched else '浏览器操作超时；动作结果可能未知，请核实，不要直接重发')
        self.not_dispatched = not_dispatched


def validate_request(method: str, path: str, allow_writes: bool) -> None:
    if (method, path) not in READ_ROUTES | (WRITE_ROUTES if allow_writes else set()):
        raise ValueError('浏览器通道不支持该接口，或写操作未启用')


class BridgeState:
    def __init__(self, token: str, *, allow_writes: bool = False, command_timeout: float = 120):
        self.token = token
        self.allow_writes = allow_writes
        self.command_timeout = command_timeout
        self.client = None
        self.connection_error = None
        self.last_seen = 0.0
        self.pending = {}
        self.commands = queue.Queue()
        self.lock = threading.Lock()
        self.rate_limits = None
        self.rate_state = {}
        self.rate_limit_version = 0

    def configure_rates(self, values):
        if not isinstance(values, dict):
            raise ValueError('请求频率配置格式无效')
        r, g = values.get('request_seconds'), values.get('greet_seconds')
        if type(r) not in (int, float) or not 5 <= r <= 30 or type(g) not in (int, float) or not 20 <= g <= 60:
            raise ValueError('请求间隔须为5至30秒，打招呼间隔须为20至60秒')
        with self.lock:
            self.rate_limits = {'request_seconds': r, 'greet_seconds': g}

    def heartbeat(self, client, data):
        self.touch(client)
        with self.lock:
            self.rate_limit_version = 1 if data.get('rate_limit_version') == 1 else 0
            rate = data.get('rate_limit', {})
            self.rate_state = {k: rate[k] for k in ('state', 'until', 'request_seconds', 'greet_seconds', 'last_request_at') if k in rate}
            pending = self.pending.get(data.get('id'))
            if pending and pending['owner'] == client and data.get('write_started') is True:
                pending['write_started'] = True

    def touch(self, client: str):
        if not isinstance(client, str) or not re.fullmatch(r'[A-Za-z0-9-]{1,80}', client):
            raise ValueError('无效扩展标识')
        with self.lock:
            if self.client and self.client != client and (
                time.monotonic() - self.last_seen < 35 or self.pending
            ):
                self.connection_error = '另一个扩展已绑定；请重启连接服务后重新配对'
                raise ValueError(self.connection_error)
            self.client = client
            self.connection_error = None
            self.last_seen = time.monotonic()

    def status(self):
        return {'connected': bool(self.client and time.monotonic() - self.last_seen < 35),
                'allow_writes': self.allow_writes, 'connection_error': self.connection_error,
                'rate_limits': self.rate_limits, 'rate_limit': self.rate_state,
                'rate_limit_version': self.rate_limit_version}

    def call(self, operation: str, target: str, args: dict):
        if operation not in {'discover', 'inspect', 'open_login', 'cards', 'api', 'navigate', 'open_profile', 'profile_snapshot', 'profile_capture', 'resume_canvas', 'profile_network', 'chat_probe', 'chat_send', 'attachment_fetch', 'greet'}:
            raise ValueError('不支持的浏览器操作')
        if operation in {'chat_send', 'greet'} and not self.allow_writes:
            raise ValueError('消息发送未启用')
        if operation not in {'discover', 'open_login'} and not re.fullmatch(r'\d+:[A-Za-z0-9-]+', target):
            raise ValueError('无效页面标识，请重新发现页面')
        if operation == 'api':
            validate_request(args.get('method'), args.get('path'), self.allow_writes)
        if not self.status()['connected']:
            raise ValueError('Chrome 扩展尚未连接；这不代表 BOSS 未登录')
        request_id = secrets.token_hex(16)
        if self.rate_limits:
            args = {**args, 'rate_limits': self.rate_limits}
        item = {'id': request_id, 'operation': operation, 'target': target, 'args': args,
                'deadline': int((time.time() + self.command_timeout) * 1000)}
        pending = {'event': threading.Event(), 'owner': self.client, 'result': None, 'error': None,
                   'leased': False, 'write_started': False, 'not_dispatched': False, 'rate_limited': False}
        with self.lock:
            self.pending[request_id] = pending
        self.commands.put(item)
        try:
            if not pending['event'].wait(self.command_timeout):
                with self.lock:
                    raise BrowserCommandTimeout(not_dispatched=not pending['leased'] or
                                                (self.rate_limit_version == 1 and not pending['write_started']))
            if pending['error']:
                raise BrowserExecutionError(pending['error'], not_dispatched=pending['not_dispatched'], rate_limited=pending['rate_limited'])
            return pending['result']
        finally:
            with self.lock:
                self.pending.pop(request_id, None)

    def poll(self, client: str, timeout: float = 15):
        self.touch(client)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                item = self.commands.get(timeout=max(0.001, end - time.monotonic()))
            except queue.Empty:
                return None
            with self.lock:
                if item['id'] in self.pending and item['deadline'] > time.time() * 1000:
                    self.pending[item['id']]['leased'] = True
                    return item
        return None

    def complete(self, client, request_id, result, error, *, not_dispatched=False, rate_limited=False):
        with self.lock:
            pending = self.pending.get(request_id)
            if not pending or pending['owner'] != client or pending['event'].is_set():
                return False
            pending['result'] = result
            pending['error'] = str(error)[:500] if error else None
            pending['not_dispatched'] = bool(not_dispatched) and not pending['write_started']
            pending['rate_limited'] = bool(rate_limited)
            pending['event'].set()
            return True


def make_server(state: BridgeState, port: int = 17891):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Never log message bodies, pairing tokens or candidate data.

        def origin_allowed(self):
            origin = self.headers.get('Origin', '')
            return not origin or bool(re.fullmatch(r'chrome-extension://[a-p]{32}', origin))

        def respond(self, code, body):
            raw = json.dumps(body, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            origin = self.headers.get('Origin')
            if origin and self.origin_allowed():
                self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def do_OPTIONS(self):
            if not self.origin_allowed():
                return self.respond(403, {'error': 'origin denied'})
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', self.headers.get('Origin', ''))
            self.send_header('Access-Control-Allow-Headers', 'Authorization,Content-Type')
            self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
            self.end_headers()

        def authorized(self):
            if not self.origin_allowed():
                self.respond(403, {'error': 'origin denied'})
                return False
            if self.headers.get('Host') not in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}:
                self.respond(403, {'error': 'host denied'})
                return False
            if not secrets.compare_digest(self.headers.get('Authorization', ''), f'Bearer {state.token}'):
                self.respond(401, {'error': '连接令牌不匹配'})
                return False
            return True

        def do_GET(self):
            if self.authorized():
                self.respond(200, state.status()) if self.path == '/status' else self.respond(404, {})

        def do_POST(self):
            if not self.authorized():
                return
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 8_000_000:
                    raise ValueError('请求大小无效')
                data = json.loads(self.rfile.read(length))
                if self.path == '/rate-settings':
                    state.configure_rates(data)
                    result = state.status()
                elif self.path == '/heartbeat':
                    state.heartbeat(data['client'], data)
                    result = {'accepted': True}
                elif self.path == '/poll':
                    result = {'command': state.poll(data['client'])}
                elif self.path == '/result':
                    result = {'accepted': state.complete(data['client'], data['id'], data.get('result'), data.get('error'),
                              not_dispatched=data.get('not_dispatched', False), rate_limited=data.get('rate_limited', False))}
                elif self.path == '/command':
                    result = {'result': state.call(data['operation'], data.get('target', ''), data.get('args', {}))}
                else:
                    return self.respond(404, {})
                self.respond(200, result)
            except TimeoutError as exc:
                not_dispatched = getattr(exc, 'not_dispatched', False)
                self.respond(504, {'error': str(exc), 'outcome_unknown': not not_dispatched, 'not_dispatched': not_dispatched})
            except BrowserExecutionError as exc:
                self.respond(502, {'error': str(exc) + ('' if exc.not_dispatched else '；若已执行写动作，请核实，不要直接重发'),
                                  'outcome_unknown': not exc.not_dispatched, 'not_dispatched': exc.not_dispatched, 'rate_limited': exc.rate_limited})
            except ValueError as exc:
                self.respond(400, {'error': str(exc)[:300], 'outcome_unknown': False})
            except (KeyError, TypeError):
                self.respond(400, {'error': '请求格式无效', 'outcome_unknown': False})

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)
