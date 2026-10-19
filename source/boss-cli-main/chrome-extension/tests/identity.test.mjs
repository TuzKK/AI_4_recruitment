import test from 'node:test';
import assert from 'node:assert/strict';
import {loadClientIdentity} from '../identity.mjs';
test('extension identity survives session reset and migrates existing identity',async()=>{
 const local={},session={client:'existing-session'};
 const storage={local:{get:async key=>({[key]:local[key]}),set:async data=>Object.assign(local,data)},
 session:{get:async key=>({[key]:session[key]})}};
 assert.equal(await loadClientIdentity(storage,()=> 'new-id'),'existing-session');
 delete session.client;
 assert.equal(await loadClientIdentity(storage,()=> 'another-id'),'existing-session');
});
