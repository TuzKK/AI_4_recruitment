import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchPositions, type PositionSummary } from "../api/client";
import { Briefcase, Users } from "lucide-react";

export default function PositionList() {
  const [positions, setPositions] = useState<PositionSummary[]>([]);

  useEffect(() => {
    fetchPositions().then(setPositions);
  }, []);

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-5 py-6 lg:px-8">
      <div className="section-shell p-6 lg:p-7">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Position Matrix</p>
            <h1 className="mt-2 text-3xl font-semibold text-white">职位矩阵</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
              统一查看已沉淀的岗位画像、来源候选人规模和创建时间，快速判断哪些岗位值得继续投放自动化流程。
            </p>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="text-sm text-slate-400">共 {positions.length} 个岗位画像</div>
        <Link
          to="/tasks/new"
          className="rounded-2xl bg-cyan-300 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200"
        >
          + 新建职位任务
        </Link>
      </div>

      {positions.length === 0 ? (
        <div className="section-shell p-12 text-center">
          <Briefcase size={48} className="mx-auto mb-4 text-slate-500" />
          <p className="text-slate-400">暂无职位，点击上方按钮创建</p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {positions.map((position) => (
            <div
              key={position.id}
              className="section-shell p-5 transition hover:-translate-y-0.5 hover:border-cyan-300/20"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold text-white">{position.title}</h3>
                  {position.description && (
                    <p className="mt-2 text-sm leading-6 text-slate-400">{position.description}</p>
                  )}
                </div>
                <div className="flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-slate-300">
                  <Users size={14} className="text-cyan-200" />
                  {position.candidate_count}
                </div>
              </div>
              <div className="mt-5 border-t border-white/8 pt-4 text-xs text-slate-500">
                创建于{" "}
                {position.created_at
                  ? new Date(position.created_at).toLocaleDateString("zh-CN")
                  : "未知"}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
