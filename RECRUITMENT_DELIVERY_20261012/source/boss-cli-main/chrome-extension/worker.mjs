import {isBossUrl,classify,validateApi,parseTarget} from './protocol.mjs';
import {pageOperation} from './page.mjs';

let running=false;
let generation=0;
let controller=null;
const status=text=>chrome.storage.session.set({status:text});
async function inspect(tabId) {
  const tab=await chrome.tabs.get(tabId);
  if (!isBossUrl(tab.url)) throw new Error('页面已离开 BOSS');
  const frames=await chrome.scripting.executeScript({target:{tabId,allFrames:true},func:pageOperation,args:['inspect',{},Date.now()+5000]});
  const root=frames.find(r=>r.frameId===0);
  if (!root?.documentId || !root.result) throw new Error('页面加载中，请稍后重试');
  const values=frames.map(r=>r.result).filter(Boolean);
  return {target:`${tabId}:${root.documentId}`,url:tab.url,state:classify(tab.url,values),
    account:values.find(v=>v.account)?.account || ''};
}
async function accountIdentity(target, deadline) {
  const {tabId,documentId}=parseTarget(target);
  const response=await chrome.scripting.executeScript({target:{tabId,documentIds:[documentId]},world:'MAIN',func:pageOperation,
    args:['api',{method:'GET',path:'/wapi/zpuser/wap/getUserInfo.json',params:{}},deadline]});
  const payload=response[0]?.result?.body;
  if (payload?.code !== 0) throw new Error('无法读取当前账号标识，请确认登录或验证状态');
  const data=payload.zpData;
  const containers=[data?.userInfo,data?.bossInfo,data?.geekInfo,data];
  for (const item of containers) {
    if (!item || typeof item !== 'object') continue;
    for (const key of ['uid','userId','encryptUid','encryptUserId']) {
      if (['string','number'].includes(typeof item[key]) && String(item[key])) {
        const bytes=new TextEncoder().encode(key+':'+item[key]);
        return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
      }
    }
  }
  throw new Error('接口未提供已识别的稳定账号标识，暂停操作；不能用昵称代替账号 ID');
}
async function discover() {
  const tabs=await chrome.tabs.query({url:['https://www.zhipin.com/*','https://zhipin.com/*']});
  const pages=[];
  for (const tab of tabs) {
    try {
      const page=await inspect(tab.id);
      if(page.state==='logged_in') {
        try {page.account_key=await accountIdentity(page.target,Date.now()+7000);}
        catch(e) {page.account_error=e.message;}
      }
      pages.push(page);
    }
    catch {pages.push({target:`${tab.id}:unavailable`,url:tab.url,state:'unknown',account:''});}
  }
  return pages;
}
export async function execute(command) {
  if (Date.now() >= command.deadline) throw new Error('操作已过期，未执行');
  if (command.operation === 'discover') return {pages:await discover()};
  if (command.operation === 'open_login') {
    const pages=await discover();
    if (pages.length) return {opened:false,pages,instruction:'请在已有 BOSS 页面登录或完成验证，然后查询 browser status --probe'};
    await chrome.tabs.create({url:'https://www.zhipin.com/web/chat/recommend'});
    return {opened:true,instruction:'请在新页面人工登录，然后查询 browser status --probe'};
  }
  const {tabId,documentId}=parseTarget(command.target);
  const before=await inspect(tabId);
  if (before.target !== command.target) throw new Error('页面已刷新，请重新发现并选择');
  if (command.operation === 'inspect') return before;
  if (before.state !== 'logged_in') throw new Error(`招聘页面不可用：${before.state}`);
  const expected=command.args?.account_key;
  if (!expected || await accountIdentity(command.target,command.deadline) !== expected) {
    throw new Error('账号标识缺失或已变化，请重新发现并选择页面；未执行目标操作');
  }
  if (command.operation === 'navigate') {
    const paths={recommend:'/web/chat/recommend',chat:'/web/chat/index'};
    const destination=paths[command.args.page];
    if(!destination) throw new Error('只允许导航至推荐牛人或沟通页面');
    if(new URL(before.url).pathname!==destination) await chrome.tabs.update(tabId,{url:'https://www.zhipin.com'+destination});
    let ready;
    while(Date.now()<command.deadline-1500) {
      try {ready=await inspect(tabId);if(new URL(ready.url).pathname===destination && ready.state==='logged_in') break;}catch{}
      await new Promise(r=>setTimeout(r,250));
    }
    if(!ready || new URL(ready.url).pathname!==destination || ready.state!=='logged_in') throw new Error('页面导航未就绪');
    if(await accountIdentity(ready.target,command.deadline)!==expected) throw new Error('导航后账号已变化');
    return {...ready,account_key:expected};
  }
  let result;
  if (command.operation === 'api') {
    validateApi(command.args);
    result=await chrome.scripting.executeScript({target:{tabId,documentIds:[documentId]},world:'MAIN',func:pageOperation,
      args:['api',command.args,command.deadline]});
    result=result[0]?.result;
  } else if (command.operation === 'cards') {
    if (!new URL(before.url).pathname.includes('/web/chat/recommend')) throw new Error('请先打开推荐牛人页面');
    const frames=await chrome.scripting.executeScript({target:{tabId,allFrames:true},func:pageOperation,
      args:['cards',{},command.deadline]});
    result=[...new Map(frames.flatMap(x=>x.result || []).map(x=>[x.geek_id,x])).values()];
  } else if (command.operation === 'open_profile') {
    if(!new URL(before.url).pathname.includes('/web/chat/recommend')) throw new Error('先由 CLI 导航到推荐页面');
    if(typeof command.args.geek_id!=='string' || !command.args.geek_id) throw new Error('缺少候选人ID');
    const locations=await chrome.scripting.executeScript({target:{tabId,allFrames:true},func:pageOperation,
      args:['locate_profile',command.args,command.deadline]});
    const matches=locations.filter(r=>r.result>0);
    if(matches.length!==1 || matches[0].result!==1) throw new Error('卡片不存在或不唯一，未点击');
    const response=await chrome.scripting.executeScript({target:{tabId,documentIds:[matches[0].documentId]},func:pageOperation,
      args:['open_profile',command.args,command.deadline]});
    result=response[0]?.result;
  } else if (command.operation === 'profile_snapshot') {
    const frames=await chrome.scripting.executeScript({target:{tabId,allFrames:true},world:'MAIN',func:pageOperation,
      args:['profile_snapshot',{},command.deadline]});
    result={frames:frames.map(x=>({frameId:x.frameId,documentId:x.documentId,...x.result}))};
  } else throw new Error('不支持的命令');
  const after=await inspect(tabId);
  if (after.target !== before.target || after.account !== before.account || after.state !== 'logged_in') {
    throw new Error('请求过程中页面或账号已变化；结果不可信，写操作不要自动重试');
  }
  if (await accountIdentity(command.target,command.deadline) !== expected) throw new Error('账号已变化，结果未知，请核实');
  return result;
}
async function loop() {
  if (running) return;
  const config=await chrome.storage.local.get(['enabled','port','token']);
  if (!config.enabled || !config.token) return;
  running=true;
  const current=++generation;
  controller=new AbortController();
  const signal=controller.signal;
  let {client}=await chrome.storage.session.get('client');
  if (!client) {client=crypto.randomUUID(); await chrome.storage.session.set({client});}
  const send=async (path,data)=>{
    const response=await fetch(`http://127.0.0.1:${config.port}${path}`,{method:'POST',signal,
      headers:{'Content-Type':'application/json','Authorization':`Bearer ${config.token}`},body:JSON.stringify(data)});
    if (!response.ok) throw new Error(`本机连接失败 HTTP ${response.status}`);
    return await response.json();
  };
  try {
    while (current===generation) {
      const {command}=await send('/poll',{client});
      await status('已连接 CLI；可返回终端查询页面和登录状态');
      if (!command) continue;
      let result=null,error=null;
      try {result=await execute(command);} catch(e) {error=e.message;}
      // A lost result is never replayed: the CLI treats timeout as unknown.
      await send('/result',{client,id:command.id,result,error});
    }
  } catch(e) {
    await status(e.name==='AbortError'?'已断开':e.message);
  } finally {running=false;}
}
chrome.runtime.onMessage.addListener((message,_sender,respond)=>{
  if (message.action==='connect') {
    generation++; controller?.abort();
    const start=async()=>{while(running) await new Promise(r=>setTimeout(r,50)); await chrome.alarms.create('reconnect',{periodInMinutes:0.5}); void loop();};
    void start(); respond({ok:true});
  } else if (message.action==='disconnect') {
    generation++; controller?.abort(); void chrome.alarms.clear('reconnect'); respond({ok:true});
  }
});
chrome.alarms.onAlarm.addListener(alarm=>{if(alarm.name==='reconnect') void loop();});
chrome.runtime.onStartup.addListener(()=>void loop());
void loop();
