import unittest
from unittest.mock import patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database.db import Base,get_db
from database.models import BossAccount
from web.routes import chat
class ChatApiTests(unittest.TestCase):
 def setUp(self):
  self.engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
  Base.metadata.create_all(self.engine); sessions=sessionmaker(self.engine)
  with sessions() as db:
   db.add(BossAccount(name='fixture',profile_dir='fixture',connection_type='extension',cdp_url='extension:fixture',target_id='1:doc',is_logged_in=True)); db.commit()
  def database():
   with sessions() as db: yield db
  app=FastAPI(); app.include_router(chat.router); app.dependency_overrides[get_db]=database
  self.client=TestClient(app,base_url='http://127.0.0.1:8000')
 def tearDown(self): self.client.close(); self.engine.dispose()
 def test_single_use_even_after_timeout(self):
  preview={'token':'dom-token','frame_document':'doc','name':'测试','conversation_id':'p1','has_draft':False}
  with patch('web.routes.chat.bridge.call',new_callable=AsyncMock) as call:
   call.return_value=preview
   p=self.client.post('/api/chat/preview',json={'account_id':1}); self.assertEqual(p.status_code,200,p.text)
   body={'preview_id':p.json()['preview_id'],'message':'hello'}
   call.side_effect=RuntimeError('timeout')
   result=self.client.post('/api/chat/send',json=body); self.assertEqual(result.json()['status'],'unknown')
   count=call.await_count
   repeat=self.client.post('/api/chat/send',json=body); self.assertEqual(repeat.json()['status'],'unknown')
   self.assertEqual(call.await_count,count)
 def test_cross_origin_blocked(self):
  response=self.client.post('/api/chat/preview',headers={'Origin':'https://evil.test'},json={'account_id':1})
  self.assertEqual(response.status_code,403)
 def test_empty_message_rejected(self):
  response=self.client.post('/api/chat/send',json={'preview_id':'x','message':' '})
  self.assertEqual(response.status_code,422)
 def test_success_receipt_and_changed_replay(self):
  with patch('web.routes.chat.bridge.call',new_callable=AsyncMock) as call:
   call.return_value={'token':'dom','frame_document':'doc','name':'测试','conversation_id':'p1'}
   p=self.client.post('/api/chat/preview',json={'account_id':1}).json()
   call.return_value={'status':'observed'}
   body={'preview_id':p['preview_id'],'message':'hello'}
   self.assertEqual(self.client.post('/api/chat/send',json=body).json()['status'],'observed')
   self.assertEqual(self.client.post('/api/chat/send',json=body).json()['status'],'observed')
   self.assertEqual(call.await_count,2)
   body['message']='different'
   self.assertEqual(self.client.post('/api/chat/send',json=body).status_code,409)
   self.assertEqual(self.client.get('/api/chat/history').json()[0]['message'],'hello')
 def test_page_rejection_is_recorded_as_not_sent(self):
  with patch('web.routes.chat.bridge.call',new_callable=AsyncMock) as call:
   call.return_value={'token':'dom','frame_document':'doc','name':'测试','conversation_id':'p1'}
   p=self.client.post('/api/chat/preview',json={'account_id':1}).json()
   call.return_value={'status':'not_sent','detail':'会话已变化','chat_error':True}
   body={'preview_id':p['preview_id'],'message':'hello'}
   result=self.client.post('/api/chat/send',json=body).json()
   self.assertEqual(result['status'],'not_sent');self.assertEqual(result['detail'],'会话已变化')
   self.client.post('/api/chat/send',json=body)
   self.assertEqual(call.await_count,2)
