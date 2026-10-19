import { pageOperation } from './page-dom.js';
import { chatOperation } from './chat-dom.js';
let socket = null;
let heartbeat = null;
let connecting = null;
let connectionEnabled = false;
let queue = Promise.resolve();
const seen = new Map();
const matchesBoss = url => { try { const u = new URL(url); return u.protocol === 'https:' && ['www.zhipin.com','zhipin.com'].includes(u.hostname); } catch { return false; } };

async function setStatus(status) { await chrome.storage.session.set({bridgeStatus:status}); }
async function frames(tabId, operation, args = {}, documentIds) {
  const target = documentIds ? {tabId, documentIds} : {tabId, allFrames:true};
  return chrome.scripting.executeScript({target, func:operation.startsWith('chat_') ? chatOperation : pageOperation, args:[operation,args], world:operation.startsWith('chat_') ? 'MAIN' : 'ISOLATED'});
}
function summarize(results) {
  const root = results.find(r => r.frameId === 0);
  if (!root?.result) throw new Error('页面未就绪，请在原 BOSS 标签页加载完成后重试');
  const data = results.map(r => r.result).filter(Boolean);
  const url = root.result.url;
  const path = new URL(url).pathname;
  let state = 'unknown';
  if (data.some(d => d.verify) || /\/verify|\/captcha|\/safe\//.test(path)) state = 'verification_required';
  else if (data.some(d => d.login) || /\/login|\/web\/user\//.test(path)) state = 'not_logged_in';
  else if (path.startsWith('/web/geek/')) state = 'wrong_role';
  else if ((path.startsWith('/web/chat') || path.startsWith('/web/boss')) && data.some(d => d.content || d.name)) state = 'logged_in';
  return {state, url, name:data.find(d=>d.name)?.name || '', company:data.find(d=>d.company)?.company || '', documentId:root.documentId};
}
async function inspect(tabId, documentId) {
  const tab = await chrome.tabs.get(tabId);
  if (!matchesBoss(tab.url)) throw new Error('原标签页已离开 BOSS，请重新检测接入');
  const results = await frames(tabId,'inspect');
  const status = summarize(results);
  if (documentId && status.documentId !== documentId) throw new Error('页面已刷新或跳转，请重新检测并接入此页面');
  return status;
}
function assertLive(ws) {
  if (!connectionEnabled || socket !== ws || ws.readyState !== WebSocket.OPEN) throw new Error('扩展连接已断开，操作取消');
}
function requireRecruiter(state) {
  if (state.state !== 'logged_in') throw new Error('BOSS 页面未登录或需要验证');
  if (!state.url.includes('/web/chat/recommend')) throw new Error('请在原标签页打开牛人推荐，再重新接入');
}
async function ready(tabId, documentId, ws) {
  const state = await inspect(tabId,documentId);
  assertLive(ws);
  requireRecruiter(state);
  return state;
}
async function execute(command, ws) {
  assertLive(ws);
  if (Date.now() > command.deadline) throw new Error('操作已过期，未执行');
  if (command.operation === 'discover') {
    const tabs = await chrome.tabs.query({url:['https://www.zhipin.com/*','https://zhipin.com/*']});
    const result=[];
    for (const tab of tabs) {
      try {
        const info = await inspect(tab.id);
        result.push({...info, target_id:`${tab.id}:${info.documentId}`});
      } catch { /* A closed or navigating tab is not safe to select. */ }
    }
    return result;
  }
  const match = /^(\d+):([A-Za-z0-9-]+)$/.exec(command.target);
  if (!match) throw new Error('无效的 BOSS 标签页标识');
  const tabId = Number(match[1]), documentId = match[2];
  const state = await inspect(tabId,documentId);
  assertLive(ws);
  if (command.operation === 'inspect') return state;
  if (['chat_preview','chat_send','chat_diagnostics'].includes(command.operation)) {
    const checkChat = s => {
      if (s.state !== 'logged_in' || !/^https:\/\/(www\.)?zhipin\.com\/web\/chat(?:\/index)?\/?$/.test(s.url)) throw new Error('请在原 BOSS 标签页打开聊天会话，再重新接入');
    };
    checkChat(state);
    if (command.operation === 'chat_diagnostics') return await frames(tabId,'chat_diagnostics');
    if (command.operation === 'chat_preview') {
      const results = await frames(tabId,'chat_preview');
      checkChat(await inspect(tabId,documentId)); assertLive(ws);
      const failed = results.find(r=>r.result?.chat_error);
      if (failed) throw new Error(failed.result.detail);
      const found = results.filter(r=>r.result);
      if (found.length !== 1) throw new Error('未唯一识别会话、联系人标识或输入框。请先打开会话；当前页面结构可能尚不支持');
      return {...found[0].result, frame_document:found[0].documentId};
    }
    if (typeof command.args?.frame_document !== 'string') throw new Error('缺少会话所在页面');
    checkChat(await inspect(tabId,documentId)); assertLive(ws);
    if (Date.now()>command.deadline) throw new Error('发送操作已过期');
    const result = await frames(tabId,'chat_send',{...command.args,deadline:command.deadline},[command.args.frame_document]);
    if (!result[0]?.result) throw new Error(result[0]?.error?.message || '页面脚本没有返回结果，发送状态未知');
    return result[0].result;
  }
  requireRecruiter(state);
  if (command.operation === 'cards') {
    const results = await frames(tabId,'cards');
    await ready(tabId,documentId,ws);
    return [...new Map(results.flatMap(r=>r.result||[]).map(c=>[c.geek_id,c])).values()];
  }
  if (command.operation === 'scroll') {
    await ready(tabId,documentId,ws);
    assertLive(ws);
    await frames(tabId,'scroll');
    return true;
  }
  if (command.operation === 'greet') {
    if (typeof command.args?.geek_id !== 'string' || !command.args.geek_id) throw new Error('缺少候选人标识');
    const locations = await frames(tabId,'locate',command.args);
    const found = locations.filter(r=>r.result > 0);
    if (found.length !== 1 || found[0].result !== 1) throw new Error('候选人卡片已变化或重复，未发送');
    await ready(tabId,documentId,ws);
    assertLive(ws);
    if (Date.now() > command.deadline) throw new Error('操作已过期，未发送');
    const result = await frames(tabId,'greet',{...command.args,deadline:command.deadline},[found[0].documentId]);
    return result[0]?.result === true;
  }
  throw new Error('不支持的浏览器操作');
}
async function receive(ws, message) {
  if (message.type === 'ready') { await setStatus('已连接本机程序，可返回设置页检测 BOSS 页面'); return; }
  if (message.type === 'pong') return;
  if (typeof message.id !== 'string') return;
  let response = seen.get(message.id);
  if (!response) {
    try { response = {id:message.id,result:await execute(message,ws)}; }
    catch(error) { response = {id:message.id,error:error.message}; }
    seen.set(message.id,response);
    if (seen.size > 100) seen.delete(seen.keys().next().value);
  }
  if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(response));
}
async function connect() {
  if (socket && [WebSocket.OPEN,WebSocket.CONNECTING].includes(socket.readyState)) return;
  if (connecting) return connecting;
  connecting = (async () => {
    const config = await chrome.storage.local.get(['bridgeToken','enabled']);
    if (!config.enabled || !config.bridgeToken) return;
    connectionEnabled = true;
    let {clientId} = await chrome.storage.session.get('clientId');
    if (!clientId) { clientId=crypto.randomUUID(); await chrome.storage.session.set({clientId}); }
    const ws = new WebSocket('ws://127.0.0.1:8000/api/browser-extension/ws');
    socket = ws;
    await setStatus('正在连接本机程序…');
    ws.onopen = () => {
      ws.send(JSON.stringify({type:'hello',token:config.bridgeToken,client_id:clientId}));
      clearInterval(heartbeat);
      heartbeat = setInterval(()=> { if (ws.readyState===WebSocket.OPEN) ws.send(JSON.stringify({type:'ping'})); },20000);
    };
    ws.onmessage = event => { try { const message=JSON.parse(event.data); queue=queue.then(()=>receive(ws,message)).catch(()=>{}); } catch {} };
    ws.onclose = event => {
      if (socket===ws) { socket=null; clearInterval(heartbeat); }
      setStatus(event.code===1008 ? '配对失败，请复制本机设置页的配对码后重试' : '已断开，请确认本机程序运行后点击连接');
    };
    ws.onerror = () => setStatus('无法连接本机程序，请先启动 http://127.0.0.1:8000');
  })().finally(()=>{connecting=null;});
  return connecting;
}
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  // Only extension pages; no externally_connectable and no page messaging bridge.
  if (sender.id !== chrome.runtime.id || sender.tab) return;
  (async()=>{
    if (message.type==='connect') {
      if (typeof message.token !== 'string' || message.token.length < 20) throw new Error('请粘贴本机设置页中的完整配对码');
      await chrome.storage.local.set({bridgeToken:message.token.trim(),enabled:true});
      if (socket) { socket.onclose=null; socket.close(); socket=null; clearInterval(heartbeat); }
      await connect();
      return {ok:true};
    }
    if (message.type==='disconnect') {
      connectionEnabled = false;
      await chrome.storage.local.set({enabled:false});
      if(socket) socket.close();
      return {ok:true};
    }
    throw new Error('未知操作');
  })().then(respond).catch(error=>respond({error:error.message}));
  return true;
});
chrome.alarms.create('bridge-reconnect',{periodInMinutes:1});
chrome.alarms.onAlarm.addListener(alarm=>{if(alarm.name==='bridge-reconnect') connect();});
chrome.runtime.onStartup.addListener(connect);
connect();
