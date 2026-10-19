import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../resume-tap.js',import.meta.url),'utf8');

function page(pathname) {
  const calls=[];
  const listeners=new Map();
  const childWindow={};
  class Context2D {
    constructor(canvas){this.canvas=canvas;}
    fillText(...args){calls.push(args);return 'drawn';}
  }
  const sandbox={location:{origin:'https://www.zhipin.com',pathname},JSON:Object.create(JSON),
    CanvasRenderingContext2D:Context2D,Date,Reflect,WeakSet,
    addEventListener:(type,callback)=>listeners.set(type,callback),
    document:{querySelectorAll:()=>[{contentWindow:childWindow}]}};
  vm.runInNewContext(source,sandbox);
  return {sandbox,calls,Context2D,listeners,childWindow};
}

test('captures parsed resume data without changing JSON.parse result',()=>{
  const {sandbox}=page('/web/frame/c-resume/');
  const value=sandbox.JSON.parse('{"geekDetailInfo":{"geekWorkExpList":[{"company":"Example"}]}}');
  assert.equal(value.geekDetailInfo.geekWorkExpList[0].company,'Example');
  assert.equal(sandbox.__bossResumeTap.details.length,1);
  assert.equal(sandbox.__bossResumeTap.details[0].value.geekWorkExpList.length,1);
});

test('records text actually drawn on the resume canvas and preserves drawing',()=>{
  const {sandbox,calls,Context2D}=page('/web/frame/c-resume/');
  const context=new Context2D({width:1044,height:1734});
  assert.equal(context.fillText('work experience',10,20),'drawn');
  assert.equal(calls.length,1);
  assert.equal(sandbox.__bossResumeTap.drawnText[0].text,'work experience');
});

test('does nothing outside the two expected BOSS frames',()=>{
  const {sandbox}=page('/web/chat/index');
  assert.equal(sandbox.__bossResumeTap,undefined);
});

test('captures same-origin c-resume completion message without changing it',()=>{
  const {sandbox,listeners,childWindow}=page('/web/frame/recommend/');
  const payload={type:'IFRAME_DONE',data:{abstractData:{geekDetailInfo:{geekWorkExpList:[{company:'Example'}]}}}};
  listeners.get('message')({origin:'https://www.zhipin.com',source:childWindow,data:payload});
  assert.equal(sandbox.__bossResumeTap.messages.length,1);
  assert.equal(sandbox.__bossResumeTap.messages[0].data.abstractData.geekDetailInfo.geekWorkExpList[0].company,'Example');
  assert.equal(payload.data.abstractData.geekDetailInfo.geekWorkExpList[0].company,'Example');
});

test('ignores unrelated message sources and origins, and records WASM errors',()=>{
  const {sandbox,listeners,childWindow}=page('/web/frame/recommend/');
  const dispatch=listeners.get('message');
  const error={type:'WASM_ERROR',data:{message:'render failed'}};
  dispatch({origin:'https://attacker.example',source:childWindow,data:error});
  dispatch({origin:'https://www.zhipin.com',source:{},data:error});
  dispatch({origin:'https://www.zhipin.com',source:childWindow,data:{type:'OTHER',data:{}}});
  assert.equal(sandbox.__bossResumeTap.messages.length,0);
  dispatch({origin:'https://www.zhipin.com',source:childWindow,data:error});
  assert.equal(sandbox.__bossResumeTap.messages[0].data.message,'render failed');
});
