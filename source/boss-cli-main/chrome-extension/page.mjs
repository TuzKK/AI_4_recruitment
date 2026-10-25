// This function is serialized into Chrome; all dependencies must be inside it.
export async function pageOperation(operation, args, deadline) {
  if (!['www.zhipin.com','zhipin.com'].includes(location.hostname) || location.protocol !== 'https:') throw new Error('已离开 BOSS');
  if (Date.now() >= deadline) throw new Error('操作已过期，未执行');
  const visible = selector => [...document.querySelectorAll(selector)].some(e=>e.getClientRects().length);
  if (operation === 'inspect') {
    return {url:location.href,
      login:visible('.login-dialog, .login-register-box, .sign-form, .login-content'),
      verify:visible('.geetest_panel, .nc-container, .captcha-container, .verify-dialog'),
      content:visible('[data-geekid], .chat-conversation, .chat-list, .geek-list, .chat-container, .recommend-list'),
      account:document.querySelector('.nav-figure .label-name, .user-name, .user-info .name')?.textContent?.trim() || ''};
  }
  if (operation === 'cards') {
    if (!['/web/chat/recommend','/web/frame/recommend','/web/frame/recommend/'].includes(location.pathname)) return [];
    if (args.close_profile === true) {
      const roots=[...document.querySelectorAll('.boss-dialog__body,.dialog-wrap.active,.geek-detail,.resume-dialog,.dialog-lib-resume')]
        .filter(e=>e.getClientRects().length);
      const buttons=[...new Set(roots.flatMap(root=>{
        const modal=root.closest('.boss-dialog,.dialog-wrap,.dialog-container,.dialog')||root;
        return [...modal.querySelectorAll('[aria-label="关闭"],[title="关闭"],.boss-dialog__close,.dialog-close,.close-btn,.icon-close,.close')];
      }))].filter(e=>e.getClientRects().length);
      if (roots.length && buttons.length!==1) throw new Error('无法唯一确定简历关闭按钮，请关闭简历弹窗后恢复');
      if (buttons.length===1) {
        buttons[0].click();
        await new Promise(resolve=>setTimeout(resolve,300));
      }
    }
    if (args.advance === true) {
      const card=[...document.querySelectorAll('[data-geekid]')].find(e=>e.getClientRects().length);
      if (card) {
        let container=card.parentElement;
        while(container && !(container.scrollHeight>container.clientHeight+2 &&
              /auto|scroll/.test(getComputedStyle(container).overflowY))) container=container.parentElement;
        // Standards-mode pages often report BODY as scrollable while HTML
        // owns the document scroll position. BODY.scrollTo then does nothing.
        if (!container || container===document.body) container=document.scrollingElement;
        if(container) container.scrollTo({top:container.scrollHeight,behavior:'instant'});
        await new Promise(resolve=>setTimeout(resolve,800));
      }
    }
    return [...document.querySelectorAll('[data-geekid]')].filter(e=>e.getClientRects().length).map(e=>({
      geek_id:e.getAttribute('data-geekid'),
      name:e.querySelector('[class*="name"]')?.textContent?.trim() || '', text:e.innerText || ''
    })).filter(e=>e.geek_id && e.text.length>=30);
  }
  if (operation === 'locate_greet' || operation === 'greet') {
    let clicked=false;
    let controls=[];
    try {
      const recommendationPage = ['/web/chat/recommend', '/web/frame/recommend', '/web/frame/recommend/'].includes(location.pathname);
      if (!recommendationPage && operation === 'locate_greet') return 0;
      if (!recommendationPage) throw new Error('请先打开牛人推荐页面');
      if (visible('.login-dialog, .login-register-box, .sign-form, .geetest_panel, .verify-dialog')) throw new Error('页面需要登录或验证，未发送');
      const cards=()=>[...document.querySelectorAll('[data-geekid]')].filter(e=>e.getAttribute('data-geekid')===args.geek_id && e.getClientRects().length);
      if (operation === 'locate_greet') return cards().length;
      const current=cards();
      if (current.length!==1) throw new Error('候选人卡片缺失或重复，未发送');
      const actions=card=>{
        // BOSS may put data-geekid on the content column, while the greeting
        // is its sibling. Expand only inside a container with this single ID.
        let root=card;
        for(let depth=0;root && depth<4;depth++,root=root.parentElement) {
          if(['BODY','HTML','UL','OL','MAIN'].includes(root.tagName)) break;
          const ids=new Set([...root.querySelectorAll('[data-geekid]')]
            .map(e=>e.getAttribute('data-geekid')).filter(Boolean));
          const own=root.getAttribute?.('data-geekid');
          if(own) ids.add(own);
          if(ids.size!==1 || !ids.has(args.geek_id)) break;
          const found=[...root.querySelectorAll('button, a, [role="button"], div, span, i, em')]
            .filter(e=>e.getClientRects().length && ['打招呼','继续沟通'].includes(e.textContent.trim()));
          if(found.length) return found;
        }
        return [];
      };
      const candidates=actions(current[0]).filter(e=>e.textContent.trim()==='打招呼');
      // A nested label and its button represent one action, not two.
      const buttons=candidates.filter(e=>!candidates.some(other=>other!==e && e.contains?.(other)))
        .filter(e=>!e.disabled && e.getAttribute('aria-disabled')!=='true' && !e.closest?.('[disabled],[aria-disabled="true"]'));
      controls=actions(current[0]).map(e=>({tag:e.tagName,className:String(e.className||''),label:e.textContent.trim().slice(0,30)}));
      if (buttons.length!==1) throw new Error('打招呼按钮不可用或不唯一，未发送');
      if (args.dry_run===true) return {status:'ready',candidate_id:args.geek_id,clicked:false,controls};
      if (Date.now()>=deadline-1500) throw new Error('操作已过期，未发送');
      clicked=true;
      buttons[0].click();
      for(let i=0;i<32 && Date.now()<deadline-500;i++) {
        const updated=cards();
        if(updated.length===1 && actions(updated[0]).some(e=>e.textContent.trim()==='继续沟通')) {
          return {status:'observed',candidate_id:args.geek_id,clicked:true,verification:'card_state'};
        }
        await new Promise(resolve=>setTimeout(resolve,250));
      }
      return {status:'clicked',candidate_id:args.geek_id,clicked:true,error:'已点击，页面未出现继续沟通；需核对会话记录'};
    } catch(error) {
      if(operation==='locate_greet') throw error;
      return {status:clicked?'unknown':'not_sent',candidate_id:args.geek_id,clicked,
        error:String(error?.message||error),controls};
    }
  }
  if (operation === 'locate_profile' || operation === 'open_profile') {
    const cards=[...document.querySelectorAll('[data-geekid]')].filter(e=>e.getAttribute('data-geekid')===args.geek_id && e.getClientRects().length);
    if (operation === 'locate_profile') return cards.length;
    if(cards.length!==1) throw new Error('候选人卡片缺失或重复，未操作');
    const card=cards[0];
    const candidates=[...card.querySelectorAll('[class*="name"], [class*="info"], [class*="content"]')];
    const opener=candidates.find(e=>e.getClientRects().length && (e.innerText||'').trim() &&
      !/^(BUTTON|A)$/.test(e.tagName) && !e.closest('button,a') && !/(立即沟通|继续沟通|打招呼|聊天|联系|收藏|点赞|分享)/.test(e.innerText||''));
    if(!opener) throw new Error('无法安全确定简历详情入口，未点击任何按钮');
    opener.click();
    return {opened:true,geek_id:args.geek_id};
  }
  if (operation === 'profile_snapshot') {
    const requests=performance.getEntriesByType('resource').filter(e=>{
      try {return new URL(e.name).pathname==='/wapi/zpjob/view/geek/info';}catch{return false;}
    }).slice(-12).map(e=>{const u=new URL(e.name);return {path:u.pathname,params:Object.fromEntries(u.searchParams),startTime:e.startTime};});
    const sections=[...document.querySelectorAll('[class*="resume"], [class*="geek-detail"]')]
      .filter(e=>e.getClientRects().length && (e.innerText||'').length>80)
      .map(e=>({className:String(e.className),text:e.innerText}));
    const tap=globalThis.__bossResumeTap;
    const firstCard=document.querySelector('[data-geekid]');
    const listLayout=[];
    for(let e=firstCard?.parentElement;e && listLayout.length<12;e=e.parentElement) {
      listLayout.push({tag:e.tagName,className:String(e.className),height:e.clientHeight,total:e.scrollHeight,
        top:e.scrollTop,overflow:getComputedStyle(e).overflowY});
    }
    const closeControls=[...document.querySelectorAll('[class*="close"],[aria-label="关闭"],[title="关闭"]')]
      .filter(e=>e.getClientRects().length).map(e=>({tag:e.tagName,className:String(e.className),label:e.getAttribute('aria-label')||e.getAttribute('title')||''})).slice(0,30);
    return {greeting_protocol:2,url:location.href,text:document.body?.innerText||'',sections,requests,listLayout,closeControls,
      resumeTap:tap?{parseCount:tap.parseCount,drawCount:tap.drawCount,
        details:tap.details,drawnText:tap.drawnText,messages:tap.messages}:null};
  }
  if (operation === 'chat_probe' || operation === 'chat_send') {
    if (location.pathname !== '/web/chat/index' || window !== top) throw new Error('请先打开 BOSS 沟通页面');
    if (visible('.login-dialog, .login-register-box, .sign-form, .geetest_panel, .verify-dialog')) throw new Error('页面需要登录或验证');
    const chat=globalThis.iBossRoot?.chat;
    if (operation === 'chat_probe') return {url:location.pathname,available:typeof chat?.sendMessage==='function',
      account_uid:chat?.userInfo?.userId ?? null,chat_keys:Object.keys(chat||{}).slice(0,30),
      user_keys:Object.keys(chat?.userInfo||{}).slice(0,30),send_signature:String(chat?.sendMessage||'').slice(0,350)};
    const {uid,encrypt_uid,friend_source,message}=args;
    if (!Number.isSafeInteger(uid) || uid<=0 || typeof encrypt_uid!=='string' || !/^[A-Za-z0-9_-]{12,100}$/.test(encrypt_uid) ||
        !Number.isSafeInteger(friend_source) || friend_source<0 || friend_source>100 || typeof message!=='string' ||
        message.trim()!==message || message.length<1 || message.length>500) throw new Error('消息目标或正文无效，未发送');
    if (typeof chat?.sendMessage!=='function' || !String(chat.sendMessage).includes('getFriendById')) throw new Error('页面聊天客户端未就绪，未发送');
    if (Date.now()>=deadline-1500) throw new Error('发送请求已过期，未发送');
    await chat.sendMessage(message,'text',{uid,encryptUid:encrypt_uid,friendSource:friend_source});
    return {invoked:true,uid,detail:'已调用页面聊天发送函数；须通过历史消息接口核实送达'};
  }
  if (operation !== 'api') throw new Error('不支持的页面操作');
  // No arbitrary scripts or destinations. The worker validates the exact route.
  if (!args.path.startsWith('/wapi/') || args.path.includes('..') || args.path.includes('://')) throw new Error('非法接口');
  return await new Promise((resolve,reject)=>{
    const xhr=new XMLHttpRequest();
    const query=new URLSearchParams(args.params || {}).toString();
    xhr.open(args.method,args.path+(query?'?'+query:''),true);
    xhr.withCredentials=true;
    xhr.timeout=Math.max(1, Math.min(20000,deadline-Date.now()-250));
    xhr.setRequestHeader('X-Requested-With','XMLHttpRequest');
    const bst=document.cookie.split('; ').find(x=>x.startsWith('bst='));
    if (bst) xhr.setRequestHeader('zp_token',decodeURIComponent(bst.slice(4)));
    let body=null;
    if (args.method === 'POST') {
      xhr.setRequestHeader('Content-Type',args.json ? 'application/json' : 'application/x-www-form-urlencoded; charset=UTF-8');
      body=args.json ? JSON.stringify(args.json) : new URLSearchParams(args.data || {}).toString();
    }
    xhr.onload=()=>{
      let parsed=null;
      try {parsed=JSON.parse(xhr.responseText);} catch { /* Never return HTML or cookie headers. */ }
      resolve({status:xhr.status,body:parsed,retry_after:xhr.getResponseHeader('Retry-After')});
    };
    xhr.onerror=()=>reject(new Error('页面请求失败，动作结果未知；不要直接重发'));
    xhr.ontimeout=()=>reject(new Error('页面请求超时，动作结果未知；不要直接重发'));
    if (Date.now() >= deadline) return reject(new Error('操作已过期，未执行'));
    xhr.send(body);
  });
}
