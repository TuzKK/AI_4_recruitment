// A stable installation identity, with migration from the old session store.
export async function loadClientIdentity(storage, createId=()=>crypto.randomUUID()) {
 const saved=await storage.local.get('client');
 if(saved.client) return saved.client;
 const previous=await storage.session.get('client');
 const client=previous.client||createId();
 await storage.local.set({client});
 return client;
}
