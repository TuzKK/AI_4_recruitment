"""CLI-side browser session selection; credentials stay inside Chrome."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import click
import httpx

from .constants import CONFIG_DIR
from .exceptions import BossApiError


def bridge_file():
    return Path(os.environ.get('BOSS_BRIDGE_FILE', str(CONFIG_DIR / 'browser-bridge.json')))


def load_bridge():
    path = bridge_file()
    if not path.exists():
        return None
    try:
        config = json.loads(path.read_text(encoding='utf-8'))
        port = config['port']
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError()
        if not isinstance(config['token'], str) or len(config['token']) < 20:
            raise ValueError()
        return config
    except (ValueError, KeyError):
        raise BossApiError('浏览器连接配置无效，请重启 boss browser serve') from None


def select_page(status, pages, target=None):
    if not status.get('connected'):
        raise BossApiError('Chrome 扩展尚未连接；不能据此判断 BOSS 是否登录')
    if target:
        pages = [p for p in pages if p.get('target') == target]
        if not pages:
            raise BossApiError('绑定页面已关闭或刷新，请重新发现并选择页面')
    if not pages:
        raise BossApiError('未发现 BOSS 页面，请运行 boss browser open-login')
    ready = [p for p in pages if p.get('state') == 'logged_in']
    if len(ready) > 1:
        raise BossApiError('发现多个已登录页面，请使用 --browser-target 指定目标')
    if not ready:
        states = ', '.join(sorted({p.get('state', 'unknown') for p in pages}))
        raise BossApiError(f'页面未确认招聘端登录（{states}）；请在原页面完成登录或验证')
    return ready[0]


@dataclass
class BrowserSession:
    base_url: str
    token: str
    target: str = ''
    account_key: str = ''
    cookies: dict = field(default_factory=dict)
    transport: str = 'browser'

    def rpc(self, route, payload=None):
        try:
            with httpx.Client(base_url=self.base_url, trust_env=False, timeout=32) as client:
                headers = {'Authorization': f'Bearer {self.token}'}
                response = (client.get(route, headers=headers) if payload is None else
                            client.post(route, json=payload, headers=headers))
                data = response.json()
                if response.status_code != 200:
                    raise BossApiError(data.get('error', '浏览器连接失败'))
                return data
        except (httpx.HTTPError, ValueError):
            raise BossApiError('浏览器连接服务不可用或超时；请检查 boss browser serve。动作结果未知时不要重发') from None

    def call(self, operation, args=None, target=None):
        args = {**(args or {}), 'account_key': self.account_key}
        return self.rpc('/command', {'operation': operation, 'target': self.target if target is None else target,
                                     'args': args})['result']

    def request(self, method, path, **kwargs):
        response = self.call('api', {'method': method, 'path': path, 'params': kwargs.get('params') or {},
                                     'data': kwargs.get('data') or {}, 'json': kwargs.get('json')})
        if not isinstance(response, dict) or not isinstance(response.get('body'), dict):
            raise BossApiError('浏览器返回非 JSON；请检查登录、验证页面或接口变更')
        if not 200 <= response.get('status', 0) < 300:
            raise BossApiError(f"浏览器接口 HTTP {response.get('status')}，未自动重试")
        return response['body']

    def navigate(self, page):
        result = self.call('navigate', {'page': page})
        self.target = result['target']
        self.account_key = result['account_key']
        return result


def browser_connection():
    config = load_bridge()
    if not config:
        raise BossApiError('尚未配置浏览器连接，请先运行 boss browser serve 并连接扩展')
    return BrowserSession(f"http://127.0.0.1:{config['port']}", config['token'])


def resolve_browser_session():
    context = click.get_current_context(silent=True)
    options = context.find_root().obj or {} if context else {}
    mode = options.get('transport', os.environ.get('BOSS_TRANSPORT', 'auto'))
    if mode == 'cookie':
        return None
    if mode == 'auto' and not bridge_file().exists():
        return None
    connection = browser_connection()
    status = connection.rpc('/status')
    if not status['connected']:
        select_page(status, [])
    pages = connection.call('discover')['pages']
    selected = select_page(status, pages, options.get('browser_target'))
    connection.target = selected['target']
    connection.account_key = selected.get('account_key', '')
    return connection
