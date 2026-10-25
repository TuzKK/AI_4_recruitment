import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
const code=await readFile(new URL('../rate-observer.js',import.meta.url),'utf8');
test('passive fetch observer preserves response and records only limit metadata',async()=>{
  const response=new Response(JSON.stringify({code:9,private_data:'not retained'}),{headers:{'Content-Type':'application/json','Retry-After':'180'}});
  const context=vm.createContext({URL,Date,JSON,location:{protocol:'https:',hostname:'www.zhipin.com',href:'https://www.zhipin.com/web/chat/index'},fetch:async()=>response});
  vm.runInContext(code,context);
  const received=await context.fetch('/wapi/test');
  assert.equal(received,response);
  for(let i=0;i<20&&!context.__bossRateLimitSignal;i++)await new Promise(r=>setTimeout(r,5));
  assert.equal(context.__bossRateLimitSignal.code,9);
  assert.equal(context.__bossRateLimitSignal.retry_after,'180');
  assert.equal(context.__bossRateLimitSignal.private_data,undefined);
});
test('XHR 429 is observed without replacing the original return value',()=>{
  class XHR {open(){return 123;}addEventListener(_name,fn){this.listener=fn;}getResponseHeader(){return '240';}}
  const context=vm.createContext({URL,Date,JSON,XMLHttpRequest:XHR,location:{protocol:'https:',hostname:'www.zhipin.com',href:'https://www.zhipin.com/'}});
  vm.runInContext(code,context);
  const xhr=new context.XMLHttpRequest();assert.equal(xhr.open('GET','/wapi/test'),123);
  xhr.status=429;xhr.listener();
  assert.equal(context.__bossRateLimitSignal.status,429);
  assert.equal(context.__bossRateLimitSignal.retry_after,'240');
  const longest=context.__bossRateLimitSignal.cooldown_until;
  const at=context.__bossRateLimitSignal.at;
  xhr.getResponseHeader=()=>null;xhr.listener();
  assert.equal(context.__bossRateLimitSignal.cooldown_until,longest);
  assert.ok(context.__bossRateLimitSignal.at>at);
});
