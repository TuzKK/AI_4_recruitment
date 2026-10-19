import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import ts from 'typescript';
const source=(await fs.readFile(new URL('../src/api/client.ts',import.meta.url),'utf8')).replace('import.meta.env.VITE_API_BASE_URL','undefined');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
const client=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
const timers=[];
globalThis.window={setTimeout(fn,ms){timers.push(ms);return 1;},clearTimeout(){}};
test('AI analysis has a longer request deadline than normal API calls',async()=>{
 globalThis.fetch=async()=>new Response('{}',{status:200,headers:{'content-type':'application/json'}});
 await client.analyzePosition('test','');
 assert.equal(timers.at(-1),120000);
 await client.api.get('/api/health');
 assert.equal(timers.at(-1),15000);
});
test('API error shows the actionable detail, not serialized JSON',async()=>{
 globalThis.fetch=async()=>new Response(JSON.stringify({detail:'模型服务连接超时'}),{status:504,headers:{'content-type':'application/json'}});
 await assert.rejects(client.analyzePosition('test',''),error=>error.message==='模型服务连接超时');
});
