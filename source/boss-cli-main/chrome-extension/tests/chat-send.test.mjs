import test from 'node:test';
import assert from 'node:assert/strict';
import {pageOperation} from '../page.mjs';

const calls=[];
globalThis.location={protocol:'https:',hostname:'www.zhipin.com',pathname:'/web/chat/index'};
globalThis.window=globalThis;
globalThis.top=globalThis;
globalThis.document={querySelectorAll:()=>[]};
globalThis.iBossRoot={chat:{sendMessage:async function getFriendById(...args){calls.push(args)}}};

test('chat send invokes native client once with the bound recipient',async()=>{
  const args={uid:123,encrypt_uid:'abcdefghijklmnop',friend_source:0,message:'您好，方便介绍一下项目吗？'};
  const result=await pageOperation('chat_send',args,Date.now()+5000);
  assert.equal(result.invoked,true);
  assert.deepEqual(calls,[[args.message,'text',{uid:123,encryptUid:'abcdefghijklmnop',friendSource:0}]]);
});

test('invalid recipient never invokes native client',async()=>{
  await assert.rejects(pageOperation('chat_send',{uid:0,encrypt_uid:'bad',friend_source:0,message:'您好'},Date.now()+5000),/无效/);
  assert.equal(calls.length,1);
});
