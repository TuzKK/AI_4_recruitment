import test from 'node:test';
import assert from 'node:assert/strict';
import {pageOperation} from '../../source/boss-cli-main/chrome-extension/page.mjs';

test('advance scrolls only the recommendation card container',async()=>{
  globalThis.location={protocol:'https:',hostname:'www.zhipin.com',pathname:'/web/frame/recommend/'};
  let calls=0;
  const container={clientHeight:500,scrollHeight:2000,scrollTop:0,parentElement:null,
    scrollTo({top}){calls++;this.scrollTop=top;}};
  const card={parentElement:container,getClientRects:()=>[1],
    getAttribute:()=> 'c1',querySelector:()=>({textContent:'candidate'}),
    innerText:'A candidate card containing enough readable content'};
  globalThis.getComputedStyle=()=>({overflowY:'auto'});
  globalThis.document={querySelectorAll:()=>[card],scrollingElement:container};
  const rows=await pageOperation('cards',{advance:true},Date.now()+3000);
  assert.equal(calls,1);
  assert.equal(container.scrollTop,2000);
  assert.equal(rows[0].geek_id,'c1');
});

test('advance never scrolls a resume frame or chat history',async()=>{
  location.pathname='/web/chat/index';
  let calls=0;
  document.scrollingElement={scrollTo(){calls++;}};
  assert.deepEqual(await pageOperation('cards',{advance:true},Date.now()+3000),[]);
  assert.equal(calls,0);
});

test('preparing cards closes only a unique visible resume dialog close control',async()=>{
  location.pathname='/web/frame/recommend/';
  let closed=0;
  const button={getClientRects:()=>[1],click(){closed++;}};
  const modal={getClientRects:()=>[1],closest:()=>null,querySelectorAll:()=>[button]};
  document.querySelectorAll=selector=>selector.includes('.boss-dialog__body')?[modal]:[];
  await pageOperation('cards',{close_profile:true},Date.now()+3000);
  assert.equal(closed,1);
});

test('ambiguous close controls are never clicked',async()=>{
  let closed=0;
  const button={getClientRects:()=>[1],click(){closed++;}};
  const modal={getClientRects:()=>[1],closest:()=>null,querySelectorAll:()=>[button,{...button}]};
  document.querySelectorAll=selector=>selector.includes('.boss-dialog__body')?[modal]:[];
  await assert.rejects(pageOperation('cards',{close_profile:true},Date.now()+3000));
  assert.equal(closed,0);
});

test('document scroll uses scrollingElement when BODY reports overflow',async()=>{
  let bodyScrolls=0,documentScrolls=0;
  const body={clientHeight:500,scrollHeight:2000,parentElement:null,scrollTo(){bodyScrolls++;}};
  const root={scrollHeight:2000,scrollTo(){documentScrolls++;}};
  const card={parentElement:body,getClientRects:()=>[1],getAttribute:()=> 'c1',
    querySelector:()=>({textContent:'candidate'}),innerText:'A candidate card containing enough readable content'};
  document={body,scrollingElement:root,querySelectorAll:()=>[card]};
  await pageOperation('cards',{advance:true},Date.now()+3000);
  assert.equal(bodyScrolls,0);
  assert.equal(documentScrolls,1);
});
