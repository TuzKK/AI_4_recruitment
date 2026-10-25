import test from 'node:test';
import assert from 'node:assert/strict';
import {singleExecutionResult} from '../execution-result.mjs';

test('script errors and missing results cannot become an empty success',()=>{
  assert.throws(()=>singleExecutionResult([{error:{message:'button blocked'}}],'greet'),/button blocked/);
  assert.throws(()=>singleExecutionResult([{}],'greet'),/未返回/);
  assert.throws(()=>singleExecutionResult([],'greet'),/缺失/);
});
test('structured pre-click rejection survives the extension boundary',()=>{
  const result={status:'not_sent',error:'no button',clicked:false};
  assert.equal(singleExecutionResult([{result}],'greet'),result);
});
