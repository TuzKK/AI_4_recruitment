import test from 'node:test';
import assert from 'node:assert/strict';
import {validateCapture, screenshotClip} from '../capture.mjs';

test('capture rejects arbitrary scripts and unbounded scroll arguments',()=>{
 assert.throws(()=>validateCapture({action:'evaluate',script:'alert(1)'}));
 assert.throws(()=>validateCapture({action:'step',capture_id:'abc',top:-1}));
 validateCapture({action:'step',capture_id:'abc',top:400});
});
test('clip maps iframe viewport without capturing surrounding list',()=>{
 assert.deepEqual(screenshotClip({x:10,y:20,width:500,height:300},{x:100,y:200}, {width:1440,height:1000}),
 {x:110,y:220,width:500,height:300,scale:1});
 assert.throws(()=>screenshotClip({x:0,y:0,width:0,height:300},{x:0,y:0},{width:1440,height:1000}));
 assert.throws(()=>screenshotClip({x:0,y:0,width:500,height:300},{x:1000,y:0},{width:1440,height:1000}));
});

import {transitioned} from '../capture.mjs';
test('unchanged previous resume never belongs to next requested candidate',()=>{
 const old={frameId:2,documentId:'doc',result:{identifiable:true,key:'old'}};
 assert.equal(transitioned([old],old),false);
 assert.equal(transitioned([old],{...old,result:{identifiable:true,key:'new'}}),false);
 assert.equal(transitioned([old],{...old,documentId:'new-doc'}),false);
 assert.equal(transitioned([],{...old,result:{identifiable:false}}),false);
 assert.equal(transitioned([],old),true);
});

import {diagnosticClip} from '../capture.mjs';
test('diagnostic crop preserves only visible pixels and never labels it full',()=>{
 const result=diagnosticClip({x:100,y:200,width:522,height:891},[{x:0,y:0,width:1440,height:900}]);
 assert.equal(result.cropped,true);
 assert.deepEqual(result.clip,{x:100,y:200,width:522,height:700,scale:1});
 assert.throws(()=>diagnosticClip({x:2000,y:0,width:100,height:100},[{x:0,y:0,width:1440,height:900}]));
});
