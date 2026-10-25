import test from 'node:test';
import assert from 'node:assert/strict';
import {BossRateLimiter} from '../rate-limit.mjs';

function fixture(saved={}) {
  let now=100000;
  const storage={async get(){return structuredClone(saved);},async set(value){Object.assign(saved,structuredClone(value));}};
  const limiter=()=>new BossRateLimiter({storage,now:()=>now,sleep:async ms=>{now+=ms;}});
  return {limiter,now:()=>now,advance:ms=>{now+=ms;},saved};
}
test('all concurrent requests serialize and respect start spacing',async()=>{
  const f=fixture(), l=f.limiter(), times=[];
  await Promise.all([1,2,3].map(()=>l.run('request',200000,async()=>times.push(f.now()))));
  assert.deepEqual(times,[100000,105000,110000]);
});
test('greeting interval persists across limiter recreation and other requests',async()=>{
  const f=fixture(), times=[];
  await f.limiter().run('greet',200000,async()=>times.push(f.now()));
  await f.limiter().run('request',200000,async()=>{});
  await f.limiter().run('greet',200000,async()=>times.push(f.now()));
  assert.deepEqual(times,[100000,120000]);
});
test('cooldown is shared, respects Retry-After, and never dispatches',async()=>{
  const f=fixture(),l=f.limiter();
  await assert.rejects(l.run('request',200000,async()=>({status:429,retry_after:'180'})),/冷却/);
  assert.equal(f.saved.bossRateState.cooldown_until,280000);
  let called=false;
  await assert.rejects(f.limiter().run('request',200000,async()=>{called=true;}),/冷却/);
  assert.equal(called,false);
});
test('business code 9 triggers minimum cooldown and settings cannot speed up defaults',async()=>{
  const f=fixture(),l=f.limiter();
  await assert.rejects(l.configure({request_seconds:1,greet_seconds:2}));
  await assert.rejects(l.run('request',200000,async()=>({status:200,body:{code:9}})),/冷却/);
  assert.equal(f.saved.bossRateState.cooldown_until,220000);
});
test('expired waiting slot does not execute or reserve future burst slots',async()=>{
  const f=fixture(),l=f.limiter();
  await l.run('greet',200000,async()=>{});
  let called=false;
  await assert.rejects(l.run('greet',110000,async()=>{called=true;}),/等待/);
  assert.equal(called,false);
  assert.equal(f.saved.bossRateState.last_greet_at,100000);
});
test('UI limit signal blocks the next account request and is not replayed forever',async()=>{
  const f=fixture(),l=f.limiter();let called=false;
  const signals=async()=>[{at:100000,status:429,retry_after:'180'}];
  await assert.rejects(l.run('request',200000,async()=>{called=true;},signals),/冷却/);
  assert.equal(called,false);
  assert.equal(f.saved.bossRateState.cooldown_until,280000);
  assert.equal(f.saved.bossRateState.last_signal_at,100000);
  f.advance(180001);
  await l.run('request',400000,async()=>{called=true;},signals);
  assert.equal(called,true);
});

test('passive signals retain the longest cooldown from multiple responses',async()=>{
  const f=fixture();
  await assert.rejects(f.limiter().run('request',200000,async()=>{},async()=>[
    {at:100000,status:429,retry_after:null,cooldown_until:700000}
  ]));
  assert.equal(f.saved.bossRateState.cooldown_until,700000);
});
