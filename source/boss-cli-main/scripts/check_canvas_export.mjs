// Isolated browser fixture; never connects to the user's Chrome.
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
import {resumeCanvasPage} from '../chrome-extension/canvas.mjs';

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const {chromium}=await import(pathToFileURL(path.join(root,'.venv/Lib/site-packages/playwright/driver/package/index.mjs')).href);
const browser=await chromium.launch({channel:'chrome',headless:true});
try {
 const page=await browser.newPage();
 await page.route('https://www.zhipin.com/web/frame/c-resume/',route=>route.fulfill({contentType:'text/html',body:`
 <canvas width="400" height="600"></canvas><canvas width="400" height="600"></canvas>
 <script>for(const [i,c] of [...document.querySelectorAll('canvas')].entries()){
 const x=c.getContext('2d');x.fillStyle='white';x.fillRect(0,0,400,600);
 x.fillStyle='black';x.font='22px Arial';for(let line=0;line<18;line++)x.fillText('Resume '+i+' line '+line,20,30+line*30);}</script>`}));
 await page.goto('https://www.zhipin.com/web/frame/c-resume/');
 const run=(action,index,identity=null,deadlineMs=5000)=>page.evaluate(async ({source,args})=>{const fn=eval('('+source+')');return fn(args);},
   {source:resumeCanvasPage.toString(),args:[action,index,Date.now()+deadlineMs,identity]});
 const meta=await run('inspect',null);
 assert.equal(meta.canvas_count,2);
 assert.deepEqual(meta.canvases.map(x=>[x.width,x.height]),[[400,600],[400,600]]);
 const first=await run('image',0,meta.identity),second=await run('image',1,meta.identity);
 assert.equal(first.canvas_count,2);
 assert.notEqual(first.png,second.png);
 assert.ok(Buffer.from(first.png,'base64').subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])));
 await assert.rejects(run('image',2,meta.identity),/页码无效/);
 await page.evaluate(()=>{const x=document.querySelector('canvas').getContext('2d');x.fillStyle='black';x.fillRect(20,40,200,200);});
 await assert.rejects(run('image',1,meta.identity),/内容或简历身份已变化/);
 await page.evaluate(()=>{const c=document.querySelector('canvas');c.width=300;c.height=150;});
 const placeholder=await run('inspect',null,null,500);
 assert.equal(placeholder.initialized,false);
 await assert.rejects(run('image',0,meta.identity),/内容或简历身份已变化/);
 const diagnostic=await run('diagnostic',0);
 assert.equal(diagnostic.canvas.width,300);
 assert.ok(Buffer.from(diagnostic.png,'base64').subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])));
 await page.evaluate(()=>{const c=document.querySelector('canvas');c.width=400;c.height=600;
   const x=c.getContext('2d');x.fillStyle='white';x.fillRect(0,0,400,600);});
 const blank=await run('inspect',null,null,500);
 assert.equal(blank.initialized,false);
 console.log(JSON.stringify({ok:true,canvases:meta.canvas_count,first_bytes:Buffer.from(first.png,'base64').length}));
} finally {await browser.close();}
