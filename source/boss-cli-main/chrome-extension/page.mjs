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
    return [...document.querySelectorAll('[data-geekid]')].filter(e=>e.getClientRects().length).map(e=>({
      geek_id:e.getAttribute('data-geekid'),
      name:e.querySelector('[class*="name"]')?.textContent?.trim() || '', text:e.innerText || ''
    })).filter(e=>e.geek_id && e.text.length>=30);
  }
  if (operation === 'locate_greet' || operation === 'greet') {
    if (location.pathname !== '/web/chat/recommend') throw new Error('请先打开牛人推荐页面');
    if (visible('.login-dialog, .login-register-box, .sign-form, .geetest_panel, .verify-dialog')) throw new Error('页面需要登录或验证，未发送');
    const cards=[...document.querySelectorAll('[data-geekid]')].filter(e=>e.getAttribute('data-geekid')===args.geek_id && e.getClientRects().length);
    if (operation === 'locate_greet') return cards.length;
    if (cards.length!==1) throw new Error('候选人卡片缺失或重复，未发送');
    const card=cards[0];
    const actions=()=>[...card.querySelectorAll('button, a, [role="button"]')].filter(e=>e.getClientRects().length);
    const buttons=actions().filter(e=>e.textContent.trim()==='打招呼' && !e.disabled && e.getAttribute('aria-disabled')!=='true');
    if (buttons.length!==1) throw new Error('打招呼按钮不可用或不唯一，未发送');
    if (Date.now()>=deadline-1500) throw new Error('操作已过期，未发送');
    buttons[0].click();
    for(let i=0;i<12 && Date.now()<deadline-300;i++) {
      if(actions().some(e=>e.textContent.trim()==='继续沟通')) return {status:'observed',candidate_id:args.geek_id};
      await new Promise(resolve=>setTimeout(resolve,250));
    }
    throw new Error('已点击打招呼但结果未确认，请人工核查，不自动重发');
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
    return {url:location.href,text:document.body?.innerText||'',sections,requests,
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
      resolve({status:xhr.status,body:parsed});
    };
    xhr.onerror=()=>reject(new Error('页面请求失败，动作结果未知；不要直接重发'));
    xhr.ontimeout=()=>reject(new Error('页面请求超时，动作结果未知；不要直接重发'));
    if (Date.now() >= deadline) return reject(new Error('操作已过期，未执行'));
    xhr.send(body);
  });
}
