import {loadClientIdentity} from './identity.mjs';
import {profileCapture,captureFingerprint} from './capture.mjs';
import {resumeCanvasPage} from './canvas.mjs';
import {captureCanvasSegment} from './canvas-segment.mjs';
import {createNetworkProbe} from './network-probe.mjs';
import {selectAttachmentUrl,fetchAttachmentPage} from './attachment.mjs';
const captureSessions=new Map();
const openedProfiles=new Map();
let networkProbe;
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
    if(command.args.refresh || new URL(before.url).pathname!==destination) await chrome.tabs.update(tabId,{url:'https://www.zhipin.com'+destination});
    let ready;
    while(Date.now()<command.deadline-1500) {
      try {ready=await inspect(tabId);if(new URL(ready.url).pathname===destination && ready.state==='logged_in' && (!command.args.refresh || ready.target!==before.target)) break;}catch{}
      await new Promise(r=>setTimeout(r,250));
    }
    if(!ready || new URL(ready.url).pathname!==destination || ready.state!=='logged_in' || (command.args.refresh && ready.target===before.target)) throw new Error('页面导航未就绪');
    if(await accountIdentity(ready.target,command.deadline)!==expected) throw new Error('导航后账号已变化');
    return {...ready,account_key:expected};
  }
  let result;
  if (command.operation === 'attachment_fetch') {
    if(new URL(before.url).pathname !== '/web/chat/index') throw new Error('Open the BOSS chat page first');
    const {gid,mid}=command.args;
    if(!Number.isSafeInteger(gid) || gid<=0 || !/^[0-9]{1,30}$/.test(String(mid))) {
      throw new Error('Invalid attachment identity');
    }
    const response=await chrome.scripting.executeScript({target:{tabId,documentIds:[documentId]},world:'MAIN',
      func:pageOperation,args:['api',{method:'GET',path:'/wapi/zpchat/boss/historyMsg',
        params:{gid,c:50,src:0}},command.deadline]});
    const history=response[0]?.result;
    if(history?.status!==200 || history.body?.code!==0) throw new Error('Cannot read live chat history');
    const url=selectAttachmentUrl(history.body.zpData?.messages,gid,mid);
    let previewTab;
    try {
      previewTab=await chrome.tabs.create({url:'https://m.zhipin.com/',active:false});
      let ready=false;
      while(Date.now()<command.deadline-3000) {
        const current=await chrome.tabs.get(previewTab.id);
        if(current.status==='complete') {
          if(new URL(current.url).origin!=='https://m.zhipin.com') throw new Error('Attachment tab left BOSS');
          ready=true; break;
        }
        await new Promise(resolve=>setTimeout(resolve,200));
      }
      if(!ready) throw new Error('Attachment tab did not load');
      const data=await chrome.scripting.executeScript({target:{tabId:previewTab.id},world:'MAIN',
        func:fetchAttachmentPage,args:[url,command.deadline]});
      result=data[0]?.result;
      if(!result?.base64) throw new Error('No PDF returned');
    } finally {
      if(previewTab) await chrome.tabs.remove(previewTab.id).catch(()=>{});
    }
  } else if (command.operation === 'greet') {
    if(new URL(before.url).pathname !== '/web/chat/recommend') throw new Error('请先打开牛人推荐页面');
    if(typeof command.args?.geek_id!=='string' || !command.args.geek_id) throw new Error('缺少候选人 ID');
    const locations=await chrome.scripting.executeScript({target:{tabId,allFrames:true},func:pageOperation,
      args:['locate_greet',command.args,command.deadline]});
    const matches=locations.filter(r=>r.result>0);
    if(matches.length!==1 || matches[0].result!==1) throw new Error('候选人卡片缺失或重复，未发送');
    const response=await chrome.scripting.executeScript({target:{tabId,documentIds:[matches[0].documentId]},func:pageOperation,
      args:['greet',command.args,command.deadline]});
    result=response[0]?.result;
  } else if (command.operation === 'chat_probe' || command.operation === 'chat_send') {
    if(new URL(before.url).pathname !== '/web/chat/index') throw new Error('请先导航至沟通页面');
    const response=await chrome.scripting.executeScript({target:{tabId,documentIds:[documentId]},world:'MAIN',func:pageOperation,
      args:[command.operation,command.args,command.deadline]});
    result=response[0]?.result;
  } else if (command.operation === 'api') {
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
    const previous=await chrome.scripting.executeScript({target:{tabId,allFrames:true},func:captureFingerprint});
    if(previous.some(f=>f.result?.identifiable)) throw new Error('已有详情，先由CLI刷新推荐页再按ID打开；不能依据内容变化推断身份');
    const response=await chrome.scripting.executeScript({target:{tabId,documentIds:[matches[0].documentId]},func:pageOperation,
      args:['open_profile',command.args,command.deadline]});
    result=response[0]?.result;
    openedProfiles.set(tabId,{geek_id:command.args.geek_id,documentId,previous});
  } else if (command.operation === 'profile_capture') {
    if(!new URL(before.url).pathname.includes('/web/chat/recommend')) throw new Error('截图仅允许推荐页面');
    const opened=openedProfiles.get(tabId);
    if(!opened||opened.documentId!==documentId||opened.geek_id!==command.args.geek_id) throw new Error('先按同一候选人ID打开详情');
    result=await profileCapture(chrome,tabId,command.args,command.deadline,captureSessions,opened.previous);
    if(command.args.action==='prepare') opened.captureId=result.capture_id;
    if(command.args.action==='release' && opened.captureId===command.args.capture_id) opened.captureId=null;
  } else if (command.operation === 'resume_canvas') {
    if(!new URL(before.url).pathname.includes('/web/chat/recommend')) throw new Error('Canvas 仅允许推荐页详情');
    const opened=openedProfiles.get(tabId);
    if(!opened||opened.documentId!==documentId||opened.geek_id!==command.args.geek_id) throw new Error('先按同一候选人 ID 打开详情');
    if(!['inspect','image','diagnostic','segment'].includes(command.args.action)) throw new Error('不支持的 Canvas 操作');
    if(command.args.action==='segment') {
      const session=captureSessions.get(command.args.capture_id);
      if(!session||session.tabId!==tabId||opened.captureId!==command.args.capture_id||
         session.initial.total<=session.initial.height+2||
         !opened.canvasIdentity||!opened.canvasDocumentId) throw new Error('长简历画布会话未就绪');
      result=await captureCanvasSegment(chrome,tabId,session,
        {identity:opened.canvasIdentity,documentId:opened.canvasDocumentId},command.args.top,command.deadline);
    } else {
    if(command.args.action!=='inspect' && (!Number.isInteger(command.args.index)||command.args.index<0||command.args.index>=30)) throw new Error('Canvas 页码无效');
    if(command.args.action==='image' && !opened.canvasIdentity) throw new Error('先确认稳定的简历画布');
    const frames=await chrome.scripting.executeScript({target:{tabId,allFrames:true},func:resumeCanvasPage,
      args:[[command.args.action,command.args.index??null,command.deadline,opened.canvasIdentity??null]]});
    const matches=frames.filter(f=>f.result);
    if(matches.length!==1) throw new Error('在线简历 Canvas 文档不存在或不唯一');
    if(command.args.action==='inspect' && matches[0].result.initialized) {
      if(opened.canvasIdentity && (opened.canvasIdentity!==matches[0].result.identity ||
          opened.canvasDocumentId!==matches[0].documentId)) throw new Error('简历画布身份已变化');
      opened.canvasIdentity=matches[0].result.identity;
      opened.canvasDocumentId=matches[0].documentId;
    }
    if(command.args.action==='image' && (opened.canvasIdentity!==matches[0].result.identity ||
        opened.canvasDocumentId!==matches[0].documentId)) throw new Error('简历画布身份已变化');
    result={document_id:matches[0].documentId,...matches[0].result};
    }
  } else if (command.operation === 'profile_snapshot') {
    const frames=await chrome.scripting.executeScript({target:{tabId,allFrames:true},world:'MAIN',func:pageOperation,
      args:['profile_snapshot',{},command.deadline]});
    result={frames:frames.map(x=>({frameId:x.frameId,documentId:x.documentId,...x.result}))};
  } else if (command.operation === 'profile_network') {
    if(!new URL(before.url).pathname.includes('/web/chat/recommend')) throw new Error('网络诊断仅允许推荐页面');
    const {action,geek_id}=command.args;
    if(typeof geek_id!=='string' || !geek_id) throw new Error('缺少候选人 ID');
    networkProbe ??= createNetworkProbe(chrome);
    if(action==='start') {
      const locations=await chrome.scripting.executeScript({target:{tabId,allFrames:true},func:pageOperation,
        args:['locate_profile',{geek_id},command.deadline]});
      if(locations.filter(r=>r.result>0).length!==1) throw new Error('候选人卡片不存在或重复');
      result=await networkProbe.start(tabId,geek_id);
    } else if(action==='stop') {
      const opened=openedProfiles.get(tabId);
      if(opened && opened.geek_id!==geek_id) throw new Error('当前详情候选人身份不一致');
      result=await networkProbe.stop(tabId,geek_id);
    } else throw new Error('不支持的网络诊断操作');
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
  const client=await loadClientIdentity(chrome.storage);
  const send=async (path,data)=>{
    const response=await fetch(`http://127.0.0.1:${config.port}${path}`,{method:'POST',signal,
      headers:{'Content-Type':'application/json','Authorization':`Bearer ${config.token}`},body:JSON.stringify(data)});
    const payload=await response.json();
    if (!response.ok) throw new Error(`本机连接失败 HTTP ${response.status}：${payload.error||'未知错误'}`);
    return payload;
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
