import test from 'node:test';
import assert from 'node:assert/strict';
import {foregroundTarget} from '../foreground.mjs';

test('restores the selected BOSS tab and minimized window for rendering',async()=>{
  const calls=[];
  const chrome={
    tabs:{get:async()=>({active:false,windowId:7}),update:async(id,args)=>calls.push(['tab',id,args])},
    windows:{get:async()=>({focused:false,state:'minimized'}),update:async(id,args)=>calls.push(['window',id,args])}
  };
  await foregroundTarget(chrome,12);
  assert.deepEqual(calls,[['tab',12,{active:true}],['window',7,{focused:true,state:'normal'}]]);
});

test('already visible target does not switch tabs or windows',async()=>{
  const chrome={
    tabs:{get:async()=>({active:true,windowId:7}),update:async()=>assert.fail('unexpected tab change')},
    windows:{get:async()=>({focused:true,state:'normal'}),update:async()=>assert.fail('unexpected window change')}
  };
  await foregroundTarget(chrome,12);
});
