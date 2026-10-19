import test from 'node:test';
import assert from 'node:assert/strict';
import {isBossUrl, classify, validateApi, parseTarget} from '../protocol.mjs';

test('strict origin checks', () => {
  assert.equal(isBossUrl('https://www.zhipin.com/web/chat/index'), true);
  assert.equal(isBossUrl('https://www.zhipin.com.evil.test/'), false);
  assert.equal(isBossUrl('http://www.zhipin.com/'), false);
});
test('URL alone does not prove logged in', () => {
  assert.equal(classify('https://www.zhipin.com/web/chat/index', [{}]), 'unknown');
  assert.equal(classify('https://www.zhipin.com/web/chat/index', [{content:true}]), 'logged_in');
  assert.equal(classify('https://www.zhipin.com/web/chat/index', [{content:true,verify:true}]), 'verification_required');
  assert.equal(classify('https://www.zhipin.com/web/geek/index', [{content:true}]), 'wrong_role');
});
test('only exact API paths and methods', () => {
  validateApi({method:'POST',path:'/wapi/zprelation/friend/filterByLabel'});
  assert.throws(() => validateApi({method:'GET',path:'https://evil.test'}));
  assert.throws(() => validateApi({method:'GET',path:'/wapi/zpchat/fastReply/sendReplyMsg'}));
});
test('target includes document identity', () => {
  assert.deepEqual(parseTarget('12:doc-id'), {tabId:12,documentId:'doc-id'});
  assert.throws(() => parseTarget('12'));
});
