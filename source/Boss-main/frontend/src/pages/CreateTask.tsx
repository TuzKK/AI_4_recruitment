import { useEffect, useState, useSyncExternalStore } from "react";
import { useNavigate } from "react-router-dom";
import {
  api,
  analyzePosition,
  createTask,
} from "../api/client";
import {
  Search,
  Sparkles,
  Settings,
  Rocket,
  ChevronRight,
  ChevronLeft,
  Loader2,
  X,
  Plus,
} from "lucide-react";
import { useToast } from "../hooks/useToast";
import { getTaskDraftSnapshot, subscribeTaskDraft, updateTaskDraft, resetTaskDraft, setAnalysisPending, type TaskDraft } from "../state/taskDraft";

const STEPS = [
  { icon: Search, label: "输入岗位" },
  { icon: Sparkles, label: "AI 分析" },
  { icon: Settings, label: "配置参数" },
  { icon: Rocket, label: "确认启动" },
];

export default function CreateTask() {
  const navigate = useNavigate();
  const { pushToast } = useToast();
  const [accounts, setAccounts] = useState<{ id: number; name: string; is_logged_in: boolean }[]>([]);
  const { draft, analysisPending, storageError } = useSyncExternalStore(subscribeTaskDraft, getTaskDraftSnapshot);
  const { accountId, step, title, description, analysis, editableKeywords, newKeyword, dailyLimit, threshold, startHour, endHour } = draft;
  const setField = <K extends keyof TaskDraft>(key: K, value: TaskDraft[K]) => updateTaskDraft({[key]:value});
  const setAccountId = (value: string) => setField("accountId", value);
  const setStep = (value: number) => setField("step", value);
  const setTitle = (value: string) => setField("title", value);
  const setDescription = (value: string) => setField("description", value);
  const setEditableKeywords = (value: string[]) => setField("editableKeywords", value);
  const setNewKeyword = (value: string) => setField("newKeyword", value);
  const setDailyLimit = (value: number) => setField("dailyLimit", value);
  const setThreshold = (value: number) => setField("threshold", value);
  const setStartHour = (value: string) => setField("startHour", value);
  const setEndHour = (value: string) => setField("endHour", value);
  const [accountError, setAccountError] = useState("");
  useEffect(() => {
    let active = true;
    api.get<{ id: number; name: string; is_logged_in: boolean }[]>("/api/boss-accounts")
      .then(data => { if (active) { setAccounts(data); const ready = data.filter(a => a.is_logged_in); updateTaskDraft(current => ({accountId: current.accountId
        ? (data.some(a => String(a.id) === current.accountId) ? current.accountId : "")
        : (ready.length === 1 ? String(ready[0].id) : "")})); } })
      .catch(error => { if (active) setAccountError((error as Error).message); });
    return () => { active = false; };
  }, []);
  const [launching, setLaunching] = useState(false);
  const loading = launching || analysisPending;
  const autoContact = false;

  async function handleAnalyze() {
    if (!title.trim() || loading) return;
    const submittedRevision = draft.revision;
    setAnalysisPending(true);
    try {
      const result = await analyzePosition(title, description);
      const keywords = [
        ...((result.keywords as { primary_keywords?: string[] }).primary_keywords || []),
        ...((result.keywords as { skill_keywords?: string[] }).skill_keywords || []),
      ];
      const current = getTaskDraftSnapshot().draft;
      if (current.revision === submittedRevision && current.title === title && current.description === description) {
        updateTaskDraft({analysis:result,editableKeywords:keywords,step:1});
      }
    } catch (err) {
      pushToast({
        type: "error",
        title: "AI 分析失败",
        message: (err as Error).message,
      });
    } finally {
      setAnalysisPending(false);
    }
  }

  function addKeyword() {
    if (newKeyword.trim() && !editableKeywords.includes(newKeyword.trim())) {
      setEditableKeywords([...editableKeywords, newKeyword.trim()]);
      setNewKeyword("");
    }
  }

  function removeKeyword(keyword: string) {
    setEditableKeywords(editableKeywords.filter((item) => item !== keyword));
  }

  async function handleLaunch() {
    if (!analysis || loading) return;
    setLaunching(true);
    try {
      if (!accountId) throw new Error("请先在设置中接入并选择 BOSS 账号");
      await createTask(analysis.position_id, {
        account_id: Number(accountId),
        greeting_daily_limit: dailyLimit,
        qualified_threshold: threshold,
        auto_contact_followup: autoContact,
        working_hours_start: startHour,
        working_hours_end: endHour,
        keywords: editableKeywords,
      });
      pushToast({
        type: "success",
        title: "招聘任务已创建",
        message: `岗位 "${title}" 已进入执行队列`,
      });
      updateTaskDraft({step:0});
      navigate("/");
    } catch (err) {
      pushToast({
        type: "error",
        title: "任务启动失败",
        message: (err as Error).message,
      });
    } finally {
      setLaunching(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-5 py-6 lg:px-8">
      <div className="section-shell p-6 lg:p-7">
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Task Composer</p>
        <h1 className="mt-2 text-3xl font-semibold text-white">新建招聘任务</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
          按照岗位输入、AI 解析、参数配置和最终确认四步完成任务创建。Windows 使用已接入的 Chrome 执行推荐卡片筛选和打招呼。浏览器模式暂不支持聊天回复及附件收集。
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 px-1 text-sm">
        <p role="status" className={storageError ? "text-amber-200" : "text-slate-400"}>
          {storageError || "草稿自动保存在当前浏览器，切换页面或刷新后会恢复。"}
        </p>
        <button type="button" disabled={loading} onClick={() => {
          if (window.confirm("清空上次填写的内容和分析结果？已创建的任务不会删除。")) resetTaskDraft();
        }} className="rounded-xl border border-white/10 px-3 py-2 text-slate-300 hover:bg-white/5 disabled:opacity-40">清空草稿</button>
      </div>
      <div className="section-shell space-y-2 p-5">
        <label htmlFor="boss-account" className="block text-sm text-slate-200">执行任务的 BOSS 账号</label>
        <select id="boss-account" value={accountId} onChange={e => setAccountId(e.target.value)} className="w-full rounded-xl border border-white/10 bg-slate-900 p-3">
          <option value="">请选择已接入账号</option>
          {accounts.map(a => <option key={a.id} value={a.id} disabled={!a.is_logged_in}>{a.name} {a.is_logged_in ? "（已连接）" : "（未连接）"}</option>)}
        </select>
        <p className="text-xs text-slate-400">账号需要保持 Chrome 页面打开。未连接时，请到设置中检测接入。</p>
        {accountError && <p className="text-xs text-amber-200">{accountError}</p>}
      </div>
      <div className="section-shell p-5">
        <div className="grid gap-3 md:grid-cols-4">
          {STEPS.map((item, index) => (
            <div
              key={item.label}
              className={`rounded-[22px] border px-4 py-4 ${
                index === step
                  ? "border-cyan-300/30 bg-cyan-300/12"
                  : index < step
                  ? "border-emerald-300/20 bg-emerald-300/8"
                  : "border-white/8 bg-white/4"
              }`}
            >
              <div className="flex items-center gap-3">
                <div className="rounded-2xl bg-slate-950/40 p-2.5">
                  <item.icon
                    size={16}
                    className={
                      index === step
                        ? "text-cyan-200"
                        : index < step
                        ? "text-emerald-200"
                        : "text-slate-400"
                    }
                  />
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">
                    Step {index + 1}
                  </p>
                  <p className="mt-1 text-sm font-semibold text-white">{item.label}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {step === 0 && (
        <div className="section-shell p-6 lg:p-8">
          <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="space-y-5">
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-300">
                  职位名称
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="例如：Quant Trader、量化交易员、Java 后端开发"
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-base text-white outline-none placeholder:text-slate-500"
                  onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-slate-300">
                  补充说明
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="例如：偏高频方向，base 上海，3 年以上经验，偏自营或做市背景"
                  rows={5}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500"
                />
              </div>
              <button
                onClick={handleAnalyze}
                disabled={!title.trim() || loading}
                className="inline-flex items-center gap-2 rounded-2xl bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
                {loading ? "AI 分析中..." : "开始 AI 分析"}
              </button>
            </div>

            <div className="rounded-[28px] border border-white/10 bg-white/5 p-5">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500">What happens next</p>
              <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-300">
                <li>1. 自动生成岗位 JD、职责和要求</li>
                <li>2. 自动提炼 Boss 搜索关键词</li>
                <li>3. 自动给出筛选阈值与执行建议</li>
                <li>4. 选择已接入的 Chrome 账号执行任务</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {step === 1 && analysis && (
        <div className="space-y-6">
          <div className="section-shell p-6">
            <h3 className="text-xl font-semibold text-white">AI 生成的 JD</h3>
            <div className="mt-4 space-y-4 text-sm leading-7 text-slate-300">
              <p>
                <strong className="text-slate-100">职位：</strong>
                {(analysis.jd as { title?: string }).title}
              </p>
              <p>
                <strong className="text-slate-100">概述：</strong>
                {(analysis.jd as { summary?: string }).summary}
              </p>
              <div>
                <strong className="text-slate-100">职责：</strong>
                <ul className="mt-2 list-disc space-y-1 pl-5">
                  {(((analysis.jd as { responsibilities?: string[] }).responsibilities) || []).map(
                    (item, index) => (
                      <li key={index}>{item}</li>
                    )
                  )}
                </ul>
              </div>
              <div>
                <strong className="text-slate-100">要求：</strong>
                <ul className="mt-2 list-disc space-y-1 pl-5">
                  {(((analysis.jd as { requirements?: string[] }).requirements) || []).map(
                    (item, index) => (
                      <li key={index}>{item}</li>
                    )
                  )}
                </ul>
              </div>
            </div>
          </div>

          <div className="section-shell p-6">
            <h3 className="text-xl font-semibold text-white">搜索关键词</h3>
            <p className="mt-2 text-sm text-slate-400">支持手动删改，最终会作为客户端搜索和筛选的参考词库。</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {editableKeywords.map((keyword) => (
                <span
                  key={keyword}
                  className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1.5 text-sm text-cyan-100"
                >
                  {keyword}
                  <button onClick={() => removeKeyword(keyword)} className="text-cyan-200 hover:text-red-300">
                    <X size={14} />
                  </button>
                </span>
              ))}
            </div>
            <div className="mt-4 flex gap-2">
              <input
                type="text"
                value={newKeyword}
                onChange={(e) => setNewKeyword(e.target.value)}
                placeholder="添加关键词"
                className="flex-1 rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-2.5 text-sm text-white outline-none placeholder:text-slate-500"
                onKeyDown={(e) => e.key === "Enter" && addKeyword()}
              />
              <button
                onClick={addKeyword}
                className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2.5 text-slate-100 hover:bg-white/8"
              >
                <Plus size={16} />
              </button>
            </div>
          </div>

          <ActionBar
            backLabel="上一步"
            onBack={() => setStep(0)}
            nextLabel="进入参数配置"
            onNext={() => setStep(2)}
          />
        </div>
      )}

      {step === 2 && (
        <div className="space-y-6">
          <div className="section-shell p-6">
            <h3 className="text-xl font-semibold text-white">运行参数配置</h3>
            <div className="mt-5 grid gap-5 md:grid-cols-2">
              <Field label="每日打招呼上限" hint="Boss 直聘限制 100 次/天，建议设置 80 左右">
                <input
                  type="number"
                  value={dailyLimit}
                  onChange={(e) => setDailyLimit(Number(e.target.value))}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-white outline-none"
                  min={1}
                  max={100}
                />
              </Field>
              <Field label="评分达标阈值" hint="推荐卡片 AI 初筛评分达标后打招呼">
                <input
                  type="number"
                  value={threshold}
                  onChange={(e) => setThreshold(Number(e.target.value))}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-white outline-none"
                  min={0}
                  max={100}
                />
              </Field>
              <Field label="工作时段" hint="原项目尚未实现时段调度，当前任务会立即执行">
                <div className="flex items-center gap-2">
                  <input
                    type="time"
                    value={startHour}
                    onChange={(e) => setStartHour(e.target.value)}
                    className="rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-white outline-none"
                  />
                  <span className="text-slate-500">至</span>
                  <input
                    type="time"
                    value={endHour}
                    onChange={(e) => setEndHour(e.target.value)}
                    className="rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-3 text-sm text-white outline-none"
                  />
                </div>
              </Field>
              <Field label="自动跟进联系方式" hint="浏览器模式尚未实现此功能">
                <label className="flex items-center gap-3 text-sm text-slate-200">
                  <input
                    type="checkbox"
                    checked={autoContact}
                    disabled
                    className="h-4 w-4 rounded border-white/20 bg-slate-950/40"
                  />
                  {autoContact ? "已开启" : "已关闭"}
                </label>
              </Field>
            </div>
          </div>

          <ActionBar
            backLabel="返回关键词"
            onBack={() => setStep(1)}
            nextLabel="查看启动摘要"
            onNext={() => setStep(3)}
          />
        </div>
      )}

      {step === 3 && analysis && (
        <div className="space-y-6">
          <div className="section-shell p-6">
            <h3 className="text-xl font-semibold text-white">确认并启动</h3>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <SummaryCard label="职位名称" value={title} />
              <SummaryCard label="搜索关键词" value={`${editableKeywords.length} 个`} />
              <SummaryCard label="每日上限" value={`${dailyLimit} 次/天`} />
              <SummaryCard label="达标阈值" value={`${threshold} 分`} />
              <SummaryCard label="工作时段" value={`${startHour} ~ ${endHour}`} />
              <SummaryCard label="自动获取联系方式" value={autoContact ? "开启" : "关闭"} />
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => setStep(2)}
              className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-medium text-slate-100 hover:bg-white/8"
            >
              <ChevronLeft size={16} />
              返回参数配置
            </button>
            <button
              onClick={handleLaunch}
              disabled={loading}
              className="flex-1 rounded-2xl bg-emerald-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span className="inline-flex items-center gap-2">
                {loading ? <Loader2 size={18} className="animate-spin" /> : <Rocket size={18} />}
                {loading ? "启动中..." : "开始招聘"}
              </span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-[24px] border border-white/8 bg-white/4 p-4">
      <label className="block text-sm font-medium text-slate-200">{label}</label>
      <div className="mt-3">{children}</div>
      <p className="mt-2 text-xs leading-5 text-slate-500">{hint}</p>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[24px] border border-white/8 bg-white/4 p-4">
      <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{label}</p>
      <p className="mt-2 text-lg font-semibold text-white">{value}</p>
    </div>
  );
}

function ActionBar({
  backLabel,
  onBack,
  nextLabel,
  onNext,
}: {
  backLabel: string;
  onBack: () => void;
  nextLabel: string;
  onNext: () => void;
}) {
  return (
    <div className="flex gap-3">
      <button
        onClick={onBack}
        className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-medium text-slate-100 hover:bg-white/8"
      >
        <ChevronLeft size={16} />
        {backLabel}
      </button>
      <button
        onClick={onNext}
        className="flex-1 rounded-2xl bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200"
      >
        <span className="inline-flex items-center gap-2">
          {nextLabel}
          <ChevronRight size={16} />
        </span>
      </button>
    </div>
  );
}
