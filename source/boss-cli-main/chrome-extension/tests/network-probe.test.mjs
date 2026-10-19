import test from 'node:test';
import assert from 'node:assert/strict';
import {createNetworkProbe} from '../network-probe.mjs';

function fakeChrome() {
  const listeners=[];
  const events={addListener(fn){listeners.push(fn);}};
  const commands=[];
  return {
    commands,
    emit(method,params){for(const fn of listeners) fn({tabId:7},method,params);},
    debugger:{
      onEvent:events,
      onDetach:{addListener(){}},
      attach:async()=>{}, detach:async()=>{},
      sendCommand:async(_target,method,params)=>{
        commands.push([method,params]);
        if(method==='Network.getResponseBody') return {body:'{"code":0,"zpData":{"resume":"example"}}',base64Encoded:false};
        return {};
      }
    }
  };
}

test('collects only same-origin JSON responses and stops cleanly',async()=>{
  const chrome=fakeChrome();
  const probe=createNetworkProbe(chrome);
  await probe.start(7,'candidate-1');
  chrome.emit('Network.responseReceived',{requestId:'1',type:'XHR',response:{url:'https://www.zhipin.com/wapi/profile?x=1',mimeType:'application/json',status:200}});
  chrome.emit('Network.loadingFinished',{requestId:'1'});
  chrome.emit('Network.responseReceived',{requestId:'2',type:'XHR',response:{url:'https://other.example/private',mimeType:'application/json',status:200}});
  chrome.emit('Network.loadingFinished',{requestId:'2'});
  const result=await probe.stop(7,'candidate-1');
  assert.equal(result.responses.length,1);
  assert.equal(result.responses[0].path,'/wapi/profile');
  assert.match(result.responses[0].body,/resume/);
  assert.equal(chrome.commands.filter(([name])=>name==='Network.getResponseBody').length,1);
  assert.ok(chrome.commands.some(([name])=>name==='Network.disable'));
});

test('rejects a different candidate and does not release the session',async()=>{
  const chrome=fakeChrome();
  const probe=createNetworkProbe(chrome);
  await probe.start(7,'candidate-1');
  await assert.rejects(probe.stop(7,'candidate-2'),/身份/);
  await probe.stop(7,'candidate-1');
});
