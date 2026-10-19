"""Manage app-owned Chrome profiles and externally attached BOSS tabs."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.db import SessionLocal, get_db
from database.models import BossAccount, RecruitTask
from rpa.chrome_connection import (ChromeConnection, PROFILES_BASE, RECOMMEND_URL,
    discover, inspect_page, inspect_during_login, launch_managed, normalize_endpoint, target_id)
from utils.config import get_config

router = APIRouter(prefix='/api/boss-accounts', tags=['boss-accounts'])
logger = logging.getLogger(__name__)
_active_logins: dict[int, asyncio.Task] = {}


class AccountCreate(BaseModel):
    name: str = ''


class ConnectRequest(BaseModel):
    cdp_url: str
    target_id: str


def account_out(a):
    return {'id': a.id, 'account_id': a.id, 'name': a.name or f'账号 {a.id}',
            'phone': a.phone or '', 'company': a.company or '',
            'connection_type': a.connection_type, 'cdp_url': a.cdp_url,
            'is_logged_in': a.is_logged_in, 'is_logging_in': a.id in _active_logins,
            'last_error': a.last_error or '',
            'step': 'waiting_for_login' if a.id in _active_logins else '',
            'last_login_at': a.last_login_at.isoformat() if a.last_login_at else None,
            'created_at': a.created_at.isoformat() if a.created_at else None}


async def validate_connection(endpoint, selected):
    if endpoint.startswith('extension:'):
        from rpa.extension_bridge import bridge, extension_endpoint
        state = await bridge.call(extension_endpoint(endpoint), 'inspect', selected)
        return {**state, 'target_id': selected}
    connection = ChromeConnection(endpoint, selected)
    try:
        page = await connection.open()
        return {**await inspect_page(page), 'target_id': await target_id(page)}
    finally:
        await connection.close()


STATE_MESSAGES = {'not_logged_in': '请先在 Chrome 中登录招聘者账号',
                  'verification_required': 'BOSS 页面需要人工完成验证',
                  'wrong_role': '当前为求职者页面，请切换到招聘者端',
                  'unknown': '尚未识别到已登录的招聘页面，请打开牛人推荐或聊天页',
                  'wrong_page': '所选页面已离开 BOSS 直聘'}


def save_state(account, state):
    account.is_logged_in = state['state'] == 'logged_in'
    account.last_error = '' if account.is_logged_in else STATE_MESSAGES.get(state['state'], '浏览器连接已断开')
    if account.is_logged_in:
        account.last_login_at = datetime.utcnow()
        account.target_id = state['target_id']
        if state.get('name'):
            account.name = state['name']
        if state.get('company'):
            account.company = state['company']


async def refresh_account(account):
    if not account.cdp_url:
        account.is_logged_in = False
        return
    try:
        save_state(account, await validate_connection(account.cdp_url, account.target_id))
    except Exception:
        account.is_logged_in = False
        account.last_error = '无法连接所选 Chrome 页面，请重新检测；专用浏览器可点击重新登录'


@router.get('')
async def list_accounts(db: Session = Depends(get_db)):
    accounts = db.query(BossAccount).order_by(BossAccount.created_at.desc()).all()
    for account in accounts:
        if account.id not in _active_logins:
            await refresh_account(account)
    db.commit()
    return [account_out(a) for a in accounts]


@router.get('/discover')
async def discover_browsers(port: int | None = Query(None, ge=1, le=65535), db: Session = Depends(get_db)):
    from rpa.extension_bridge import bridge
    cdp, extension_pages = await asyncio.gather(
        discover([a.cdp_url for a in db.query(BossAccount).all()], port), bridge.discover())
    cdp['pages'] = extension_pages + cdp['pages']
    return cdp


@router.post('/connect')
async def connect_browser(req: ConnectRequest, db: Session = Depends(get_db)):
    try:
        if req.cdp_url.startswith('extension:'):
            from rpa.extension_bridge import extension_endpoint
            extension_endpoint(req.cdp_url)
            endpoint = req.cdp_url
        else:
            endpoint = normalize_endpoint(req.cdp_url)
        if not req.target_id:
            raise ValueError('请选择具体 BOSS 页面')
        state = await validate_connection(endpoint, req.target_id)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, 'Chrome 调试连接失败，请重新检测') from exc
    if state['state'] != 'logged_in':
        raise HTTPException(409, STATE_MESSAGES.get(state['state'], '尚未登录'))
    account = db.query(BossAccount).filter(BossAccount.cdp_url == endpoint).first()
    if account:
        ensure_idle(db, account.id)
    else:
        account = BossAccount(profile_dir=f'external:{uuid4().hex}', connection_type='extension' if endpoint.startswith('extension:') else 'external', cdp_url=endpoint)
        db.add(account)
    save_state(account, state)
    db.commit()
    db.refresh(account)
    return account_out(account)


def ensure_idle(db, account_id):
    for task in db.query(RecruitTask).filter(RecruitTask.status.in_(['pending', 'running', 'paused'])).all():
        if json.loads(task.config_json or '{}').get('account_id') == account_id:
            raise HTTPException(409, '该账号有正在执行的任务，请先停止任务')


def schedule_login(account_id, profile):
    _active_logins[account_id] = asyncio.create_task(_run_login(account_id, profile))


@router.post('/login')
async def start_login(req: AccountCreate, db: Session = Depends(get_db)):
    account = BossAccount(name=req.name, profile_dir=str(PROFILES_BASE / ('account_' + uuid4().hex)),
                          connection_type='managed', is_logged_in=False)
    db.add(account)
    db.commit()
    db.refresh(account)
    schedule_login(account.id, account.profile_dir)
    return {'account_id': account.id, 'status': 'launching', 'message': '正在打开专用 Chrome，请登录 BOSS 招聘者账号'}


@router.post('/{account_id}/relogin')
async def relogin(account_id: int, db: Session = Depends(get_db)):
    account = db.get(BossAccount, account_id)
    if not account:
        raise HTTPException(404, '账号不存在')
    ensure_idle(db, account_id)
    if account.connection_type in ('external', 'extension'):
        await refresh_account(account)
        db.commit()
        if not account.is_logged_in:
            raise HTTPException(409, account.last_error + '。外部浏览器请在原窗口登录后重新检测接入')
        return {'account_id': account.id, 'status': 'connected'}
    if account_id not in _active_logins:
        account.last_error = ''
        db.commit()
        schedule_login(account_id, account.profile_dir)
    return {'account_id': account_id, 'status': 'launching'}


@router.get('/{account_id}/status')
async def get_login_status(account_id: int, db: Session = Depends(get_db)):
    account = db.get(BossAccount, account_id)
    if not account:
        raise HTTPException(404, '账号不存在')
    if account_id not in _active_logins:
        await refresh_account(account)
        db.commit()
    return account_out(account)


@router.delete('/{account_id}')
async def delete_account(account_id: int, db: Session = Depends(get_db)):
    account = db.get(BossAccount, account_id)
    if not account:
        raise HTTPException(404, '账号不存在')
    ensure_idle(db, account_id)
    job = _active_logins.get(account_id)
    if job:
        job.cancel()
        try:
            await job
        except asyncio.CancelledError:
            pass
    # Removing a binding never deletes or closes user browser data.
    db.delete(account)
    db.commit()
    return {'status': 'deleted'}


async def _run_login(account_id, profile):
    connection = None
    try:
        endpoint = await launch_managed(profile, get_config().get('browser', {}).get('chrome_path', ''))
        with SessionLocal() as db:
            account = db.get(BossAccount, account_id)
            if not account:
                return
            account.cdp_url = endpoint
            account.target_id = ''
            account.is_logged_in = False
            account.last_error = ''
            db.commit()
        from playwright.async_api import async_playwright
        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.connect_over_cdp(endpoint, timeout=5000)
            from rpa.chrome_connection import is_boss_url
            pages = [p for c in browser.contexts for p in c.pages if is_boss_url(p.url)]
            page = pages[0] if pages else await browser.contexts[0].new_page()
            if not pages:
                await page.goto(RECOMMEND_URL, wait_until='domcontentloaded')
            selected = await target_id(page)
            await page.bring_to_front()
        finally:
            await pw.stop()
        connection = ChromeConnection(endpoint, selected)
        page = await connection.open()
        with SessionLocal() as db:
            account = db.get(BossAccount, account_id)
            account.target_id = selected
            db.commit()
        for _ in range(150):
            if page.is_closed():
                raise RuntimeError('登录窗口已关闭，请点击重新登录')
            state = await inspect_during_login(page)
            if state['state'] == 'logged_in':
                with SessionLocal() as db:
                    account = db.get(BossAccount, account_id)
                    if account:
                        save_state(account, {**state, 'target_id': selected})
                        db.commit()
                return
            await asyncio.sleep(2)
        raise RuntimeError('等待登录超时。浏览器已保留，完成登录后点击刷新状态')
    except Exception as exc:
        logger.error('Account %s login failed: %s', account_id, exc)
        with SessionLocal() as db:
            account = db.get(BossAccount, account_id)
            if account:
                account.is_logged_in = False
                account.last_error = str(exc)[:500]
                db.commit()
    finally:
        if connection:
            await connection.close()
        _active_logins.pop(account_id, None)
