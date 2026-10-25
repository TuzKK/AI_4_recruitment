import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {selectAttachmentUrl, fetchAttachmentPage} from '../attachment.mjs';

const makeMessage = (url, overrides={}) => ({
  mid: '123', bizType: 13, from: {uid: 42},
  body: {type: 12, hyperLink: {hyperLinkType: 1, url}}, ...overrides,
});
const fileUrl = 'https://m.zhipin.com/wflow/zpgeek/download/preview4boss?file=abc';
const wrapped = `bosszp://bosszhipin.app/openwith?type=resume&url=${encodeURIComponent(fileUrl)}`;

test('attachment preserves rate limit metadata', async()=>{
  globalThis.location={origin:'https://m.zhipin.com'};
  globalThis.fetch=async()=>new Response('',{status:429,headers:{'Retry-After':'240'}});
  assert.deepEqual(await fetchAttachmentPage(fileUrl,Date.now()+5000),{status:429,retry_after:'240'});
});

test('attachment preserves business rate limit without exposing body data',async()=>{
  globalThis.location={origin:'https://m.zhipin.com'};
  globalThis.fetch=async()=>new Response('{"code":9,"private_data":"ignored"}',{headers:{'Content-Type':'application/json'}});
  assert.deepEqual(await fetchAttachmentPage(fileUrl,Date.now()+5000),{status:200,body:{code:9},retry_after:null});
});

test('selects only the requested candidate attachment and fixed BOSS preview route', () => {
  const messages = [makeMessage(wrapped), makeMessage(wrapped, {mid:'124'})];
  assert.equal(selectAttachmentUrl(messages, 42, '123'), fileUrl);
  assert.throws(() => selectAttachmentUrl(messages, 7, '123'));
  assert.throws(() => selectAttachmentUrl(messages, 42, '125'));
  assert.throws(() => selectAttachmentUrl([makeMessage('https://evil.test/file.pdf')], 42, '123'));
  const evil = 'https://m.zhipin.com.evil.test/wflow/zpgeek/download/preview4boss';
  assert.throws(() => selectAttachmentUrl([makeMessage(`bosszp://bosszhipin.app/openwith?url=${encodeURIComponent(evil)}`)], 42, '123'));
});

test('fetch accepts a real PDF response and returns bounded base64', async () => {
  globalThis.location = {origin:'https://m.zhipin.com'};
  globalThis.fetch = async () => new Response(new Uint8Array([37,80,68,70,45,49,46,55,10,37,37,69,79,70]),
    {status:200,headers:{'Content-Type':'application/pdf'}});
  const result = await fetchAttachmentPage(fileUrl, Date.now()+5000);
  assert.equal(result.bytes, 14);
  assert.equal(Buffer.from(result.base64,'base64').toString('ascii',0,5),'%PDF-');
});

test('fetch rejects JSON login errors and non-PDF data', async () => {
  globalThis.location = {origin:'https://m.zhipin.com'};
  globalThis.fetch = async () => new Response('{"code":7}',
    {status:200,headers:{'Content-Type':'application/json'}});
  await assert.rejects(fetchAttachmentPage(fileUrl, Date.now()+5000), /PDF/);
});

test('fetch function is self-contained when Chrome serializes it', async () => {
  const isolated = vm.runInNewContext(`(${fetchAttachmentPage.toString()})`, {
    location:{origin:'https://m.zhipin.com'},
    fetch:async () => new Response(new Uint8Array([37,80,68,70,45,49,46,55,10,37,37,69,79,70]),
      {status:200,headers:{'Content-Type':'application/pdf'}}),
    Response,AbortSignal,btoa,URL,
  });
  assert.equal((await isolated(fileUrl,Date.now()+5000)).bytes,14);
});
