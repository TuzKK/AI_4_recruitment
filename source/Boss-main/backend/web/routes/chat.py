"""Explicit user-initiated sends to the currently open Chrome conversation."""
import json
from datetime import datetime, timedelta
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from database.db import get_db
from database.models import BossAccount, BrowserChatSend, RecruitTask
from rpa.extension_bridge import bridge, extension_endpoint
from web.routes.browser_extension import local_origin


def local_request(request: Request):
    if request.client.host not in ('127.0.0.1','::1','testclient') or not local_origin(str(request.base_url).rstrip('/')):
        raise HTTPException(403,'仅允许本机使用')
    origin=request.headers.get('origin')
    if origin and not local_origin(origin):
        raise HTTPException(403,'请从本机招聘程序发送消息')

router=APIRouter(prefix='/api/chat',tags=['chat'],dependencies=[Depends(local_request)])

class PreviewRequest(BaseModel):
    account_id: int

class SendRequest(BaseModel):
    preview_id: str = Field(min_length=1,max_length=64)
    message: str = Field(min_length=1,max_length=2000)
    @field_validator('message')
    @classmethod
    def nonempty(cls,value):
        value=value.strip()
        if not value: raise ValueError('消息不能为空')
        return value


def ensure_available(db,endpoint):
    if db.query(BrowserChatSend).filter_by(endpoint=endpoint,status='sending').first():
        raise HTTPException(409,'此 Chrome 正在发送消息，请等待结果')
    for task in db.query(RecruitTask).filter(RecruitTask.status.in_(['pending','running','paused'])).all():
        account=db.get(BossAccount,json.loads(task.config_json or '{}').get('account_id'))
        if account and account.cdp_url==endpoint:
            raise HTTPException(409,'此 Chrome 有招聘任务，请先停止任务再发送消息')


def receipt(row):
    return {'id':row.id,'account_id':row.account_id,'name':row.name,'message':row.message,
            'status':row.status,'detail':row.detail,'created_at':row.created_at.isoformat()}

@router.post('/preview')
async def preview(req:PreviewRequest,db:Session=Depends(get_db)):
    account=db.get(BossAccount,req.account_id)
    if not account: raise HTTPException(404,'账号不存在')
    if account.connection_type!='extension': raise HTTPException(409,'此功能需要 Chrome 插件接入的账号')
    endpoint,target=account.cdp_url,account.target_id
    ensure_available(db,endpoint)
    try:
        result=await bridge.call(extension_endpoint(endpoint),'chat_preview',target)
    except Exception as exc:
        raise HTTPException(409,str(exc)) from exc
    if not isinstance(result,dict) or not all(result.get(k) for k in ('token','frame_document','name','conversation_id')):
        raise HTTPException(409,'未识别当前会话，请更新插件并在 BOSS 中打开联系人')
    if result.get('has_draft'): raise HTTPException(409,'BOSS 输入框中已有草稿，请先处理')
    row=BrowserChatSend(id=uuid4().hex,account_id=account.id,endpoint=endpoint,target=target,
                       name=result['name'],preview_json=json.dumps(result,ensure_ascii=False),status='preview')
    db.add(row); db.commit()
    return {'preview_id':row.id,'name':row.name,'conversation_id':result['conversation_id'],'expires_in':300}

@router.post('/send')
async def send(req:SendRequest,db:Session=Depends(get_db)):
    row=db.get(BrowserChatSend,req.preview_id)
    if not row: raise HTTPException(404,'预览不存在，请重新读取会话')
    if row.status!='preview':
        if row.message!=req.message: raise HTTPException(409,'此预览已使用，不能更改消息后重发')
        return receipt(row)
    if datetime.utcnow()-row.created_at>timedelta(minutes=5): raise HTTPException(409,'预览已过期，请重新读取')
    account=db.get(BossAccount,row.account_id)
    if not account or account.cdp_url!=row.endpoint or account.target_id!=row.target:
        raise HTTPException(409,'账号接入已变化，请重新读取会话')
    ensure_available(db,row.endpoint)
    # Commit intent before external side effect; repeated HTTP requests cannot resend.
    updated=db.query(BrowserChatSend).filter_by(id=row.id,status='preview').update({'status':'sending','message':req.message})
    db.commit(); db.refresh(row)
    if updated!=1: return receipt(row)
    try:
        data=json.loads(row.preview_json)
        result=await bridge.call(extension_endpoint(row.endpoint),'chat_send',row.target,
                                {**data,'message':req.message},timeout=12)
        if isinstance(result,dict) and result.get('status')=='observed':
            row.status='observed'; row.detail='BOSS 页面出现新增本人消息；不代表对方已收到或已读'
        elif isinstance(result,dict) and result.get('status')=='not_sent':
            row.status='not_sent'; row.detail=result.get('detail','页面校验未通过，未点击发送')
        else:
            row.status='unknown'; row.detail=(result or {}).get('detail','未确认结果，请到 BOSS 核对，勿重复发送')
    except Exception as exc:
        row.status='unknown'; row.detail=f'{exc}；请到 BOSS 核对，程序不会重发'
    db.commit()
    return receipt(row)

@router.get('/history')
def history(db:Session=Depends(get_db)):
    return [receipt(r) for r in db.query(BrowserChatSend).filter(BrowserChatSend.status!='preview').order_by(BrowserChatSend.created_at.desc()).limit(50)]

@router.post('/diagnostics')
async def diagnostics(req:PreviewRequest,db:Session=Depends(get_db)):
    account=db.get(BossAccount,req.account_id)
    if not account or account.connection_type!='extension': raise HTTPException(409,'请选择插件账号')
    try:
        return await bridge.call(extension_endpoint(account.cdp_url),'chat_diagnostics',account.target_id)
    except Exception as exc:
        raise HTTPException(409,str(exc)) from exc
