import { Routes, Route, NavLink, useLocation } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import CreateTask from "./pages/CreateTask";
import CandidateList from "./pages/CandidateList";
import CandidateDetail from "./pages/CandidateDetail";
import PositionList from "./pages/PositionList";
import MarketResearch from "./pages/MarketResearch";
import Settings from "./pages/Settings";
import BrowserChat from "./pages/BrowserChat";
import {
  LayoutDashboard,
  PlusCircle,
  Users,
  Briefcase,
  Globe,
  Settings as SettingsIcon,
  Sparkles,
  Radar,
  ChevronRight,
} from "lucide-react";

const navItems = [
  { to: "/chat", icon: Users, label: "网页聊天", hint: "读取当前联系人并发送文字" },
  { to: "/", icon: LayoutDashboard, label: "作战总览", hint: "任务、漏斗、实时动态" },
  { to: "/tasks/new", icon: PlusCircle, label: "新建任务", hint: "AI 解析岗位并开跑" },
  { to: "/candidates", icon: Users, label: "候选人池", hint: "筛选、跟进、导出" },
  { to: "/positions", icon: Briefcase, label: "职位矩阵", hint: "岗位画像与规模" },
  { to: "/market", icon: Globe, label: "市场情报", hint: "竞对与人才趋势" },
  { to: "/settings", icon: SettingsIcon, label: "系统设置", hint: "模型与账号管理" },
];

export default function App() {
  const location = useLocation();
  const currentNav =
    navItems.find((item) =>
      item.to === "/"
        ? location.pathname === "/"
        : location.pathname.startsWith(item.to)
    ) ?? navItems[0];

  return (
    <div className="min-h-screen px-4 py-4 text-slate-100 md:px-5 lg:px-6">
      <div className="mx-auto grid min-h-[calc(100vh-2rem)] max-w-[1600px] grid-cols-1 gap-4 lg:grid-cols-[290px_minmax(0,1fr)]">
        <aside className="glass-panel-strong flex flex-col overflow-hidden rounded-[30px]">
          <div className="border-b border-white/10 px-6 py-6">
            <div className="mb-5 flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-cyan-300/30 bg-cyan-300/10 text-cyan-200">
                <Radar size={20} />
              </div>
              <div>
                <h1 className="text-base font-semibold tracking-[0.18em] text-cyan-100 uppercase">
                  Boss直聘客户端自动化招聘
                </h1>
                <p className="mt-1 text-xs text-slate-400">
                  Recruiter cockpit for search, outreach and resume scoring
                </p>
              </div>
            </div>

            <div className="rounded-[24px] border border-white/10 bg-white/5 p-4">
              <div className="flex items-center justify-between text-xs uppercase tracking-[0.2em] text-slate-400">
                <span>Command Status</span>
                <Sparkles size={14} className="text-cyan-200" />
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div>
                  <p className="text-[11px] text-slate-500">模式</p>
                  <p className="mt-1 text-sm font-semibold text-slate-100">AI 自动化</p>
                </div>
                <div>
                  <p className="text-[11px] text-slate-500">重点</p>
                  <p className="mt-1 text-sm font-semibold text-slate-100">Boss 直聘客户端</p>
                </div>
              </div>
            </div>
          </div>

          <nav className="flex-1 space-y-2 px-4 py-5">
            {navItems.map(({ to, icon: Icon, label, hint }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `group block rounded-[22px] border px-4 py-3 transition-all ${
                    isActive
                      ? "border-cyan-300/30 bg-cyan-300/12 shadow-[0_18px_40px_rgba(6,182,212,0.12)]"
                      : "border-transparent bg-transparent hover:border-white/10 hover:bg-white/5"
                  }`
                }
              >
                {({ isActive }) => (
                  <div className="flex items-start gap-3">
                    <div
                      className={`mt-0.5 flex h-10 w-10 items-center justify-center rounded-2xl ${
                        isActive
                          ? "bg-cyan-300/16 text-cyan-100"
                          : "bg-white/5 text-slate-300 group-hover:text-slate-100"
                      }`}
                    >
                      <Icon size={18} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-semibold text-slate-100">
                          {label}
                        </span>
                        <ChevronRight
                          size={15}
                          className={isActive ? "text-cyan-200" : "text-slate-500"}
                        />
                      </div>
                      <p className="mt-1 text-xs leading-5 text-slate-400">{hint}</p>
                    </div>
                  </div>
                )}
              </NavLink>
            ))}
          </nav>

          <div className="border-t border-white/10 px-6 py-4 text-xs text-slate-500">
            v1.0.0 · recruitment control surface
          </div>
        </aside>

        <main className="glass-panel overflow-hidden rounded-[30px]">
          <div className="border-b border-white/10 px-6 py-5 lg:px-8">
            <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
              <div>
                <p className="text-[11px] uppercase tracking-[0.24em] text-cyan-200/80">
                  Active Module
                </p>
                <h2 className="mt-2 text-3xl font-semibold tracking-tight text-white">
                  {currentNav.label}
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
                  {currentNav.hint}。围绕 Boss 直聘客户端的岗位分析、候选人触达、简历评分和联系方式获取流程统一调度。
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3 md:min-w-[260px]">
                <MetricBadge label="渠道" value="Boss 直聘客户端" />
                <MetricBadge label="驱动" value="RPA + LLM" />
              </div>
            </div>
          </div>

          <div className="h-[calc(100vh-11rem)] overflow-auto">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/tasks/new" element={<CreateTask />} />
              <Route path="/candidates" element={<CandidateList />} />
              <Route path="/candidates/:id" element={<CandidateDetail />} />
              <Route path="/positions" element={<PositionList />} />
              <Route path="/market" element={<MarketResearch />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/chat" element={<BrowserChat />} />
            </Routes>
          </div>
        </main>
      </div>
    </div>
  );
}

function MetricBadge({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[20px] border border-white/10 bg-white/5 px-4 py-3">
      <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-100">{value}</p>
    </div>
  );
}
