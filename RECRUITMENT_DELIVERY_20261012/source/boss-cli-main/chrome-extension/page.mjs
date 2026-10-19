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
    return {url:location.href,text:document.body?.innerText||'',sections,requests};
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
