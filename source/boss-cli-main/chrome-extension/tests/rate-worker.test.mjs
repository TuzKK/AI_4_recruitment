import test from 'node:test';
import assert from 'node:assert/strict';
let now=100000;
const saved={},requests=[];
const originalNow=Date.now,originalTimeout=globalThis.setTimeout;
Date.now=()=>now;
globalThis.setTimeout=(fn,ms)=>{now+=ms;queueMicrotask(fn);return 0;};
globalThis.chrome={
  storage:{local:{get:async()=>({enabled:false,...saved}),set:async v=>Object.assign(saved,v)},session:{set:async()=>{}}},
  runtime:{onMessage:{addListener(){}},onStartup:{addListener(){}}},alarms:{onAlarm:{addListener(){}}},
  tabs:{get:async()=>({url:'https://www.zhipin.com/web/chat/index'})},
  scripting:{executeScript:async input=>{
    if(input.files || input.func?.name==='rateSignalPage')return [];
    const {args}=input;
    if(args[0]==='inspect')return [{frameId:0,documentId:'doc',result:{content:true,account:'boss'}}];
    assert.equal(args[0],'api');requests.push(now);
    return [{result:{status:200,body:{code:0,zpData:{userInfo:{uid:123}}}}}];
  }}
};
const {execute}=await import('../worker.mjs');
test('business API and both account checks share the same limiter',async()=>{
  try {
    const key=[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode('uid:123')))].map(x=>x.toString(16).padStart(2,'0')).join('');
    await execute({id:'one',operation:'api',target:'1:doc',deadline:220000,args:{method:'GET',path:'/wapi/zpuser/wap/getUserInfo.json',account_key:key}});
    assert.deepEqual(requests,[100000,105000,110000]);
  } finally {Date.now=originalNow;globalThis.setTimeout=originalTimeout;}
});
