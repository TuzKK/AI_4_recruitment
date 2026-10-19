// Synthetic browser integration. Never connects to the user's Chrome.
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
import {profileCapture,fitCaptureViewport,capturePage} from '../chrome-extension/capture.mjs';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const {chromium}=await import(pathToFileURL(path.join(root,'.venv/Lib/site-packages/playwright/driver/package/index.mjs')).href);
const browser=await chromium.launch({channel:'chrome',headless:true});
try {
 const page=await browser.newPage({viewport:{width:900,height:600}});
 const child='<body style="margin:0"><canvas style="display:block" width="500" height="2200"></canvas><script>const x=document.querySelector("canvas").getContext("2d");x.fillStyle="white";x.fillRect(0,0,500,2200);x.fillStyle="black";for(let i=0;i<55;i++)x.fillText("Experience "+i,20,i*40+20);</script></body>';
 const host='<style>html,body{height:100%;overflow:hidden}</style><body style="margin:0;overflow:hidden"><div style="height:40px"></div><div class="dialog-lib-resume"><div style="height:580px;min-height:580px;width:500px;overflow:auto"><iframe style="display:block;border:0;width:500px;height:2200px" src="https://fixture.invalid/c-resume"></iframe></div></div></body>';
 await page.route('https://fixture.invalid/c-resume',route=>route.fulfill({body:child,contentType:'text/html'}));
 await page.route('https://fixture.invalid/web/frame/recommend',route=>route.fulfill({body:host,contentType:'text/html'}));
 await page.goto('https://fixture.invalid/web/frame/recommend');
 await page.frameLocator('iframe').locator('canvas').waitFor();
 const cdp=await page.context().newCDPSession(page);
 let loseFitReply=false;
 const chrome={tabs:{get:async()=>({active:false})},permissions:{contains:async()=>true},debugger:{attach:async()=>{},detach:async()=>{},sendCommand:(_target,method,params)=>cdp.send(method,params)},
 scripting:{executeScript:async input=>{
   const results=[];
   for(const [index,frame] of page.frames().entries()){
    const documentId='doc-'+index;
    if(input.target.documentIds&&!input.target.documentIds.includes(documentId))continue;
    const result=await frame.evaluate(async input=>{const fn=eval('('+input.source+')');return await fn(...input.args);},
      {source:input.func.toString(),args:input.args||[]});
    if(loseFitReply&&input.func===fitCaptureViewport){loseFitReply=false;throw Error('Simulated lost fit reply');}
    results.push({frameId:index,documentId,result});
   }
   return results;
 }}};
 const sessions=new Map();
 const call=args=>profileCapture(chrome,1,args,Date.now()+25000,sessions,[]);
 const original=await page.locator('.dialog-lib-resume > div').getAttribute('style');
 const prepared=await call({action:'prepare'});
 const capture_id=prepared.capture_id;
 const initial=await call({action:'step',capture_id,top:0});
 assert.equal(initial.cropped,true);
 assert.equal(initial.can_fit_viewport,true);
 const fit=await call({action:'fit',capture_id});
 assert.equal(fit.height,560);
 const output=path.join(root,'.runtime','capture-controller-fixture');await mkdir(output,{recursive:true});
 let top=0,count=0,last;
 while(count<20){
   last=await call({action:'step',capture_id,top});
   assert.equal(last.cropped,false);
   assert.equal(last.unstable,false);
   assert.equal(last.nested_scroll_uncovered,false);
   await writeFile(path.join(output,'segment-'+count+'.png'),Buffer.from(last.png,'base64'));
   count++;
   if(last.top+last.height>=last.total-2)break;
   top=Math.min(last.total-last.height,last.top+Math.floor(last.height*.8));
 }
 assert.ok(count>=5&&count<20);
 assert.equal(last.top+last.height,last.total);
 await call({action:'release',capture_id});
 assert.equal(await page.locator('.dialog-lib-resume > div').getAttribute('style'),original);
 const retry=await call({action:'prepare'});
 await call({action:'step',capture_id:retry.capture_id,top:0});
 loseFitReply=true;
 await assert.rejects(call({action:'fit',capture_id:retry.capture_id}),/lost fit reply/);
 assert.equal(await page.locator('.dialog-lib-resume > div').getAttribute('style'),original);
 await call({action:'release',capture_id:retry.capture_id});
 // Simulate a stopped extension worker after CSS mutation; next prepare repairs it.
 await page.evaluate(async ({source,args})=>{const fn=eval('('+source+')');return fn(args);},{source:fitCaptureViewport.toString(),args:[560,'orphan',Date.now()+5000]});
 assert.notEqual(await page.locator('.dialog-lib-resume > div').getAttribute('style'),original);
 await page.evaluate(async ({source,args})=>{const fn=eval('('+source+')');return fn(...args);},{source:capturePage.toString(),args:['prepare',null,Date.now()+5000]});
 assert.equal(await page.locator('.dialog-lib-resume > div').getAttribute('style'),original);
 console.log(JSON.stringify({ok:true,segments:count,total:last.total,viewport:last.height,restored:true,output}));
} finally {await browser.close();}
