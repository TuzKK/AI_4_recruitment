import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchDashboardStats,
  fetchTasks,
  fetchFunnel,
  pauseTask,
  resumeTask,
  stopTask,
  type DashboardStats,
  type TaskSummary,
  type FunnelStage,
} from "../api/client";
import { useTaskWebSocket } from "../hooks/useWebSocket";
import { statusLabel, statusColor } from "../lib/utils";
import {
  Users,
  FileCheck,
  UserCheck,
  Phone,
  Play,
  Pause,
  Square,
  Activity,
  ArrowUpRight,
  Sparkles,
} from "lucide-react";

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [activeFunnel, setActiveFunnel] = useState<FunnelStage[]>([]);
  const [activeTaskId, setActiveTaskId] = useState<number | null>(null);
  const { events } = useTaskWebSocket(activeTaskId);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10_000);
    return () => clearInterval(interval);
  }, []);

  async function loadData() {
    try {
      const [s, t] = await Promise.all([fetchDashboardStats(), fetchTasks()]);
      setStats(s);
      setTasks(t);

      const running = t.find((item) => item.status === "running");
      if (running) {
        setActiveTaskId(running.id);
        const funnel = await fetchFunnel(running.id);
        setActiveFunnel(funnel.funnel);
      } else {
        setActiveTaskId(null);
        setActiveFunnel([]);
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function handlePause(id: number) {
    await pauseTask(id);
    loadData();
  }

  async function handleResume(id: number) {
    await resumeTask(id);
    loadData();
  }

  async function handleStop(id: number) {
    await stopTask(id);
    loadData();
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-5 py-6 lg:px-8">
      <section className="section-shell overflow-hidden p-6 lg:p-8">
        <div className="grid gap-8 lg:grid-cols-[1.3fr_0.9fr]">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs uppercase tracking-[0.2em] text-cyan-100">
              <Sparkles size={14} />
              招聘作战总览
            </div>
            <h1 className="mt-5 max-w-3xl text-3xl font-semibold leading-tight text-white lg:text-5xl">
              让 Boss 直聘客户端招聘流程从岗位拆解到联系方式获取，全部在一个指挥台里完成。
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-400 lg:text-base">
              看板会持续汇总任务状态、漏斗变化和实时执行日志，方便你判断哪条岗位链路值得放量，哪一轮话术需要调整。
            </p>
          </div>
          <div className="rounded-[28px] border border-white/10 bg-white/5 p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Quick Action</p>
                <h2 className="mt-2 text-xl font-semibold text-white">启动新的自动化招聘任务</h2>
              </div>
              <ArrowUpRight className="text-cyan-200" size={20} />
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-400">
              输入职位名称，AI 生成 JD、关键词和阈值建议，随后直接启动 Boss 客户端执行链路。
            </p>
            <Link
              to="/tasks/new"
              className="mt-6 inline-flex rounded-2xl bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200"
            >
              创建招聘任务
            </Link>
          </div>
        </div>
      </section>

      {stats && (
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard
            icon={<Users className="text-cyan-200" />}
            label="候选人总数"
            value={stats.total_candidates}
            accent="from-cyan-400/20 to-cyan-400/5"
          />
          <StatCard
            icon={<FileCheck className="text-indigo-200" />}
            label="已收简历"
            value={stats.resume_received}
            accent="from-indigo-400/20 to-indigo-400/5"
          />
          <StatCard
            icon={<UserCheck className="text-emerald-200" />}
            label="评分达标"
            value={stats.qualified}
            accent="from-emerald-400/20 to-emerald-400/5"
          />
          <StatCard
            icon={<Phone className="text-amber-200" />}
            label="已获联系方式"
            value={stats.contact_obtained}
            accent="from-amber-300/20 to-amber-300/5"
          />
        </section>
      )}

      <section className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
        <div className="section-shell p-6">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Funnel Monitor</p>
              <h2 className="mt-2 text-xl font-semibold text-white">招聘漏斗</h2>
            </div>
          </div>

          {activeFunnel.length > 0 ? (
            <div className="space-y-4">
              {activeFunnel.map((stage, i) => {
                const maxCount = activeFunnel[0]?.count || 1;
                const width = Math.max((stage.count / maxCount) * 100, 8);
                return (
                  <div key={stage.stage} className="rounded-[22px] border border-white/8 bg-white/4 p-4">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <span className="text-sm font-medium text-slate-200">{stage.stage}</span>
                      <span className="text-xs uppercase tracking-[0.2em] text-slate-500">
                        {stage.count} 人
                      </span>
                    </div>
                    <div className="h-3 rounded-full bg-slate-900/80">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${width}%`,
                          background: `linear-gradient(90deg, hsl(${195 - i * 12}, 88%, ${62 - i * 2}%), hsl(${210 - i * 10}, 82%, ${48 - i * 2}%))`,
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="rounded-[22px] border border-dashed border-white/10 px-4 py-10 text-center text-sm text-slate-500">
              暂无运行中的任务，创建新任务后会在这里显示完整漏斗。
            </p>
          )}
        </div>

        <div className="section-shell p-6">
          <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-white">
            <Activity size={18} className="text-emerald-300" />
            实时日志
          </h2>
          <div className="h-[360px] space-y-3 overflow-y-auto rounded-[22px] border border-white/8 bg-slate-950/40 p-4 text-sm">
            {events.length === 0 ? (
              <p className="py-16 text-center text-slate-500">等待任务启动...</p>
            ) : (
              events
                .slice()
                .reverse()
                .map((evt, i) => (
                  <div key={i} className="grid grid-cols-[72px_1fr] gap-3 rounded-2xl border border-white/6 bg-white/4 px-3 py-3">
                    <span className="font-mono text-xs text-slate-500">
                      {new Date(evt.timestamp).toLocaleTimeString("zh-CN")}
                    </span>
                    <span className="leading-6 text-slate-200">{evt.message}</span>
                  </div>
                ))
            )}
          </div>
        </div>
      </section>

      <section className="section-shell overflow-hidden">
        <div className="border-b border-white/10 px-6 py-5">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Task Matrix</p>
          <h2 className="mt-2 text-xl font-semibold text-white">任务列表</h2>
        </div>
        {tasks.length === 0 ? (
          <p className="px-6 py-12 text-center text-sm text-slate-500">暂无任务</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="text-left text-slate-500">
                <tr>
                  <th className="px-6 py-4 font-medium">ID</th>
                  <th className="px-6 py-4 font-medium">职位</th>
                  <th className="px-6 py-4 font-medium">状态</th>
                  <th className="px-6 py-4 font-medium">进度</th>
                  <th className="px-6 py-4 font-medium">创建时间</th>
                  <th className="px-6 py-4 font-medium">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/6">
                {tasks.map((task) => (
                  <tr key={task.id} className="transition hover:bg-white/4">
                    <td className="px-6 py-4 font-mono text-slate-400">#{task.id}</td>
                    <td className="px-6 py-4 font-medium text-white">{task.position_title}</td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${statusColor(
                          task.status
                        )}`}
                      >
                        {statusLabel(task.status)}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-300">
                      {task.progress.greeted ?? 0} 招呼 / {task.progress.resume_received ?? 0} 简历
                    </td>
                    <td className="px-6 py-4 text-slate-400">
                      {task.created_at ? new Date(task.created_at).toLocaleString("zh-CN") : ""}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex gap-2">
                        {task.status === "running" && (
                          <>
                            <button
                              onClick={() => handlePause(task.id)}
                              className="rounded-xl border border-amber-300/20 bg-amber-300/10 p-2 text-amber-200 hover:bg-amber-300/15"
                              title="暂停"
                            >
                              <Pause size={16} />
                            </button>
                            <button
                              onClick={() => handleStop(task.id)}
                              className="rounded-xl border border-red-300/20 bg-red-300/10 p-2 text-red-200 hover:bg-red-300/15"
                              title="停止"
                            >
                              <Square size={16} />
                            </button>
                          </>
                        )}
                        {task.status === "paused" && (
                          <button
                            onClick={() => handleResume(task.id)}
                            className="rounded-xl border border-emerald-300/20 bg-emerald-300/10 p-2 text-emerald-200 hover:bg-emerald-300/15"
                            title="继续"
                          >
                            <Play size={16} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  accent: string;
}) {
  return (
    <div className={`section-shell bg-gradient-to-br ${accent} p-5`}>
      <div className="flex items-center gap-4">
        <div className="rounded-2xl bg-slate-950/40 p-3">{icon}</div>
        <div>
          <p className="text-3xl font-semibold text-white">{value}</p>
          <p className="text-sm text-slate-400">{label}</p>
        </div>
      </div>
    </div>
  );
}
