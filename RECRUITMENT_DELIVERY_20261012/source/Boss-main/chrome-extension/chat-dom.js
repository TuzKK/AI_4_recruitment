// Serialized into the isolated extension world; never accepts arbitrary selectors/code.
export async function chatOperation(operation, args = {}) {
  let clicked = false;
  try {
  if (['chat_preview','chat_diagnostics'].includes(operation) && (location.protocol !== 'https:' || !['www.zhipin.com','zhipin.com'].includes(location.hostname))) return null;
  const visible = e => !!e && !!e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden' && getComputedStyle(e).display !== 'none';
  const all = (s, root = document) => [...root.querySelectorAll(s)].filter(visible);
  const one = (s, root = document) => { const found = all(s, root); return found.length === 1 ? found[0] : null; };
  const normalize = s => String(s || '').replace(/\r\n/g, '\n').trim();
  function authorized() {
    if (location.protocol !== 'https:' || !['www.zhipin.com','zhipin.com'].includes(location.hostname)) throw new Error('不是 BOSS 页面');
    const docs = [document];
    try { if (top.document !== document) docs.push(top.document); } catch {}
    if (docs.some(d => all('.login-dialog, .login-register-box, .sign-form, .geetest_panel, .geetest_holder, .verify-dialog, #captcha', d).length)) throw new Error('页面需要登录或验证，已取消发送');
  }
  function current() {
    const panel = one('.chat-conversation');
    if (!panel) return null;
    const modernEditor=one('#boss-chat-editor-input',panel);
    if (modernEditor) {
      const selected=one('.geek-item.selected');
      const id=selected?.getAttribute('data-id');
      const nameNode=one('.base-name .name-container',panel);
      const name=normalize(one('.base-name .name-box',panel)?.textContent);
      const nameProps=nameNode?.__vue__?.$props;
      const messageVm=one('.conversation-message',panel)?.__vue__;
      const editorVm=one('.conversation-editor',panel)?.__vue__;
      const uid=id?.match(/^(\d+)-\d+$/)?.[1];
      const button=one('.conversation-editor .submit',panel);
      if (!uid || !name || String(nameProps?.geekId)!==uid || String(messageVm?.$data?.geek?.uid)!==uid ||
          !editorVm?.$parent || editorVm.$parent!==messageVm?.$parent ||
          normalize(one('.geek-name',selected)?.textContent)!==name || !button || !/^发送(?:\s*[（(][sS][）)])?$/.test(normalize(button.textContent))) return null;
      return {selected,panel,id,name,editor:modernEditor,button,editorVm};
    }
    const selected = one('.user-list li.selected, .user-list li.active, .user-list .user-item.selected, .user-list .user-item.active');
    if (!selected) return null;
    const recipientId = e => e && ['data-conversation-id','data-uid','data-geekid','data-geek-id','data-id'].map(k=>e.getAttribute(k)).find(Boolean);
    const id = recipientId(selected);
    const panelId = recipientId(panel) || recipientId(one('.chat-user, .chat-header, .conversation-header',panel));
    if (!id || panelId !== id) return null;
    const name = normalize(one('.chat-user .name, .chat-header .name, .conversation-header .name',panel)?.textContent);
    const editor = one('#chat-input, textarea.chat-input, [contenteditable="true"].chat-input',panel);
    const send = all('button, a.btn-send, .btn-send',panel).filter(e=>normalize(e.textContent)==='发送');
    if (!name || !editor || send.length!==1) return null;
    return {selected,panel,id,name,editor,button:send[0]};
  }
  function value(editor) { return normalize('value' in editor ? editor.value : editor.innerText); }
  function hasAttachments(state) {
    return !!state.editor.querySelector('img,svg,video,audio,canvas,a,[data-attachment],[data-emoji]') ||
      !!state.editorVm?.$data?.files?.length ||
      all('.attachment-list > *, .upload-list > *, .file-list > *, .image-preview, .upload-preview',state.panel).length>0;
  }
  function hasDraft(state) {
    const e=state.editor;
    return !!('value' in e ? e.value : e.textContent) || hasAttachments(state);
  }
  function matches(a,b) { return b && a.selected===b.selected && a.panel===b.panel && a.id===b.id && a.name===b.name && a.editor===b.editor && a.button===b.button; }
  authorized();
  if (operation === 'chat_diagnostics') {
    const attrs=e=>Object.fromEntries([...e.attributes].filter(a=>['id','class','role','contenteditable','type'].includes(a.name)||a.name.startsWith('data-')).map(a=>[a.name,a.value.slice(0,180)]));
    const identity=(value,depth=0)=>{
      if (!value || typeof value!=='object' || depth>3 || Array.isArray(value)) return undefined;
      const result={};
      for (const key of Object.keys(value)) {
        if (/^(uid|geekId|friendId|userId|encryptUid|name|geekName|userName|jobId|conversationId)$/i.test(key) && ['string','number'].includes(typeof value[key])) result[key]=String(value[key]).slice(0,100);
        else if (/^(current|active|selected|chat|friend|geek|user|info|data)/i.test(key)) { const nested=identity(value[key],depth+1); if(nested && Object.keys(nested).length)result[key]=nested; }
      }
      return result;
    };
    const roots=[...all('.chat-conversation'),...all('.geek-item.selected')];
    const nodes=[...new Set(roots.flatMap(r=>[r,...r.querySelectorAll('*')]))].filter(visible).slice(0,700);
    return {url:location.pathname,nodes:nodes.map(e=>({tag:e.tagName,attrs:attrs(e),parent:attrs(e.parentElement),text:/BUTTON/.test(e.tagName)||/name-box|geek-name|btn-send|submit/.test(e.className)?(e.textContent||'').trim().slice(0,80):'',vueKeys:Object.keys(e.__vue__?.$data||e.__vueParentComponent?.setupState||{}),vueIdentity:identity(e.__vue__?.$data||e.__vueParentComponent?.setupState),vueProps:identity(e.__vue__?.$props||e.__vueParentComponent?.props),vueParentKeys:Object.keys(e.__vue__?.$parent?.$data||{}),vueParentIdentity:identity(e.__vue__?.$parent?.$data),isChatChild:!!e.__vue__?.$parent && e.__vue__.$parent===document.querySelector('.conversation-message')?.__vue__?.$parent})),editors:all('textarea,[contenteditable=true]').map(e=>({tag:e.tagName,attrs:attrs(e),parent:attrs(e.parentElement)}))};
  }
  const state = current();
  if (operation === 'chat_preview') {
    if (!state) return null;
    const token = crypto.randomUUID();
    globalThis.__bossLocalChatPreview = {...state, token, expires:Date.now()+300000};
    return {token, name:state.name, conversation_id:state.id, has_draft:hasDraft(state)};
  }
  if (operation !== 'chat_send') throw new Error('不支持的聊天操作');
  const saved = globalThis.__bossLocalChatPreview;
  if (!saved || saved.token !== args.token || Date.now() > saved.expires) throw new Error('会话预览已失效或已使用，请重新读取');
  // Consume before any potential write, including failed attempts.
  delete globalThis.__bossLocalChatPreview;
  if (!matches(saved,state)) throw new Error('当前会话已变化，未发送');
  const message = normalize(args.message);
  if (!message || message.length > 2000) throw new Error('消息须为 1–2000 字符');
  if (!Number.isFinite(args.deadline) || Date.now() > args.deadline) throw new Error('发送请求已过期');
  if (hasDraft(state)) throw new Error('BOSS 输入框中已有草稿，请先处理，程序不会覆盖');
  if (state.editor.disabled || state.editor.readOnly || (!('value' in state.editor) && !state.editor.isContentEditable)) throw new Error('聊天输入框不可编辑');
  const outgoing = () => all('.message-item .item-myself .text, .message-item.is-self .text, .message-item.is-self .text-content, .message-item.is-self .message-text, .message-item.item-myself .text, .message-item.myself .text', state.panel).filter(e => (normalize(e.innerText) === message || normalize(e.textContent) === message));
  const messageId = e => {
    const row=e.closest('.message-item');
    const props=row?.__vue__?.$props;
    const model=props?.message || props?.msg;
    return row && (['data-message-id','data-mid','data-id','id'].map(k=>row.getAttribute(k)).find(Boolean) || (model?.mid ? String(model.mid) : null));
  };
  const before = new Set(outgoing().map(messageId).filter(Boolean));
  const beforeCount = outgoing().length;
  if ('value' in state.editor) {
    const proto = state.editor.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto,'value').set.call(state.editor,message);
  } else {
    state.editor.innerText = message;
  }
  state.editor.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:message}));
  state.editor.dispatchEvent(new Event('change',{bubbles:true}));
  await new Promise(resolve=>setTimeout(resolve,150));
  authorized();
  if (!matches(saved,current())) throw new Error('输入期间会话发生变化，未点击发送，请检查页面草稿');
  if (hasAttachments(state)) throw new Error('输入期间出现附件或图片，未点击发送，请检查页面草稿');
  if (state.editorVm?.$data?.disabled) throw new Error('输入后发送按钮仍被禁用，未点击发送');
  if (value(state.editor)!==message) throw new Error('输入内容已变化，未点击发送');
  if (Date.now()>args.deadline) throw new Error('发送请求已过期，未点击发送');
  if (state.button.disabled || state.button.getAttribute('aria-disabled')==='true' || state.button.classList.contains('disabled')) throw new Error('发送按钮不可用');
  clicked = true;
  state.button.click();
  for (let i=0;i<12 && Date.now()<args.deadline;i++) {
    if (!matches(saved,current())) return {status:'unknown',detail:'点击后会话变化，请在 BOSS 中核对，勿重复发送'};
    if (outgoing().length > beforeCount && outgoing().some(e=>messageId(e) && !before.has(messageId(e))) && !value(state.editor)) return {status:'observed',detail:'页面出现新的本人消息；不代表对方已收到或已读'};
    await new Promise(resolve=>setTimeout(resolve,250));
  }
  return {status:'unknown',detail:'已点击发送，但未确认新增消息，请在 BOSS 中核对，勿重复发送'};
  } catch (error) {
    return {status:clicked?'unknown':'not_sent',detail:String(error?.message || error),chat_error:true};
  }
}

