import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchCandidates, type CandidateSummary } from "../api/client";
import { statusLabel, statusColor } from "../lib/utils";
import { Download, ChevronLeft, ChevronRight, Users, Filter } from "lucide-react";

export default function CandidateList() {
  const [candidates, setCandidates] = useState<CandidateSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const pageSize = 20;

  useEffect(() => {
    loadCandidates();
  }, [page, statusFilter]);

  async function loadCandidates() {
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    if (statusFilter) params.set("status", statusFilter);
    params.set("sort_by", "created_at");
    params.set("order", "desc");

    const data = await fetchCandidates(params.toString());
    setCandidates(data.items);
    setTotal(data.total);
  }

  const totalPages = Math.ceil(total / pageSize);
  const statuses = [
    "",
    "found",
    "greeted",
    "chatting",
    "resume_received",
    "scored",
    "qualified",
    "contact_obtained",
    "rejected",
  ];

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-5 py-6 lg:px-8">
      <div className="section-shell p-6 lg:p-7">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Candidate Pool</p>
            <h1 className="mt-2 text-3xl font-semibold text-white">候选人池</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">
              按状态过滤候选人，集中查看简历得分、联系方式获取情况和创建时间，适合做批量复盘与导出。
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 md:min-w-[280px]">
            <SummaryBlock label="当前页" value={`${candidates.length}`} />
            <SummaryBlock label="候选人总数" value={`${total}`} />
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-3 rounded-[22px] border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
          <Filter size={16} className="text-cyan-200" />
          候选人状态过滤
        </div>
        <a
          href="/api/candidates/export"
          className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-100 transition hover:bg-white/8"
        >
          <Download size={16} /> 导出 Excel
        </a>
      </div>

      <div className="section-shell flex flex-wrap gap-3 p-4">
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="rounded-2xl border border-white/10 bg-slate-950/40 px-4 py-2.5 text-sm text-slate-100 outline-none"
        >
          <option value="">全部状态</option>
          {statuses
            .filter(Boolean)
            .map((status) => (
              <option key={status} value={status}>
                {statusLabel(status)}
              </option>
            ))}
        </select>
      </div>

      <div className="section-shell overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[920px] text-sm">
            <thead className="text-left text-slate-500">
              <tr>
                <th className="px-6 py-4 font-medium">姓名</th>
                <th className="px-6 py-4 font-medium">状态</th>
                <th className="px-6 py-4 font-medium">初筛分数</th>
                <th className="px-6 py-4 font-medium">简历评分</th>
                <th className="px-6 py-4 font-medium">联系方式</th>
                <th className="px-6 py-4 font-medium">创建时间</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/6">
              {candidates.map((candidate) => (
                <tr key={candidate.id} className="transition hover:bg-white/4">
                  <td className="px-6 py-4">
                    <Link
                      to={`/candidates/${candidate.id}`}
                      className="font-medium text-cyan-200 hover:text-cyan-100"
                    >
                      {candidate.name || `#${candidate.id}`}
                    </Link>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${statusColor(
                        candidate.status
                      )}`}
                    >
                      {statusLabel(candidate.status)}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono text-slate-200">
                    {candidate.pre_match_score > 0 ? candidate.pre_match_score : "-"}
                  </td>
                  <td className="px-6 py-4 font-mono">
                    {candidate.resume_score != null ? (
                      <span
                        className={
                          candidate.is_qualified
                            ? "font-semibold text-emerald-300"
                            : "text-slate-200"
                        }
                      >
                        {candidate.resume_score}
                      </span>
                    ) : (
                      "-"
                    )}
                  </td>
                  <td className="px-6 py-4">
                    {candidate.has_contact ? (
                      <span className="text-xs font-medium text-emerald-300">已获取</span>
                    ) : (
                      <span className="text-xs text-slate-500">-</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-xs text-slate-400">
                    {candidate.created_at
                      ? new Date(candidate.created_at).toLocaleString("zh-CN")
                      : ""}
                  </td>
                </tr>
              ))}
              {candidates.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                    暂无候选人数据
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-slate-400">
          <span>
            共 {total} 条，第 {page}/{totalPages} 页
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="rounded-xl border border-white/10 bg-white/5 p-2 hover:bg-white/8 disabled:opacity-50"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page === totalPages}
              className="rounded-xl border border-white/10 bg-white/5 p-2 hover:bg-white/8 disabled:opacity-50"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[20px] border border-white/10 bg-white/5 px-4 py-3">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-slate-500">
        <Users size={13} className="text-cyan-200" />
        {label}
      </div>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}
