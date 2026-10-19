import test from 'node:test';
import assert from 'node:assert/strict';
let sends=0;
let uid='new-account';
globalThis.chrome={
  storage:{local:{get:async()=>({enabled:false})},session:{set:async()=>{},get:async()=>({})}},
  runtime:{onMessage:{addListener(){}},onStartup:{addListener(){}}},
  alarms:{onAlarm:{addListener(){}}},
  tabs:{get:async()=>({url:'https://www.zhipin.com/web/chat/index'})},
  scripting:{executeScript:async input=>{
    const [operation,args]=input.args;
    if(operation==='inspect') return [{frameId:0,documentId:'same-doc',result:{content:true,account:'same-name'}}];
    if(args.path==='/wapi/zpuser/wap/getUserInfo.json') return [{result:{status:200,body:{code:0,zpData:{userInfo:uid?{uid}: {name:'same-name'}}}}}];
    sends++;return [{result:{status:200,body:{code:0,zpData:{}}}}];
  }}
};
const {execute}=await import('../worker.mjs');
test('same document with changed account never sends',async()=>{
  await assert.rejects(execute({operation:'api',target:'1:same-doc',deadline:Date.now()+5000,
    args:{method:'POST',path:'/wapi/zpchat/fastReply/sendReplyMsg',account_key:'old-account'}}),/账号/);
  assert.equal(sends,0);
});
test('unknown stable account ID never sends',async()=>{
  uid='';
  await assert.rejects(execute({operation:'api',target:'1:same-doc',deadline:Date.now()+5000,
    args:{method:'POST',path:'/wapi/zpchat/fastReply/sendReplyMsg',account_key:'expected-nonempty'}}),/账号/);
  assert.equal(sends,0);
});
test('matching stable account executes exactly once',async()=>{
  uid='valid-account';
  const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode('uid:'+uid));
  const expected=[...new Uint8Array(bytes)].map(x=>x.toString(16).padStart(2,'0')).join('');
  const result=await execute({operation:'api',target:'1:same-doc',deadline:Date.now()+5000,
    args:{method:'POST',path:'/wapi/zpchat/fastReply/sendReplyMsg',account_key:expected}});
  assert.equal(result.body.code,0);
  assert.equal(sends,1);
});
