import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
test('Chrome debugger is a required permission, never optional',async()=>{
 const manifest=JSON.parse(await readFile(new URL('../manifest.json',import.meta.url),'utf8'));
 assert.ok(manifest.permissions.includes('debugger'));
 assert.ok(!(manifest.optional_permissions||[]).includes('debugger'));
});

test('resume observer runs only in BOSS resume frames at document start',async()=>{
 const manifest=JSON.parse(await readFile(new URL('../manifest.json',import.meta.url),'utf8'));
 const tap=manifest.content_scripts.find(x=>x.js.includes('resume-tap.js'));
 assert.deepEqual(tap.matches,[
  'https://www.zhipin.com/web/frame/recommend/*',
  'https://www.zhipin.com/web/frame/c-resume/*'
 ]);
 assert.equal(tap.world,'MAIN');
 assert.equal(tap.run_at,'document_start');
});
