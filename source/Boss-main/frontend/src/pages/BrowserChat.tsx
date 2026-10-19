import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';

type Account = { id:number; name:string; connection_type:string; is_logged_in:boolean };
type Preview = { preview_id:string; name:string; conversation_id:string };
type Receipt = { id:string; name:string; message:string; status:string; detail:string; created_at:string };
const statusLabel:Record<string,string> = { not_sent:'未点击发送', sending:'正在发送', observed:'页面已出现消息', unknown:'结果未知，请核对 BOSS' };

export default function BrowserChat() {
  const [accounts,setAccounts]=useState<Account[]>([]);
  const [account,setAccount]=useState('');
  const [preview,setPreview]=useState<Preview|null>(null);
  const [message,setMessage]=useState('');
  const [history,setHistory]=useState<Receipt[]>([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const pending=useRef(false);
  useEffect(()=>{
    let disposed=false;
    Promise.all([api.get<Account[]>('/api/boss-accounts'),api.get<Receipt[]>('/api/chat/history')]).then(([a,h])=>{
      if(disposed) return;
      const supported=a.filter(x=>x.connection_type==='extension' && x.is_logged_in);
      setAccounts(supported); setAccount(supported.length===1?String(supported[0].id):''); setHistory(h);
    }).catch(e=>{if(!disposed)setError(String(e.message));});
    return ()=>{disposed=true;};
  },[]);
  async function read() {
    if(pending.current) return;
    pending.current=true; setBusy(true); setError(''); setPreview(null);
    try {setPreview(await api.post<Preview>('/api/chat/preview',{account_id:Number(account)}));}
    catch(e){setError(e instanceof Error?e.message:String(e));}
    finally{pending.current=false;setBusy(false);}
  }
  async function send() {
    if(!preview || pending.current || !message.trim()) return;
    pending.current=true; setBusy(true); setError('');
    const selected=preview; setPreview(null);
    try {
      const result=await api.post<Receipt>('/api/chat/send',{preview_id:selected.preview_id,message:message.trim()},20000);
      setHistory(h=>[result,...h.filter(x=>x.id!==result.id)]);
      if(result.status==='observed')setMessage('');
    } catch(e){setError(`${e instanceof Error?e.message:String(e)}。请在 BOSS 核对结果，不要直接重复发送。`);}
    finally{pending.current=false;setBusy(false);}
  }
  return <div className="space-y-5">
    <section className="glass-panel p-6 space-y-4">
      <h3 className="text-xl font-semibold">向当前 BOSS 会话发送文字</h3>
      <p className="text-sm text-slate-400">先在 Chrome 的 BOSS 聊天页打开目标联系人，再读取当前会话。首次使用需在 chrome://extensions 重新加载“BOSS 本地招聘连接器”，连接后到系统设置重新接入聊天标签页。</p>
      <label className="block">接入账号
        <select aria-label="接入账号" className="mt-2 block w-full rounded-lg bg-slate-900 p-3" value={account} disabled={busy} onChange={e=>{setAccount(e.target.value);setPreview(null);}}>
          <option value="">请选择 Chrome 插件账号</option>
          {accounts.map(a=><option key={a.id} value={a.id}>{a.name || `账号 ${a.id}`}</option>)}
        </select>
      </label>
      <button className="rounded-lg bg-slate-700 px-4 py-2 disabled:opacity-40" disabled={!account||busy} onClick={read}>读取当前会话</button>
      {preview && <div className="rounded-lg border border-emerald-500/30 p-4">收件人：<strong>{preview.name}</strong><p className="text-xs text-slate-400 mt-1">会话标识：{preview.conversation_id} · 预览 5 分钟内有效</p></div>}
      <label className="block">消息内容
        <textarea aria-label="消息内容" className="mt-2 block w-full rounded-lg bg-slate-900 p-3" rows={5} maxLength={2000} value={message} disabled={busy} onChange={e=>setMessage(e.target.value)} placeholder="输入要发送的文字，最多 2000 字符" />
      </label>
      <button className="rounded-lg bg-emerald-600 px-4 py-2 disabled:opacity-40" disabled={!preview||!message.trim()||busy} onClick={send}>{busy?'处理中…':preview?`发送给 ${preview.name}`:'请先读取会话'}</button>
      <p className="text-xs text-slate-400">每次发送后需重新读取会话。程序不会覆盖 BOSS 输入框已有的草稿，也不会自动重发。页面出现消息不代表对方已收到或已读。</p>
      {error&&<p role="alert" className="text-rose-300 whitespace-pre-wrap">{error}</p>}
    </section>
    <section className="glass-panel p-6 space-y-3">
      <div className="flex justify-between"><h3 className="text-lg font-semibold">本地发送记录（最近 50 条）</h3><button disabled={busy} onClick={()=>api.get<Receipt[]>('/api/chat/history').then(setHistory).catch(e=>setError(e.message))}>刷新记录</button></div>
      {!history.length&&<p className="text-slate-400">暂无记录。这不是 BOSS 历史聊天记录同步。</p>}
      {history.map(h=><article key={h.id} className="rounded-lg border border-white/10 p-4"><p>{h.name} · {statusLabel[h.status]||h.status}</p><p className="whitespace-pre-wrap my-2">{h.message}</p><p className="text-xs text-slate-400">{h.detail}</p></article>)}
    </section>
  </div>;
}
