import { useState } from "react";
import { api } from "../api/client";
type BrowserPage = { cdp_url: string; target_id: string; url: string; state: string; name: string; company: string; connection_type?: string };
type Discovery = { pages: BrowserPage[]; ordinary_chrome_count: number; warning: string };
type Pairing = { token: string; extension_path: string; connected_browsers: number };
const labels: Record<string, string> = { logged_in: "已登录招聘者账号", not_logged_in: "尚未登录", verification_required: "需要人工验证", wrong_role: "请切换招聘者端", unknown: "未确认登录，请打开牛人推荐页" };
export default function ChromeConnect({ onConnected }: { onConnected: () => Promise<void> }) {
  const [port, setPort] = useState("");
  const [result, setResult] = useState<Discovery | null>(null);
  const [pairing, setPairing] = useState<Pairing | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function prepare() {
    setBusy(true); setMessage("");
    try { setPairing(await api.get<Pairing>("/api/browser-extension/pairing")); }
    catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }
  async function copy(value: string, label: string) {
    try { await navigator.clipboard.writeText(value); setMessage(`${label}已复制`); }
    catch { setMessage("剪贴板不可用，请选中对应文本手动复制。"); }
  }
  async function scan() {
    setBusy(true); setMessage("");
    try {
      if (port && (!/^\d+$/.test(port) || Number(port) < 1 || Number(port) > 65535)) throw new Error("调试端口应为 1–65535 的整数");
      setResult(await api.get<Discovery>("/api/boss-accounts/discover" + (port ? `?port=${port}` : "")));
    } catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }
  async function connect(page: BrowserPage) {
    setBusy(true); setMessage("");
    try {
      await api.post("/api/boss-accounts/connect", { cdp_url: page.cdp_url, target_id: page.target_id });
      setMessage("已成功接入该 BOSS 页面。新建任务时请选择此账号。");
      await onConnected();
    } catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="space-y-4 rounded-2xl border border-white/10 p-4">
    <h3 className="font-semibold text-slate-100">接入现有 Chrome · 保留当前登录</h3>
    <p className="text-sm leading-6 text-slate-400">普通启动的 Chrome 请先加载本地连接扩展，无需开启调试端口、重启浏览器或重新登录。已开启调试端口的 Chrome 可直接检测。</p>
    <div className="flex flex-wrap items-center gap-3">
      <button type="button" disabled={busy} onClick={prepare} className="rounded-xl border border-cyan-300/40 px-4 py-2 text-sm text-cyan-200 disabled:opacity-50">首次接入：获取扩展配对信息</button>
      <button type="button" disabled={busy} onClick={scan} className="rounded-xl bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50">{busy ? "正在检测或连接…" : "检测已打开的 Chrome"}</button>
    </div>
    {pairing && <div className="space-y-3 rounded-xl bg-slate-900 p-4 text-sm text-slate-300">
      <ol className="list-inside list-decimal space-y-2">
        <li>在当前 Chrome 打开 <code>chrome://extensions</code>，开启开发者模式，点击“加载已解压的扩展程序”。</li>
        <li>选择下面的扩展文件夹；无需关闭 BOSS 页面。</li>
        <li>点击 Chrome 扩展图标“BOSS 本地招聘连接器”，粘贴配对码并连接。</li>
        <li>回到本页点击“检测已打开的 Chrome”，选择显示“已登录”的页面并接入。</li>
      </ol>
      <label className="block">扩展文件夹<input aria-label="扩展文件夹" readOnly value={pairing.extension_path} className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 p-2 text-xs" /></label>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={()=>copy(pairing.extension_path,"扩展路径")} className="rounded-lg bg-white/10 px-3 py-2">复制扩展路径</button>
        <button type="button" onClick={()=>copy(pairing.token,"配对码")} className="rounded-lg bg-cyan-300 px-3 py-2 font-semibold text-slate-950">复制配对码</button>
      </div>
      <label className="block text-xs text-slate-400">配对码（也可选中后手动复制）<input aria-label="扩展配对码" readOnly type="password" value={pairing.token} className="mt-1 w-full rounded-lg border border-white/10 bg-slate-950 p-2" /></label>
      <p className="text-xs text-slate-400">连接与检测只读取页面状态。页面刷新或浏览器重启后，请重新检测接入；不会自动发送消息。</p>
    </div>}
    <details className="text-xs text-slate-400"><summary className="cursor-pointer">已有调试端口（可选）</summary><input aria-label="Chrome 调试端口（可选）" type="number" min="1" max="65535" placeholder="如 9222" value={port} onChange={e => setPort(e.target.value)} className="mt-2 rounded-xl border border-white/10 bg-slate-900 px-3 py-2 text-sm" /></details>
    {result && <div className="space-y-2">
      {result.ordinary_chrome_count > 0 && <p className="text-sm text-slate-300">发现 {result.ordinary_chrome_count} 个普通 Chrome 主进程。未显示 BOSS 页面时，请在该浏览器中完成扩展配对。</p>}
      {result.warning && <p className="text-sm text-amber-200">{result.warning}</p>}
      {result.pages.length === 0 && <p className="text-sm text-slate-300">尚无可接入的 BOSS 页面。请完成扩展配对，保持已登录的 BOSS 招聘页打开后重新检测。</p>}
      {result.pages.map(page => <div key={page.cdp_url + page.target_id} className="flex items-center justify-between gap-3 rounded-xl bg-white/5 p-3">
        <div className="min-w-0 text-sm"><p>{page.name || "BOSS 招聘页面"} {page.company} · {labels[page.state] || page.state}</p><p className="break-all text-xs text-slate-400">{page.connection_type === "extension" ? "现有 Chrome（扩展连接）" : page.cdp_url} · {page.url}</p></div>
        <button type="button" disabled={busy || page.state !== "logged_in"} onClick={() => connect(page)} className="shrink-0 rounded-lg border border-cyan-300/40 px-3 py-2 text-sm text-cyan-200 disabled:opacity-40">接入此页面</button>
      </div>)}
    </div>}
    {message && <p role="status" className="text-sm text-cyan-100">{message}</p>}
  </div>;
}
