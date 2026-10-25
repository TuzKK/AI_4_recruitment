import test from 'node:test';
import assert from 'node:assert/strict';
let currentUrl='https://www.zhipin.com/web/chat/index';
let navigations=0;
const key=[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode('uid:123')))].map(x=>x.toString(16).padStart(2,'0')).join('');
globalThis.chrome={storage:{local:{get:async()=>({enabled:false}),set:async()=>{}},session:{set:async()=>{},get:async()=>({})}},
  runtime:{onMessage:{addListener(){}},onStartup:{addListener(){}}},alarms:{onAlarm:{addListener(){}}},
  tabs:{get:async()=>({url:currentUrl}),update:async(_id,{url})=>{currentUrl=url;navigations++;}},
  scripting:{executeScript:async input=>{
    if(input.files || input.func?.name==='rateSignalPage')return [];
    const {args}=input;
    if(args[0]==='inspect') return [{frameId:0,documentId:'doc',result:{content:true}}];
    if(args[0]==='api') return [{result:{status:200,body:{code:0,zpData:{userInfo:{uid:123}}}}}];
    return [];
  }}
};
const {execute}=await import('../worker.mjs');
test('CLI navigation uses only fixed BOSS pages and retains account binding',async()=>{
  const result=await execute({operation:'navigate',target:'1:doc',deadline:Date.now()+10000,args:{page:'recommend',account_key:key}});
  assert.equal(currentUrl,'https://www.zhipin.com/web/chat/recommend');
  assert.equal(result.account_key,key);
  assert.equal(navigations,1);
  await assert.rejects(execute({operation:'navigate',target:'1:doc',deadline:Date.now()+10000,args:{page:'https://evil.test',account_key:key}}));
  assert.equal(navigations,1);
});
