import test from 'node:test';
import assert from 'node:assert/strict';

const listeners={};
const local={};
const session={};
let injections=[];
let currentDoc='doc-1';
let url='https://www.zhipin.com/web/chat/recommend';
let greetCount=0;
let chatSendCount=0;
let loginOnSecondInspect=false;
let inspectCount=0;
const clone=value=>structuredClone(value);
function storage(values) { return {async get(keys){ return clone(values); },async set(value){Object.assign(values,value);}}; }
globalThis.chrome={
 runtime:{id:'a'.repeat(32),onMessage:{addListener(fn){listeners.message=fn;}},onStartup:{addListener(){}}},
 storage:{local:storage(local),session:storage(session)},
 alarms:{create(){},onAlarm:{addListener(){}}},
 tabs:{async query(){return [{id:12,url}];},async get(id){assert.equal(id,12); return {id,url};}},
 scripting:{async executeScript(options){
   injections.push(options);
   const [operation,args]=options.args;
   if(operation==='inspect') { inspectCount++; return [{frameId:0,documentId:currentDoc,result:{url,content:true,login:loginOnSecondInspect && inspectCount >= 2,verify:false,name:'Fixture',company:''}}]; }
   if(operation==='cards') return [{frameId:0,documentId:currentDoc,result:[{geek_id:'g1',name:'Fixture'}]}];
   if(operation==='locate') return [{frameId:0,documentId:currentDoc,result:1}];
   if(operation==='greet') { assert.deepEqual(options.target.documentIds,[currentDoc]); assert.ok(args.deadline>Date.now()); greetCount++;return [{result:true}]; }
   if(operation==='chat_preview') return [{frameId:0,documentId:currentDoc,result:{token:'fixture-token',name:'Fixture',conversation_id:'p1'}}];
   if(operation==='chat_send') { assert.deepEqual(options.target.documentIds,[currentDoc]); chatSendCount++; return [{result:{status:'observed'}}]; }
   if(operation==='scroll') return [{result:true}];
   throw Error('unexpected operation');
 }}
};
const intervals=[];
globalThis.setInterval=(fn,ms)=>{intervals.push({fn,ms});return intervals.length;};
globalThis.clearInterval=()=>{};
class FakeWebSocket {
 static OPEN=1; static CONNECTING=0;
 constructor(address){this.address=address;this.readyState=0;this.sent=[];FakeWebSocket.last=this;}
 send(value){this.sent.push(JSON.parse(value));}
 close(){this.readyState=3;this.onclose?.({code:1000});}
}
globalThis.WebSocket=FakeWebSocket;
await import('../worker.js');
const flush=()=>new Promise(resolve=>setTimeout(resolve,5));
async function message(value){return await new Promise(resolve=>listeners.message(value,{id:chrome.runtime.id},resolve));}
async function command(ws,id,operation,target='12:doc-1',args={},deadline=Date.now()+8000){
 ws.onmessage({data:JSON.stringify({id,operation,target,args,deadline})});
 for(let i=0;i<100;i++){const response=ws.sent.find(v=>v.id===id);if(response)return response;await flush();}
 throw Error('No response');
}

test('existing-tab extension flow; no browser launch API available',async()=>{
 await flush();
 assert.equal(FakeWebSocket.last,undefined);
 assert.equal((await message({type:'connect',token:'test-pairing-token-long-enough'})).ok,true);
 const ws=FakeWebSocket.last;
 assert.equal(ws.address,'ws://127.0.0.1:8000/api/browser-extension/ws');
 ws.readyState=1;ws.onopen();
 assert.equal(ws.sent[0].type,'hello');
 assert.equal(intervals[0].ms,20000);
 const discover=await command(ws,'1','discover');
 assert.equal(discover.result[0].state,'logged_in');
 assert.equal(discover.result[0].target_id,'12:doc-1');
 assert.equal(greetCount,0);
 const cards=await command(ws,'2','cards');
 assert.equal(cards.result[0].geek_id,'g1');
 assert.equal(greetCount,0);
 const greeting=await command(ws,'3','greet','12:doc-1',{geek_id:'g1'});
 assert.equal(greeting.result,true);
 assert.equal(greetCount,1);
 // Replay exact command id: cached result, never another send.
 ws.onmessage({data:JSON.stringify({id:'3',operation:'greet',target:'12:doc-1',args:{geek_id:'g1'},deadline:Date.now()+8000})});
 await flush();assert.equal(greetCount,1);
 currentDoc='doc-new';
 const replaced=await command(ws,'4','greet','12:doc-1',{geek_id:'g1'});
 assert.match(replaced.error,/刷新|跳转/);assert.equal(greetCount,1);
 currentDoc='doc-1';
 const expired=await command(ws,'5','greet','12:doc-1',{geek_id:'g1'},Date.now()-1);
 assert.match(expired.error,/过期/);assert.equal(greetCount,1);
 loginOnSecondInspect=true;inspectCount=0;
 const loginRace=await command(ws,'login-race','greet','12:doc-1',{geek_id:'g1'});
 assert.match(loginRace.error,/未登录|验证/);assert.equal(greetCount,1,'rechecked login state must block sending');
 loginOnSecondInspect=false;
 url='https://www.zhipin.com/web/chat/index';
 const preview=await command(ws,'chat-preview','chat_preview');
 assert.equal(preview.result.frame_document,currentDoc);
 assert.equal(chatSendCount,0);
 const sent=await command(ws,'chat-send','chat_send','12:doc-1',{token:'fixture-token',frame_document:currentDoc,message:'test'});
 assert.equal(sent.result.status,'observed');assert.equal(chatSendCount,1);
 loginOnSecondInspect=true;inspectCount=0;
 const blocked=await command(ws,'chat-login-race','chat_send','12:doc-1',{token:'fixture-token',frame_document:currentDoc,message:'test'});
 assert.match(blocked.error,/聊天会话/);assert.equal(chatSendCount,1);
 loginOnSecondInspect=false;
 url='https://evil.test/';
 const foreign=await command(ws,'6','cards');assert.match(foreign.error,/离开 BOSS/);
 url='https://www.zhipin.com/web/chat/recommend';
 const unsupported=await command(ws,'7','eval');assert.match(unsupported.error,/不支持/);
 ws.onmessage({data:JSON.stringify({id:'disconnect-race',operation:'greet',target:'12:doc-1',args:{geek_id:'g1'},deadline:Date.now()+8000})});
 assert.equal((await message({type:'disconnect'})).ok,true);
 await flush();
 assert.equal(greetCount,1,'queued commands must not run after disconnect');
 assert.equal(local.enabled,false);
});
