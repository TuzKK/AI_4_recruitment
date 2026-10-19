import time, unittest
from pathlib import Path
from playwright.async_api import async_playwright
from rpa.chrome_connection import find_chrome
HTML='''<div class="boss-chat"><ul class="user-list"><li class="selected" data-id="p1"><span class="name">测试会话</span></li></ul><div class="chat-conversation" data-id="p1"><div class="chat-user"><span class="name">测试会话</span></div><div class="message-list"></div><textarea id="chat-input"></textarea><button class="btn-send" onclick="window.clicks=(window.clicks||0)+1;let p=document.createElement('div');p.className='message-item is-self';p.setAttribute('data-mid','new-message-1');let t=document.createElement('span');t.className='text';t.textContent=document.querySelector('#chat-input').value;p.append(t);document.querySelector('.message-list').append(p);document.querySelector('#chat-input').value='';">发送</button></div></div>'''
class ChatDomTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.pw=await async_playwright().start()
  self.browser=await self.pw.chromium.launch(executable_path=find_chrome(),headless=True)
  self.page=await self.browser.new_page()
  await self.page.route('**/*',lambda r:r.fulfill(status=200,content_type='text/html; charset=utf-8',body=HTML))
  await self.page.goto('https://www.zhipin.com/web/chat/index')
 async def asyncTearDown(self):
  await self.browser.close(); await self.pw.stop()
 async def run_dom(self,op,args=None):
  src=(Path(__file__).resolve().parents[2]/'chrome-extension/chat-dom.js').read_text(encoding='utf-8-sig').replace('export async function','async function',1)
  return await self.page.evaluate('async ([op,args])=>{const run='+src+';const result=await run(op,args);if(result?.chat_error)throw new Error(result.detail);return result;}',[op,args or {}])
 def args(self,p): return {'token':p['token'],'message':'你好\n测试','deadline':int(time.time()*1000)+8000}
 async def test_preview_and_once(self):
  p=await self.run_dom('chat_preview'); self.assertEqual(p['name'],'测试会话')
  self.assertIsNone(await self.page.evaluate('window.clicks'))
  r=await self.run_dom('chat_send',self.args(p)); self.assertEqual(r['status'],'observed')
  self.assertEqual(await self.page.locator('.message-item .text').text_content(),'你好\n测试')
  with self.assertRaisesRegex(Exception,'失效|使用'): await self.run_dom('chat_send',self.args(p))
  self.assertEqual(await self.page.evaluate('window.clicks'),1)
 async def test_changed_recipient(self):
  p=await self.run_dom('chat_preview')
  await self.page.locator('.selected').evaluate("e=>e.setAttribute('data-id','p2')")
  with self.assertRaisesRegex(Exception,'会话'): await self.run_dom('chat_send',self.args(p))
  self.assertIsNone(await self.page.evaluate('window.clicks'))
 async def test_existing_draft(self):
  p=await self.run_dom('chat_preview'); await self.page.locator('#chat-input').fill('原草稿')
  with self.assertRaisesRegex(Exception,'草稿'): await self.run_dom('chat_send',self.args(p))
  self.assertEqual(await self.page.locator('#chat-input').input_value(),'原草稿')
 async def test_login(self):
  p=await self.run_dom('chat_preview')
  await self.page.evaluate("document.body.insertAdjacentHTML('beforeend','<div class=login-dialog>login</div>')")
  with self.assertRaisesRegex(Exception,'登录|验证'): await self.run_dom('chat_send',self.args(p))
  self.assertIsNone(await self.page.evaluate('window.clicks'))
 async def test_unconfirmed_click_not_reported_as_sent(self):
  p=await self.run_dom('chat_preview')
  await self.page.locator('.btn-send').evaluate("e=>e.onclick=()=>{window.clicks=(window.clicks||0)+1;document.querySelector('#chat-input').value=''}")
  r=await self.run_dom('chat_send',self.args(p)); self.assertEqual(r['status'],'unknown')
  self.assertEqual(await self.page.evaluate('window.clicks'),1)
 async def test_expired_does_not_write(self):
  p=await self.run_dom('chat_preview'); args=self.args(p); args['deadline']=0
  with self.assertRaisesRegex(Exception,'过期'): await self.run_dom('chat_send',args)
  self.assertEqual(await self.page.locator('#chat-input').input_value(),'')
  self.assertIsNone(await self.page.evaluate('window.clicks'))
 async def test_panel_recipient_mismatch(self):
  await self.page.locator('.chat-conversation').evaluate("e=>e.setAttribute('data-id','p2')")
  self.assertIsNone(await self.run_dom('chat_preview'))
 async def test_rerender_old_message_is_not_confirmation(self):
  await self.page.locator('.message-list').evaluate("e=>e.innerHTML='<div class=\"message-item is-self\"><span class=text>你好\\n测试</span></div>'")
  p=await self.run_dom('chat_preview')
  await self.page.locator('.btn-send').evaluate("e=>e.onclick=()=>{window.clicks=1;const l=document.querySelector('.message-list');l.innerHTML=l.innerHTML;document.querySelector('#chat-input').value=''}")
  self.assertEqual((await self.run_dom('chat_send',self.args(p)))['status'],'unknown')
 async def test_image_draft_not_destroyed(self):
  await self.page.locator('#chat-input').evaluate("e=>e.outerHTML='<div id=chat-input class=chat-input contenteditable=true><img src=data:, alt=emoji></div>'")
  p=await self.run_dom('chat_preview'); self.assertTrue(p['has_draft'])
  with self.assertRaisesRegex(Exception,'草稿'): await self.run_dom('chat_send',self.args(p))
  self.assertEqual(await self.page.locator('#chat-input img').count(),1)
  self.assertIsNone(await self.page.evaluate('window.clicks'))
 async def modern_fixture(self):
  await self.page.set_content('''<div class="geek-item selected" data-id="123-0"><span class="geek-name">测试会话</span></div><div class="chat-conversation"><span class="base-name"><span class="name-container"><span class="name-box">测试会话</span></span></span><div class="conversation-message"><div class="message-list"></div></div><div class="conversation-editor"><div id="boss-chat-editor-input" contenteditable="true"></div><div class="submit">发送</div></div></div>''')
  await self.page.evaluate('''()=>{const parent={};document.querySelector('.name-container').__vue__={$props:{geekId:123,name:'测试会话'}};document.querySelector('.conversation-message').__vue__={$parent:parent,$data:{geek:{uid:123}}};document.querySelector('.conversation-editor').__vue__={$parent:parent,$data:{files:[],disabled:false}};document.querySelector('.submit').onclick=()=>{window.clicks=(window.clicks||0)+1;let e=document.createElement('div');e.className='message-item';e.setAttribute('data-mid','m1');let m=document.createElement('div');m.className='item-myself';let t=document.createElement('span');t.className='text';t.textContent=document.querySelector('#boss-chat-editor-input').innerText;m.append(t);e.append(m);document.querySelector('.message-list').append(e);document.querySelector('#boss-chat-editor-input').textContent='';};}''')
 async def test_live_structure_adapter(self):
  await self.modern_fixture();p=await self.run_dom('chat_preview')
  self.assertIsNotNone(p);self.assertEqual(p['conversation_id'],'123-0')
  self.assertEqual((await self.run_dom('chat_send',self.args(p)))['status'],'observed')
 async def test_live_component_recipient_change(self):
  await self.modern_fixture();p=await self.run_dom('chat_preview');self.assertIsNotNone(p)
  await self.page.evaluate("document.querySelector('.conversation-message').__vue__.$data.geek.uid=456")
  with self.assertRaisesRegex(Exception,'会话'): await self.run_dom('chat_send',self.args(p))
  self.assertIsNone(await self.page.evaluate('window.clicks'))
 async def test_pending_attachment_blocks_send(self):
  await self.modern_fixture();p=await self.run_dom('chat_preview');self.assertIsNotNone(p)
  await self.page.evaluate("document.querySelector('.conversation-editor').__vue__.$data.files=[{name:'attachment.pdf'}]")
  with self.assertRaisesRegex(Exception,'草稿'): await self.run_dom('chat_send',self.args(p))
  self.assertIsNone(await self.page.evaluate('window.clicks'))
 async def test_attachment_arriving_during_input(self):
  await self.modern_fixture();p=await self.run_dom('chat_preview')
  await self.page.evaluate("document.querySelector('#boss-chat-editor-input').addEventListener('input',()=>setTimeout(()=>{document.querySelector('.conversation-editor').__vue__.$data.files=[{name:'late.pdf'}]},10))")
  with self.assertRaisesRegex(Exception,'附件|图片'): await self.run_dom('chat_send',self.args(p))
  self.assertIsNone(await self.page.evaluate('window.clicks'))
 async def test_foreign_frame_ignored_for_preview(self):
  await self.page.goto('https://example.test/')
  self.assertIsNone(await self.run_dom('chat_preview'))
 async def test_empty_editor_disables_send_until_text_input(self):
  await self.modern_fixture()
  await self.page.evaluate("()=>{const vm=document.querySelector('.conversation-editor').__vue__;vm.$data.disabled=true;document.querySelector('#boss-chat-editor-input').addEventListener('input',()=>{vm.$data.disabled=false})}")
  p=await self.run_dom('chat_preview')
  self.assertEqual((await self.run_dom('chat_send',self.args(p)))['status'],'observed')
