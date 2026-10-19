import test from 'node:test';
import assert from 'node:assert/strict';
import {pageOperation} from '../../source/boss-cli-main/chrome-extension/page.mjs';

let clicked=0, contacted=false;
const button={textContent:'打招呼',disabled:false,getAttribute:()=>null,getClientRects:()=>[1],click(){clicked++;contacted=true;}};
const card={getAttribute:key=>key==='data-geekid'?'c1':null,getClientRects:()=>[1],
  querySelectorAll:()=>contacted?[{...button,textContent:'继续沟通'}]:[button]};
globalThis.location={protocol:'https:',hostname:'www.zhipin.com',pathname:'/web/chat/recommend'};
globalThis.document={querySelectorAll:selector=>selector==='[data-geekid]'?[card]:[]};

test('greet only one matching visible card and confirms contact state',async()=>{
  assert.equal(await pageOperation('locate_greet',{geek_id:'c1'},Date.now()+3000),1);
  const result=await pageOperation('greet',{geek_id:'c1'},Date.now()+3000);
  assert.equal(result.status,'observed');assert.equal(clicked,1);
});

test('greet rejects an absent candidate without a click',async()=>{
  await assert.rejects(pageOperation('greet',{geek_id:'c2'},Date.now()+3000),/缺失|重复/);
  assert.equal(clicked,1);
});
