"""Authenticated local extension bridge; finite commands, never arbitrary JS."""
from __future__ import annotations
import asyncio
import re
import time
from uuid import uuid4

OPERATIONS = {'discover', 'inspect', 'cards', 'greet', 'scroll', 'chat_preview', 'chat_send', 'chat_diagnostics'}


def extension_endpoint(value):
    if not re.fullmatch(r'extension:[A-Za-z0-9-]{1,80}', value):
        raise ValueError('无效的扩展连接标识')
    return value.split(':', 1)[1]


class BridgeHub:
    def __init__(self):
        self.clients = {}
        self.pending = {}

    async def register(self, client_id, socket):
        old = self.clients.get(client_id)
        if old:
            await self.remove(client_id, old)
            await old.close(code=1000)
        self.clients[client_id] = socket

    async def remove(self, client_id, socket):
        if self.clients.get(client_id) is not socket:
            return
        self.clients.pop(client_id, None)
        for (owner, _), future in list(self.pending.items()):
            if owner == client_id and not future.done():
                future.set_exception(RuntimeError('Chrome 扩展已断开，请在原浏览器中重新连接'))

    def receive(self, client_id, message):
        if not isinstance(message.get('id'), str):
            return
        future = self.pending.get((client_id, message['id']))
        if future and not future.done():
            if message.get('error'):
                future.set_exception(RuntimeError(str(message['error'])[:500]))
            else:
                future.set_result(message.get('result'))

    async def call(self, client_id, operation, target='', args=None, timeout=10):
        if operation not in OPERATIONS:
            raise ValueError('Unsupported browser operation')
        socket = self.clients.get(client_id)
        if not socket:
            raise RuntimeError('该 Chrome 扩展未连接，请点击扩展中的连接按钮')
        command_id = uuid4().hex
        key = (client_id, command_id)
        future = asyncio.get_running_loop().create_future()
        self.pending[key] = future
        try:
            await socket.send_json({'id': command_id, 'operation': operation, 'target': target,
                                    'args': args or {}, 'deadline': int((time.time() + timeout - 1)*1000)})
            return await asyncio.wait_for(future, timeout)
        except TimeoutError as exc:
            raise RuntimeError('扩展操作超时，发送结果可能未知，任务已停止且不会自动重试') from exc
        finally:
            self.pending.pop(key, None)

    async def discover(self):
        async def probe(client):
            try:
                pages = await self.call(client, 'discover')
                return [{**p, 'cdp_url': f'extension:{client}', 'connection_type': 'extension'}
                        for p in pages if isinstance(p, dict)]
            except Exception:
                return []
        groups = await asyncio.gather(*(probe(client) for client in list(self.clients)))
        return [page for group in groups for page in group]


bridge = BridgeHub()


class ExtensionEngine:
    def __init__(self, endpoint, target):
        self.client = extension_endpoint(endpoint)
        self.target = target

    async def call(self, operation, args=None):
        return await bridge.call(self.client, operation, self.target, args)

    async def launch(self):
        if (await self.call('inspect'))['state'] != 'logged_in':
            raise RuntimeError('所选 BOSS 页面未确认登录，请打开牛人推荐页并重新检测')
        return self

    async def close(self):
        pass  # No ownership of Chrome, tabs, or extension.
