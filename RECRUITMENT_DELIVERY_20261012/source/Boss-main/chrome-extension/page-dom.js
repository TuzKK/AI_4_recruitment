// This function is serialized by chrome.scripting. Keep it self-contained.
export async function pageOperation(operation, args = {}) {
  if (location.protocol !== 'https:' || !['www.zhipin.com', 'zhipin.com'].includes(location.hostname)) {
    throw new Error('只支持 BOSS 直聘页面');
  }
  const visible = el => !!el && !!el.getClientRects().length &&
    getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
  const any = selector => [...document.querySelectorAll(selector)].some(visible);
  const text = selector => [...document.querySelectorAll(selector)].find(visible)?.textContent?.trim().slice(0,100) || '';
  const auth = {
    url: location.origin + location.pathname,
    verify: any('.geetest_panel, .geetest_holder, .verify-dialog, #captcha'),
    login: any('.login-dialog, .login-register-box, .sign-form'),
    content: any('.recommend-main, .boss-chat, .resume-list, li.card-item, .chat-container, .chat-conversation'),
    name: text('.nav-figure .nav-name, .nav-figure .name, .boss-name'),
    company: text('.nav-figure .nav-company'),
  };
  if (operation === 'inspect') return auth;
  if (auth.login || auth.verify || /\/login|\/web\/user\/|\/verify/.test(location.pathname)) {
    throw new Error('页面需要登录或人工验证，已停止操作');
  }
  const cards = [...document.querySelectorAll('li.card-item')].filter(visible);
  if (operation === 'cards') {
    return cards.map((card, i) => {
      const t = selector => card.querySelector(selector)?.textContent?.trim() || '';
      return {
        geek_id: card.querySelector('.card-inner')?.getAttribute('data-geekid') || '',
        name: t('.name'), active: t('.active-text'), salary: t('.salary-wrap span'),
        base_info: t('.base-info'), expect: t('.expect-wrap .content'),
        expect_city: t('.expect-wrap .content'), advantages: t('.geek-desc .content'),
        work_experience: [...card.querySelectorAll('.work-experience, .work-item')].map(x => x.textContent.trim()),
        tags: [...card.querySelectorAll('.tag-item')].map(x => x.textContent.trim()),
        _search_text: card.innerText, greet_btn_index: i,
      };
    }).filter(card => card.name && card.geek_id);
  }
  if (operation === 'locate' || operation === 'greet') {
    const matches = cards.filter(c => c.querySelector('.card-inner')?.getAttribute('data-geekid') === args.geek_id);
    if (operation === 'locate') return matches.length;
    if (matches.length !== 1) throw new Error('候选人卡片已变化，请重新检查页面');
    const card = matches[0];
    const buttons = [...card.querySelectorAll('button, a.btn-greet, [role="button"]')]
      .filter(b => visible(b) && b.textContent.trim() === '打招呼' && !b.disabled && b.getAttribute('aria-disabled') !== 'true');
    if (buttons.length !== 1) return false;
    if (!Number.isFinite(args.deadline) || Date.now() > args.deadline) throw new Error('操作已过期，未发送');
    buttons[0].click(); // Exactly once; never retry an uncertain send.
    for (let i=0; i<12; i++) {
      if ([...card.querySelectorAll('button, a, [role="button"]')].some(b => visible(b) && b.textContent.trim() === '继续沟通')) return true;
      await new Promise(resolve => setTimeout(resolve,250));
    }
    throw new Error('已点击打招呼但结果未确认，任务停止；请人工检查，程序不会重复发送');
  }
  if (operation === 'scroll') {
    cards.at(-1)?.scrollIntoView({block:'end',behavior:'instant'});
    return cards.length > 0;
  }
  throw new Error('不支持的页面操作');
}
