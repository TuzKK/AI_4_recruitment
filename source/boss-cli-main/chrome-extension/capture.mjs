// Fixed operations only. No caller-provided JavaScript or DevTools commands.
export function validateCapture(args) {
 if(!['prepare','step','release','fit'].includes(args.action)) throw Error('不支持的截图动作');
 if(args.action!=='prepare' && (typeof args.capture_id!=='string' || !args.capture_id)) throw Error('截图会话缺失');
 if(args.top!==undefined && (!Number.isFinite(args.top)||args.top<0||args.top>1000000)) throw Error('滚动参数无效');
}
export function screenshotClip(box, offset, viewport) {
 const clip={x:box.x+offset.x,y:box.y+offset.y,width:box.width,height:box.height,scale:1};
 if(!Object.values(clip).every(Number.isFinite)||clip.width<=0||clip.height<=0||clip.x<0||clip.y<0||
    clip.x+clip.width>viewport.width+1||clip.y+clip.height>viewport.height+1) throw Error('简历截图区域超出视口，不能声明完整');
 return clip;
}
export function screenshotRequest(clip, beyondViewport=true) {
 return {format:'png',fromSurface:true,captureBeyondViewport:beyondViewport,optimizeForSpeed:true,clip};
}
export function diagnosticClip(box, bounds) {
 let x=box.x,y=box.y,right=box.x+box.width,bottom=box.y+box.height;
 for(const bound of bounds){x=Math.max(x,bound.x);y=Math.max(y,bound.y);right=Math.min(right,bound.x+bound.width);bottom=Math.min(bottom,bound.y+bound.height);}
 if(![x,y,right,bottom].every(Number.isFinite)||right-x<10||bottom-y<10) throw Error('简历区域没有足够可见像素');
 return {clip:{x,y,width:right-x,height:bottom-y,scale:1},cropped:x!==box.x||y!==box.y||right!==box.x+box.width||bottom!==box.y+box.height};
}
export async function fitCaptureViewport([height,id,deadline]) {
 if(Date.now()>=deadline) throw Error('视口适配已过期');
 const element=document.querySelector('[data-precontact-scroll=true]');
 if(!element||element===document.scrollingElement||element.scrollHeight<=element.clientHeight+2) throw Error('没有可核实的外层长滚动容器，未修改');
 const previous=element.clientHeight;
 if(!Number.isFinite(height)||height<100||height>=previous||previous-height>64) throw Error('只允许缩短被裁剪的少量高度');
 const originalStyle=element.getAttribute('style');
 element.setAttribute('data-precontact-fit',id);
 element.setAttribute('data-precontact-original-style',JSON.stringify(originalStyle));
 try {
   element.style.setProperty('min-height','0px','important');
   element.style.setProperty('height',height+'px','important');
   element.style.setProperty('max-height',height+'px','important');
   await new Promise(resolve=>setTimeout(resolve,500));
   if(Math.abs(element.clientHeight-height)>1) throw Error('视口适配未生效');
   return {height:element.clientHeight,total:element.scrollHeight,top:element.scrollTop};
 } catch(error) {
   if(originalStyle===null) element.removeAttribute('style');else element.setAttribute('style',originalStyle);
   element.removeAttribute('data-precontact-fit');
   element.removeAttribute('data-precontact-original-style');
   throw error;
 }
}
export function restoreCaptureViewport([id]) {
 const element=Array.from(document.querySelectorAll('[data-precontact-fit]')).find(e=>e.getAttribute('data-precontact-fit')===id);
 if(!element) return {restored:false};
 const saved=element.getAttribute('data-precontact-original-style');
 if(saved===null) return {restored:false};
 const style=JSON.parse(saved);
 if(style===null) element.removeAttribute('style');else element.setAttribute('style',style);
 element.removeAttribute('data-precontact-fit');
 element.removeAttribute('data-precontact-original-style');
 return {restored:true};
}
export async function captureFingerprint() {
 if(window.frameElement&&!window.frameElement.getClientRects().length) return null;
 const root=location.pathname.includes('c-resume')?(document.body||document.documentElement):Array.from(document.querySelectorAll('.boss-dialog__body,.dialog-wrap.active,.geek-detail,.resume-dialog,.dialog-lib-resume')).find(e=>e.getClientRects().length);
 if(!root) return null;
 let bitmap='';
 try {bitmap=Array.from(root.querySelectorAll('canvas')).map(c=>c.toDataURL()).join('|');}catch{}
 const text=root.innerText||'';
 const input=location.href+'|'+text+'|'+bitmap;
 const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(input));
 return {key:Array.from(new Uint8Array(hash)).map(x=>x.toString(16).padStart(2,'0')).join(''),
   frame_url:location.origin+location.pathname,identifiable:location.pathname.includes('c-resume')||(root.scrollHeight>80&&(!!root.querySelector('canvas,img,iframe')||text.trim().length>20))};
}
export function transitioned(previous, current) {
 if(!current?.result?.identifiable) return false;
 // Content changes are not candidate identity. Never reuse a pre-existing detail.
 return !previous.some(f=>f.result?.identifiable);
}
export async function capturePage(action, top, deadline) {
 if(Date.now()>=deadline) throw Error('截图动作已过期');
 const visible=e=>e.getClientRects().length>0;
 let root;
 const resumeFrame=location.pathname.includes('c-resume');
 if(resumeFrame) root=document.body||document.documentElement;
 else root=Array.from(document.querySelectorAll('.boss-dialog__body,.dialog-wrap.active,.geek-detail,.resume-dialog,.dialog-lib-resume'))
     .find(e=>visible(e));
 if(!root) return null;
 if(action==='prepare') {
   if(!resumeFrame&&(root.scrollHeight<80||(!(root.innerText||'').trim()&&!root.querySelector('canvas,img,iframe')))) return null;
   // Recover a fit left behind if the extension worker stopped before release.
   for(const element of [root,...root.querySelectorAll('[data-precontact-fit]')]) {
     if(!element.hasAttribute('data-precontact-fit')) continue;
     const saved=element.getAttribute('data-precontact-original-style');
     if(saved===null) throw Error('截图视口恢复信息缺失');
     const style=JSON.parse(saved);
     if(style===null) element.removeAttribute('style');else element.setAttribute('style',style);
     element.removeAttribute('data-precontact-fit');
     element.removeAttribute('data-precontact-original-style');
   }
   for(let i=0;i<10;i++) {
     const control=Array.from(root.querySelectorAll('span,a,button')).find(e=>visible(e)&&/^(查看全部|展开)$/.test(e.innerText.trim()));
     if(!control) break;
     control.click(); await new Promise(r=>setTimeout(r,200));
   }
   document.querySelectorAll('[data-precontact-scroll]').forEach(e=>e.removeAttribute('data-precontact-scroll'));
   const nodes=[root,...root.querySelectorAll('*')].filter(e=>e.clientHeight>80&&e.scrollHeight>e.clientHeight+2&&/auto|scroll/.test(getComputedStyle(e).overflowY));
   let scroll=nodes.sort((a,b)=>(b.scrollHeight-b.clientHeight)-(a.scrollHeight-a.clientHeight))[0];
   if(!scroll) scroll=(root===document.body?document.scrollingElement:root);
   scroll.setAttribute('data-precontact-scroll','true');
   scroll.scrollTop=0;
 }
 const scroll=document.querySelector('[data-precontact-scroll=true]');
 if(!scroll) throw Error('简历滚动对象已变化');
 if(top!==null&&top!==undefined) scroll.scrollTop=top;
 await new Promise(r=>setTimeout(r,500));
 const doc=scroll===document.scrollingElement;
 const rect=doc?{x:0,y:0,width:innerWidth,height:innerHeight}:scroll.getBoundingClientRect();
 const height=doc?innerHeight:scroll.clientHeight;
 const metrics={top:scroll.scrollTop,height,total:scroll.scrollHeight,
 box:{x:rect.x+(!doc?scroll.clientLeft:0),y:rect.y+(!doc?scroll.clientTop:0),width:doc?innerWidth:scroll.clientWidth,height},
 viewport:{width:innerWidth,height:innerHeight},canvas_count:root.querySelectorAll('canvas').length,
 contains_iframe:!!root.querySelector('iframe'),frame_url:location.origin+location.pathname,canvas_metrics:Array.from(root.querySelectorAll('canvas')).map(c=>({width:c.width,height:c.height,css_width:c.clientWidth,css_height:c.clientHeight,transform:getComputedStyle(c).transform}))};
 if(action==='prepare') metrics.text=root.innerText||'';
 return metrics;
}

