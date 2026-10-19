import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { fetchCandidate, fetchCandidateMessages } from "../api/client";
import { statusLabel, statusColor } from "../lib/utils";
import {
  ArrowLeft,
  User,
  FileText,
  MessageSquare,
  Phone,
  Mail,
  MessageCircle,
} from "lucide-react";

export default function CandidateDetail() {
  const { id } = useParams();
  const [candidate, setCandidate] = useState<Record<string, unknown> | null>(null);
  const [messages, setMessages] = useState<Record<string, unknown>[]>([]);

  useEffect(() => {
    if (id) {
      fetchCandidate(Number(id)).then(setCandidate);
      fetchCandidateMessages(Number(id)).then(setMessages);
    }
  }, [id]);

  if (!candidate) {
    return <div className="px-6 py-16 text-center text-slate-500">加载中...</div>;
  }

  const resume = candidate.resume as Record<string, unknown> | undefined;
  const contact = candidate.contact as Record<string, unknown> | undefined;
  const score = (resume?.score as Record<string, unknown>) || {};

  const scoreItems = [
    { label: "技能匹配", value: Number(score.skill_match || 0) },
    { label: "经验相关", value: Number(score.experience_relevance || 0) },
    { label: "学历契合", value: Number(score.education_fit || 0) },
    { label: "项目质量", value: Number(score.project_quality || 0) },
    { label: "综合推荐", value: Number(score.overall_recommendation || 0) },
  ];

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-5 py-6 lg:px-8">
      <Link
        to="/candidates"
        className="inline-flex items-center gap-2 text-sm text-slate-400 transition hover:text-slate-200"
      >
        <ArrowLeft size={16} />
        返回候选人池
      </Link>

      <div className="section-shell p-6">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-full border border-cyan-300/20 bg-cyan-300/10">
              <User className="text-cyan-200" size={26} />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-white">
                {(candidate.name as string) || `候选人 #${id}`}
              </h1>
              <span
                className={`mt-2 inline-block rounded-full px-2.5 py-1 text-xs font-medium ${statusColor(
                  String(candidate.status || "")
                )}`}
              >
                {statusLabel(String(candidate.status || ""))}
              </span>
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2 lg:min-w-[320px]">
            <QuickStat
              label="初筛分数"
              value={String(candidate.pre_match_score ?? "-")}
            />
            <QuickStat
              label="简历评分"
              value={resume ? String(resume.weighted_total || "-") : "-"}
            />
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-6">
          {resume && (
            <div className="section-shell p-6">
              <h2 className="flex items-center gap-2 text-xl font-semibold text-white">
                <FileText size={18} />
                AI 评分详情
              </h2>
              <div className="mt-5 grid gap-4 md:grid-cols-5">
                {scoreItems.map((item) => (
                  <div
                    key={item.label}
                    className="rounded-[24px] border border-white/8 bg-white/4 p-4 text-center"
                  >
                    <div className="relative mx-auto mb-3 h-16 w-16">
                      <svg className="h-16 w-16 -rotate-90" viewBox="0 0 36 36">
                        <circle
                          cx="18"
                          cy="18"
                          r="14"
                          fill="none"
                          stroke="rgba(148,163,184,0.18)"
                          strokeWidth="3"
                        />
                        <circle
                          cx="18"
                          cy="18"
                          r="14"
                          fill="none"
                          stroke={
                            item.value >= 70
                              ? "#67f0ae"
                              : item.value >= 50
                              ? "#ffb457"
                              : "#ff7e8a"
                          }
                          strokeWidth="3"
                          strokeDasharray={`${(item.value / 100) * 88} 88`}
                          strokeLinecap="round"
                        />
                      </svg>
                      <span className="absolute inset-0 flex items-center justify-center text-sm font-semibold text-white">
                        {item.value}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400">{item.label}</p>
                  </div>
                ))}
              </div>

              <InsightBlock title="亮点" color="text-emerald-300" items={score.strengths as string[] | undefined} />
              <InsightBlock title="不足" color="text-red-300" items={score.weaknesses as string[] | undefined} />

              {Boolean(score.reasoning) && (
                <div className="mt-5 rounded-[24px] border border-white/8 bg-white/4 p-4">
                  <h4 className="text-sm font-medium text-slate-200">评分理由</h4>
                  <p className="mt-2 text-sm leading-6 text-slate-400">{String(score.reasoning)}</p>
                </div>
              )}
            </div>
          )}

          {Boolean(resume?.file_path) && (
            <div className="section-shell p-6">
              <h2 className="text-xl font-semibold text-white">简历文件</h2>
              <a
                href={`/api/candidates/${id}/resume`}
                className="mt-4 inline-flex items-center gap-2 rounded-2xl bg-cyan-300 px-4 py-2.5 text-sm font-semibold text-slate-950 hover:bg-cyan-200"
              >
                <FileText size={16} />
                下载简历 ({String(resume?.file_type || "")})
              </a>
            </div>
          )}
        </div>

        <div className="space-y-6">
          {contact && (
            <div className="section-shell p-6">
              <h2 className="flex items-center gap-2 text-xl font-semibold text-white">
                <Phone size={18} />
                联系方式
              </h2>
              <div className="mt-4 space-y-3 text-sm">
                {(contact.wechat as string | undefined) && (
                  <ContactRow icon={<MessageCircle size={14} className="text-emerald-300" />} label="微信" value={String(contact.wechat)} />
                )}
                {(contact.phone as string | undefined) && (
                  <ContactRow icon={<Phone size={14} className="text-cyan-200" />} label="手机" value={String(contact.phone)} />
                )}
                {(contact.email as string | undefined) && (
                  <ContactRow icon={<Mail size={14} className="text-slate-300" />} label="邮箱" value={String(contact.email)} />
                )}
              </div>
            </div>
          )}

          <div className="section-shell p-6">
            <h2 className="flex items-center gap-2 text-xl font-semibold text-white">
              <MessageSquare size={18} />
              聊天记录
            </h2>
            {messages.length === 0 ? (
              <p className="py-10 text-center text-sm text-slate-500">暂无消息</p>
            ) : (
              <div className="mt-4 max-h-96 space-y-3 overflow-y-auto">
                {messages.map((msg) => {
                  const sent = msg.direction === "sent";
                  return (
                    <div
                      key={String(msg.id)}
                      className={`flex ${sent ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                          sent
                            ? "bg-cyan-300 text-slate-950"
                            : "border border-white/10 bg-white/5 text-slate-200"
                        }`}
                      >
                        <p>{String(msg.content || "")}</p>
                        <p
                          className={`mt-2 text-xs ${
                            sent ? "text-slate-700" : "text-slate-500"
                          }`}
                        >
                          {msg.created_at
                            ? new Date(String(msg.created_at)).toLocaleString("zh-CN")
                            : ""}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function QuickStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[22px] border border-white/10 bg-white/5 px-4 py-3">
      <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function ContactRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-[20px] border border-white/8 bg-white/4 px-4 py-3">
      {icon}
      <span className="text-slate-500">{label}:</span>
      <span className="font-medium text-slate-100">{value}</span>
    </div>
  );
}

function InsightBlock({
  title,
  color,
  items,
}: {
  title: string;
  color: string;
  items?: string[];
}) {
  if (!items || items.length === 0) return null;

  return (
    <div className="mt-5 rounded-[24px] border border-white/8 bg-white/4 p-4">
      <h4 className={`text-sm font-medium ${color}`}>{title}</h4>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-300">
        {items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
