import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import ts from 'typescript';
const source=await fs.readFile(new URL('../src/state/taskDraft.ts',import.meta.url),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
let counter=0;
async function load(storage){
 globalThis.window={localStorage:storage};
 return import('data:text/javascript;base64,'+Buffer.from(code).toString('base64')+'#'+counter++);
}
function memory(){const values=new Map();return {getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v)};}
const analysis={position_id:7,title:'Engineer',jd:{title:'Engineer',responsibilities:[],requirements:[]},keywords:{},filters:{},scorecard:{}};
test('fields, analysis and step survive a fresh module/page load',async()=>{
 const storage=memory();const first=await load(storage);
 first.updateTaskDraft({title:'Engineer',description:'Details',accountId:'2',dailyLimit:35,threshold:80,startHour:'10:00',endHour:'17:00'});
 first.updateTaskDraft({analysis,editableKeywords:['Python'],newKeyword:'RAG',step:2});
 first.setAnalysisPending(true);
 const restored=(await load(storage)).getTaskDraftSnapshot();
 assert.equal(restored.draft.title,'Engineer');assert.equal(restored.draft.description,'Details');
 assert.equal(restored.draft.accountId,'2');assert.equal(restored.draft.dailyLimit,35);
 assert.equal(restored.draft.threshold,80);assert.equal(restored.draft.startHour,'10:00');
 assert.equal(restored.draft.endHour,'17:00');assert.equal(restored.draft.step,2);
 assert.equal(restored.draft.analysis.position_id,7);assert.deepEqual(restored.draft.editableKeywords,['Python']);
 assert.equal(restored.draft.newKeyword,'RAG');assert.equal(restored.analysisPending,false);
});
test('changing job input invalidates old analysis, reset clears persisted form',async()=>{
 const storage=memory(),store=await load(storage);
 store.updateTaskDraft({title:'Engineer'});store.updateTaskDraft({analysis,step:3,editableKeywords:['Python']});
 store.updateTaskDraft({description:'Changed'});
 assert.equal(store.getTaskDraftSnapshot().draft.analysis,null);assert.equal(store.getTaskDraftSnapshot().draft.step,0);
 store.resetTaskDraft();
 assert.equal((await load(storage)).getTaskDraftSnapshot().draft.title,'');
});
test('corrupt draft and blocked storage do not crash the form',async()=>{
 const corrupt=await load({getItem:()=>'{broken',setItem(){}});
 assert.equal(corrupt.getTaskDraftSnapshot().draft.title,'');
 const blocked=await load({getItem(){throw Error('blocked');},setItem(){throw Error('blocked');}});
 blocked.updateTaskDraft({title:'Still editable'});
 assert.equal(blocked.getTaskDraftSnapshot().draft.title,'Still editable');
 assert.ok(blocked.getTaskDraftSnapshot().storageError);
});