export async function profileCapture(chrome, tabId, args, deadline, sessions, previous) {
 validateCapture(args);
 if(args.action==='release') {
 const target=sessions.get(args.capture_id);
 if(target && target.tabId!==tabId) throw Error('截图会话不属于当前页面');
 let restored=null;
 if(target?.fitPending){
  const restoration=await chrome.scripting.executeScript({target:{tabId,documentIds:[target.documentId]},func:restoreCaptureViewport,args:[[args.capture_id]]});
  restored=restoration[0]?.result?.restored ?? false;
 }
 sessions.delete(args.capture_id);return {released:true,viewport_restored:restored};
}
 if(!(await chrome.permissions.contains({permissions:['debugger']}))) throw Error('截图权限缺失，请在扩展管理页重新加载0.2.2版连接器并确认Chrome权限提示');
 let session;
 if(args.action==='prepare') {
   const identities=await chrome.scripting.executeScript({target:{tabId,allFrames:true},func:captureFingerprint});
   const changed=identities.filter(f=>transitioned(previous,f));
   const prepared=[];
   for(const identity of changed){
     const responses=await chrome.scripting.executeScript({target:{tabId,documentIds:[identity.documentId]},func:capturePage,args:['prepare',null,deadline]});
     const item=responses[0];if(item?.result) prepared.push(item);
   }
   const hosts=prepared.filter(f=>f.result.contains_iframe);
   const candidates=hosts.length?hosts:prepared;
   if(candidates.length!==1) throw Error('简历区域尚未就绪或不唯一');
   const item=candidates[0];
   session={tabId,documentId:item.documentId,frameId:item.frameId,frameUrl:item.result.frame_url,
     initial:{height:item.result.height,total:item.result.total},
     nestedFrames:prepared.filter(f=>f.frameId!==item.frameId&&f.result.frame_url.includes('c-resume')).map(f=>f.documentId)};
   const id=crypto.randomUUID(); sessions.set(id,session);
   return {...item.result,capture_id:id};
 }
 session=sessions.get(args.capture_id);
 if(!session||session.tabId!==tabId) throw Error('截图会话已失效，请重新打开详情');
 if(args.action==='fit') {
   if(!session.fitHeight||session.fitApplied) throw Error('没有待适配的截图视口');
   session.fitPending=true;
   try {
     const adjusted=await chrome.scripting.executeScript({target:{tabId,documentIds:[session.documentId]},func:fitCaptureViewport,args:[[session.fitHeight,args.capture_id,deadline]]});
     if(!adjusted[0]?.result) throw Error('截图视口适配没有返回结果');
     session.fitApplied=true;
     return {height:adjusted[0].result.height,total:adjusted[0].result.total,top:adjusted[0].result.top,fit_applied:true};
   } catch(error) {
     try {
       const restored=await chrome.scripting.executeScript({target:{tabId,documentIds:[session.documentId]},func:restoreCaptureViewport,args:[[args.capture_id]]});
       if(restored[0]?.result?.restored) session.fitPending=false;
     } catch {}
     throw error;
   }
 }
 const data=await chrome.scripting.executeScript({target:{tabId,documentIds:[session.documentId]},func:capturePage,args:['step',args.top??null,deadline]});
 const metrics=data[0]?.result;
 if(!metrics||metrics.frame_url!==session.frameUrl) throw Error('简历文档已变化');
 const tabWasActive=(await chrome.tabs.get(tabId)).active;
 const debuggee={tabId};
 await chrome.debugger.attach(debuggee,'1.3');
 const send=(method,params={})=>new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error('调试截图超时：'+method)),Math.max(1,deadline-Date.now()-2000));
   chrome.debugger.sendCommand(debuggee,method,params).then(value=>{clearTimeout(timer);resolve(value);},error=>{clearTimeout(timer);reject(error);});
 });
 try {
   const layout=await send('Page.getLayoutMetrics');
   const vp=layout.cssLayoutViewport||layout.layoutViewport;
   let offset={x:0,y:0};
   const content=layout.cssContentSize||layout.contentSize||{width:vp.clientWidth,height:vp.clientHeight};
   // Capture only composited pixels within the root viewport; fit a small overflow first.
   const bounds=[{x:0,y:0,width:vp.clientWidth,height:vp.clientHeight}];
   if(session.frameId!==0) {
     const tree=await send('Page.getFrameTree'); const frames=[];
     const visit=t=>{frames.push(t.frame);(t.childFrames||[]).forEach(visit);};visit(tree.frameTree);
     const matches=frames.filter(f=>{try{const u=new URL(f.url);return u.origin+u.pathname===session.frameUrl;}catch{return false;}});
     if(matches.length!==1) throw Error('简历嵌入页面无法唯一定位');
     const owner=await send('DOM.getFrameOwner',{frameId:matches[0].id});
     const model=await send('DOM.getBoxModel',{backendNodeId:owner.backendNodeId});
     const quad=model.model.content;
     if(Math.abs(quad[1]-quad[3])>1||Math.abs(quad[0]-quad[6])>1||Math.abs(quad[2]-quad[4])>1||Math.abs(quad[5]-quad[7])>1) throw Error('简历iframe存在变换，不能确认裁剪范围');
     offset={x:quad[0],y:quad[1]};
     const width=quad[2]-quad[0],height=quad[7]-quad[1];
     if(Math.abs(width-metrics.viewport.width)>2||Math.abs(height-metrics.viewport.height)>2) throw Error('简历iframe缩放或裁剪异常');
     bounds.push({x:offset.x,y:offset.y,width,height});
     let parentId=matches[0].parentId;
     while(parentId && parentId!==tree.frameTree.frame.id) {
       const parent=frames.find(f=>f.id===parentId);
       if(!parent) throw Error('iframe祖先缺失');
       const parentOwner=await send('DOM.getFrameOwner',{frameId:parent.id});
       const ancestor=await send('DOM.getBoxModel',{backendNodeId:parentOwner.backendNodeId});
       const q=ancestor.model.content;
       if(Math.abs(q[1]-q[3])>1||Math.abs(q[0]-q[6])>1||Math.abs(q[2]-q[4])>1||Math.abs(q[5]-q[7])>1) throw Error('iframe祖先存在变换');
       bounds.push({x:q[0],y:q[1],width:q[2]-q[0],height:q[7]-q[1]});
       parentId=parent.parentId;
     }
   }
   if(session.frameId!==0) screenshotClip(metrics.box,{x:0,y:0},metrics.viewport);
   const diagnostic=diagnosticClip({...metrics.box,x:metrics.box.x+offset.x,y:metrics.box.y+offset.y},bounds);
   const clip=diagnostic.clip;
   const absoluteBox={x:metrics.box.x+offset.x,y:metrics.box.y+offset.y,width:metrics.box.width,height:metrics.box.height};
   if(diagnostic.cropped && clip.x===absoluteBox.x && clip.y===absoluteBox.y && clip.width===absoluteBox.width && metrics.height-clip.height>0 && metrics.height-clip.height<=64) session.fitHeight=clip.height;
   const image=await send('Page.captureScreenshot',screenshotRequest(clip,false));
   const after=await chrome.scripting.executeScript({target:{tabId,documentIds:[session.documentId]},func:capturePage,args:['step',null,deadline]});
   const final=after[0]?.result;
   const currentFrames=await chrome.scripting.executeScript({target:{tabId,allFrames:true},func:captureFingerprint});
   let nested_scroll_uncovered=currentFrames.some(f=>f.frameId!==session.frameId&&f.result?.identifiable&&f.result.frame_url.includes('c-resume')&&!(session.nestedFrames||[]).includes(f.documentId));
   for(const documentId of session.nestedFrames||[]){
     const child=await chrome.scripting.executeScript({target:{tabId,documentIds:[documentId]},func:capturePage,args:['step',null,deadline]});
     if(!child[0]?.result||child[0].result.total>child[0].result.height+2) nested_scroll_uncovered=true;
   }
   return {...metrics,tab_active_at_capture:tabWasActive,can_fit_viewport:!!session.fitHeight&&!session.fitApplied,nested_scroll_uncovered,content_size:content,cropped:diagnostic.cropped,capture_clip:clip,top_viewport:{width:vp.clientWidth,height:vp.clientHeight},png:image.data,unstable:!final||final.top!==metrics.top||final.total!==metrics.total||final.height!==metrics.height};
 } finally {
   await Promise.race([chrome.debugger.detach(debuggee),new Promise(resolve=>setTimeout(resolve,1000))]);
 }
}
