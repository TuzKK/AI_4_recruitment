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
  const result=await pageOperation('greet',{geek_id:'c2'},Date.now()+3000);
  assert.equal(result.status,'not_sent');
  assert.match(result.error,/缺失|重复/);
  assert.equal(clicked,1);
});

test('greet supports the recommendation iframe and clicks exactly once',async()=>{
  for (const path of ['/web/frame/recommend/', '/web/frame/recommend']) {
    location.pathname=path;
    contacted=false;
    const before=clicked;
    assert.equal(await pageOperation('locate_greet',{geek_id:'c1'},Date.now()+3000),1);
    const result=await pageOperation('greet',{geek_id:'c1'},Date.now()+3000);
    assert.equal(result.status,'observed');
    assert.equal(clicked,before+1);
  }
});

test('unrelated frames are ignored during discovery and cannot greet',async()=>{
  location.pathname='/web/chat/index';
  const before=clicked;
  assert.equal(await pageOperation('locate_greet',{geek_id:'c1'},Date.now()+3000),0);
  assert.equal((await pageOperation('greet',{geek_id:'c1'},Date.now()+3000)).status,'not_sent');
  assert.equal(clicked,before);
});

test('dry-run validates the candidate and never clicks',async()=>{
  location.pathname='/web/frame/recommend/';
  contacted=false;
  const before=clicked;
  const result=await pageOperation('greet',{geek_id:'c1',dry_run:true},Date.now()+3000);
  assert.equal(result.status,'ready');
  assert.equal(result.candidate_id,'c1');
  assert.equal(clicked,before);
});

test('greet supports a labeled DIV action and re-queries a replaced card',async()=>{
  let clicks=0;
  const makeCard=()=>({
    getAttribute:()=> 'c1',getClientRects:()=>[1],
    querySelectorAll:selector=>selector.includes('div')?[{
      tagName:'DIV',className:'btn-greet',textContent:clicks?'继续沟通':'打招呼',
      children:[],getAttribute:()=>null,getClientRects:()=>[1],click(){clicks++;}
    }]:[]
  });
  document.querySelectorAll=selector=>selector==='[data-geekid]'?[makeCard()]:[];
  const result=await pageOperation('greet',{geek_id:'c1'},Date.now()+3000);
  assert.equal(result.status,'observed');
  assert.equal(clicks,1);
});

test('greet finds the action beside the identity-marked content within one card',async()=>{
  let clicks=0;
  const button={tagName:'SPAN',className:'label',children:[],
    get textContent(){return clicks?'继续沟通':'打招呼';},
    getClientRects:()=>[1],getAttribute:()=>null,click(){clicks++;}};
  const card={tagName:'DIV',getAttribute:()=> 'c1',getClientRects:()=>[1],querySelectorAll:()=>[]};
  card.parentElement={tagName:'DIV',className:'candidate-card-wrap',getAttribute:()=>null,
    querySelectorAll:selector=>selector==='[data-geekid]'?[card]:[button]};
  document.querySelectorAll=selector=>selector==='[data-geekid]'?[card]:[];
  const probe=await pageOperation('greet',{geek_id:'c1',dry_run:true},Date.now()+3000);
  assert.equal(probe.status,'ready');
  assert.equal(clicks,0);
  const result=await pageOperation('greet',{geek_id:'c1'},Date.now()+3000);
  assert.equal(result.status,'observed');
  assert.equal(clicks,1);
});

test('greet never borrows a neighboring candidate button',async()=>{
  let clicks=0;
  const card={tagName:'DIV',getAttribute:()=> 'c1',getClientRects:()=>[1],querySelectorAll:()=>[]};
  const other={getAttribute:()=> 'c2'};
  const button={textContent:'打招呼',getClientRects:()=>[1],getAttribute:()=>null,click(){clicks++;}};
  card.parentElement={tagName:'DIV',querySelectorAll:selector=>selector==='[data-geekid]'?[card,other]:[button]};
  document.querySelectorAll=selector=>selector==='[data-geekid]'?[card]:[];
  assert.equal((await pageOperation('greet',{geek_id:'c1'},Date.now()+3000)).status,'not_sent');
  assert.equal(clicks,0);
});
