"""Pair a local Chrome extension; pairing never sends recruiting messages."""
import asyncio
import logging
import re
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from rpa.extension_bridge import bridge

router = APIRouter(prefix='/api/browser-extension', tags=['browser-extension'])
logger = logging.getLogger(__name__)
TOKEN_PATH = Path(__file__).resolve().parents[2] / 'data' / 'browser_bridge_token'
EXTENSION_DIR = Path(__file__).resolve().parents[3] / 'chrome-extension'


def pairing_token():
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not TOKEN_PATH.exists():
        try:
            with TOKEN_PATH.open('x', encoding='utf-8') as out:
                out.write(secrets.token_urlsafe(32))
        except FileExistsError:
            pass
    return TOKEN_PATH.read_text(encoding='utf-8').strip()


def local_origin(value):
    origin = urlsplit(value)
    return origin.scheme == 'http' and origin.hostname in ('localhost', '127.0.0.1') and origin.port in (8000, 5173)


@router.get('/pairing')
async def pairing(request: Request):
    if request.client.host not in ('127.0.0.1', '::1', 'testclient'):
        raise HTTPException(403, 'Only local pairing is supported')
    origin = request.headers.get('origin')
    if origin and not local_origin(origin):
        raise HTTPException(403, 'Pair from the local settings page')
    if not local_origin(str(request.base_url).rstrip('/')):
        raise HTTPException(403, 'Invalid local host')
    return JSONResponse({'token': pairing_token(), 'extension_path': str(EXTENSION_DIR),
                         'connected_browsers': len(bridge.clients)}, headers={'Cache-Control': 'no-store'})


@router.websocket('/ws')
async def extension_socket(socket: WebSocket):
    origin = socket.headers.get('origin', '')
    if (socket.client.host not in ('127.0.0.1', '::1', 'testclient') or
            not re.fullmatch(r'chrome-extension://[a-p]{32}', origin)):
        await socket.close(code=1008)
        return
    await socket.accept()
    client_id = None
    try:
        hello = await asyncio.wait_for(socket.receive_json(), timeout=5)
        if not isinstance(hello, dict):
            await socket.close(code=1008)
            return
        token = hello.get('token', '')
        candidate_id = hello.get('client_id', '')
        if (hello.get('type') != 'hello' or not isinstance(token, str) or
                not secrets.compare_digest(token, pairing_token()) or
                not isinstance(candidate_id, str) or not re.fullmatch(r'[A-Za-z0-9-]{1,80}', candidate_id)):
            logger.warning('Extension pairing rejected: hello_type=%s token_type=%s token_length=%s token_ascii=%s client_id_valid=%s',
                           hello.get('type') == 'hello', type(token).__name__, len(token) if isinstance(token,str) else -1,
                           token.isascii() if isinstance(token,str) else False,
                           isinstance(candidate_id,str) and bool(re.fullmatch(r'[A-Za-z0-9-]{1,80}',candidate_id)))
            await socket.close(code=1008)
            return
        client_id = candidate_id
        await bridge.register(client_id, socket)
        await socket.send_json({'type': 'ready'})
        while True:
            message = await asyncio.wait_for(socket.receive_json(), timeout=45)
            if not isinstance(message, dict):
                break
            if message.get('type') == 'ping':
                await socket.send_json({'type':'pong'})
            else:
                bridge.receive(client_id, message)
    except (WebSocketDisconnect, TimeoutError, ValueError, RuntimeError):
        pass
    finally:
        if client_id:
            await bridge.remove(client_id, socket)
