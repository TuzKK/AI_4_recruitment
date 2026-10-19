import assert from 'node:assert/strict';
import test from 'node:test';
import {captureCanvasSegment} from '../canvas-segment.mjs';
import {capturePage} from '../capture.mjs';
import {resumeCanvasPage} from '../canvas.mjs';

function fixture({switchAtEnd=false,changedTotal=false}={}) {
 let top=0,baselineReads=0;
 const chrome={scripting:{executeScript:async ({func,args})=>{
   if(func===capturePage) {
     top=args[1];
     return [{result:{top,height:600,total:changedTotal&&top?1300:1200,frame_url:'https://www.zhipin.com/web/frame/recommend/'}}];
   }
   assert.equal(func,resumeCanvasPage);
   const [action,, ,expected]=args[0];
   if(top===0&&action==='inspect') baselineReads++;
   const identity=top===0?(switchAtEnd&&baselineReads>1?'changed':'baseline'):'scroll-300';
   const result=action==='inspect'?{initialized:true,canvas_count:1,identity}:
     {canvas_count:1,identity:expected,canvas:{width:1000,height:1100,css_height:550},png:'cG5n'};
   return [{documentId:'resume-doc',result}];
 }}};
 return {chrome,getTop:()=>top};
}
const session={tabId:8,documentId:'host-doc',frameUrl:'https://www.zhipin.com/web/frame/recommend/',
  initial:{height:600,total:1200}};
const binding={documentId:'resume-doc',identity:'baseline'};

test('exports one scrolled Canvas and verifies the original bitmap after restoring top',async()=>{
 const {chrome,getTop}=fixture();
 const result=await captureCanvasSegment(chrome,8,session,binding,300,Date.now()+10000);
 assert.equal(result.top,300);
 assert.equal(result.identity,'scroll-300');
 assert.equal(getTop(),0);
});
test('rejects a candidate switch and restores scroll',async()=>{
 const {chrome,getTop}=fixture({switchAtEnd:true});
 await assert.rejects(captureCanvasSegment(chrome,8,session,binding,300,Date.now()+10000),/顶部画布/);
 assert.equal(getTop(),0);
});
test('rejects a layout change before exporting',async()=>{
 const {chrome,getTop}=fixture({changedTotal:true});
 await assert.rejects(captureCanvasSegment(chrome,8,session,binding,300,Date.now()+10000),/布局已变化/);
 assert.equal(getTop(),0);
});
