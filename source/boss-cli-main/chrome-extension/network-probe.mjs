// Temporary, read-only observation of responses already loaded by one BOSS tab.
export function createNetworkProbe(chrome) {
  const sessions=new Map();
  chrome.debugger.onEvent.addListener((source,method,params)=>{
    const session=sessions.get(source.tabId);
    if(!session || session.detached) return;
    if(method==='Network.responseReceived') {
      const response=params.response || {};
      let url;
      try {url=new URL(response.url);} catch {return;}
      if(url.origin!=='https://www.zhipin.com' || !['XHR','Fetch'].includes(params.type) ||
         !/json/i.test(response.mimeType || '') || session.entries.size>=100) return;
      session.entries.set(params.requestId,{path:url.pathname,query:url.search,status:response.status,
        mimeType:response.mimeType,body:null,base64Encoded:false});
    } else if(method==='Network.loadingFinished') {
      const entry=session.entries.get(params.requestId);
      if(!entry) return;
      const pending=chrome.debugger.sendCommand({tabId:source.tabId},'Network.getResponseBody',
        {requestId:params.requestId}).then(value=>{
          if(typeof value.body==='string' && value.body.length<=1000000) {
            entry.body=value.body;
            entry.base64Encoded=Boolean(value.base64Encoded);
          } else entry.error='response_too_large';
        },()=>{entry.error='response_body_unavailable';});
      session.pending.push(pending);
    }
  });
  chrome.debugger.onDetach.addListener(source=>{
    const session=sessions.get(source.tabId);
    if(session) session.detached=true;
  });
  return {
    async start(tabId,geekId) {
      if(sessions.has(tabId)) throw Error('网络诊断已在运行');
      if(typeof geekId!=='string' || !geekId) throw Error('缺少候选人身份');
      const target={tabId};
      await chrome.debugger.attach(target,'1.3');
      try {await chrome.debugger.sendCommand(target,'Network.enable',{maxTotalBufferSize:10000000});}
      catch(error) {await chrome.debugger.detach(target);throw error;}
      sessions.set(tabId,{geekId,entries:new Map(),pending:[],detached:false});
      return {started:true};
    },
    async stop(tabId,geekId) {
      const session=sessions.get(tabId);
      if(!session) throw Error('网络诊断未启动');
      if(session.geekId!==geekId) throw Error('候选人身份不一致');
      sessions.delete(tabId);
      await Promise.allSettled(session.pending);
      if(!session.detached) {
        try {await chrome.debugger.sendCommand({tabId},'Network.disable');}
        finally {await chrome.debugger.detach({tabId});}
      }
      return {detached:session.detached,responses:[...session.entries.values()]};
    }
  };
}
