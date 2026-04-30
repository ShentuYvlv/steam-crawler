import { useQuery } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import { BarChart3, CheckCircle2, MessageSquareReply, ThumbsUp } from "lucide-react";

import { fetchStatsOverview, fetchStatsTimeseries } from "@/lib/api";
import { rootRoute } from "@/routes/__root";

function DashboardHome() {
  const overviewQuery = useQuery({ queryKey: ["stats-overview"], queryFn: fetchStatsOverview });
  const timeseriesQuery = useQuery({
    queryKey: ["stats-timeseries", 14],
    queryFn: () => fetchStatsTimeseries(14)
  });
  const overview = overviewQuery.data;
  const timeseries = timeseriesQuery.data?.items ?? [];

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:py-8 xl:px-8">
      <section className="app-card p-6">
        <p className="text-sm font-medium text-blue-700">Steam Review Admin</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">运营统计总览</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-500">
          汇总评论处理进度、回复发送质量和近 14 天新增趋势。
        </p>
      </section>

      <section className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={BarChart3} label="评论总数" value={overview?.total_reviews ?? 0} />
        <StatCard
          icon={ThumbsUp}
          label="当前好评率"
          value={`${Math.round((overview?.positive_rate ?? 0) * 100)}%`}
        />
        <StatCard icon={MessageSquareReply} label="已回复" value={overview?.replied_reviews ?? 0} />
        <StatCard
          icon={CheckCircle2}
          label="回复成功率"
          value={`${Math.round((overview?.reply_success_rate ?? 0) * 100)}%`}
        />
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="app-card p-5">
          <h2 className="text-base font-semibold text-slate-950">处理状态</h2>
          <div className="mt-4 grid gap-3">
            <MiniMetric label="待处理" value={overview?.pending_reviews ?? 0} />
            <MiniMetric label="已忽略" value={overview?.ignored_reviews ?? 0} />
            <MiniMetric label="好评" value={overview?.positive_reviews ?? 0} />
            <MiniMetric label="差评" value={overview?.negative_reviews ?? 0} />
          </div>
        </div>

        <div className="app-card p-5 lg:col-span-2">
          <h2 className="text-base font-semibold text-slate-950">近 14 天趋势</h2>
          <div className="mt-5 flex h-64 items-end gap-2 overflow-hidden rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
            {timeseries.map((item) => {
              const maxValue = Math.max(
                1,
                ...timeseries.map((row) => Math.max(row.new_reviews, row.sent_replies))
              );
              return (
                <div key={item.date} className="flex flex-1 flex-col items-center gap-2">
                  <div className="flex h-44 items-end gap-1">
                    <span
                      className="w-2 rounded-t-full bg-blue-600"
                      style={{ height: `${Math.max(4, (item.new_reviews / maxValue) * 176)}px` }}
                      title={`新增评论 ${item.new_reviews}`}
                    />
                    <span
                      className="w-2 rounded-t-full bg-emerald-500/90"
                      style={{ height: `${Math.max(4, (item.sent_replies / maxValue) * 176)}px` }}
                      title={`发送回复 ${item.sent_replies}`}
                    />
                  </div>
                  <span className="text-[10px] text-slate-400">{item.date.slice(5)}</span>
                </div>
              );
            })}
          </div>
          <div className="mt-3 flex gap-4 text-xs text-slate-500">
            <span className="inline-flex items-center gap-2"><i className="h-2 w-2 rounded-full bg-blue-600" />新增评论</span>
            <span className="inline-flex items-center gap-2"><i className="h-2 w-2 rounded-full bg-emerald-500/90" />发送回复</span>
          </div>
        </div>
      </section>
    </main>
  );
}

function StatCard({
  icon: Icon,
  label,
  value
}: {
  icon: typeof BarChart3;
  label: string;
  value: string | number;
}) {
  return (
    <article className="app-card p-5 transition hover:border-blue-200 hover:bg-blue-50/20 hover:shadow-md hover:shadow-slate-200/70">
      <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-blue-50 text-blue-700 ring-1 ring-blue-100">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </div>
      <p className="mt-4 text-sm text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-slate-950">{value}</p>
    </article>
  );
}

function MiniMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3">
      <span className="text-sm text-slate-500">{label}</span>
      <span className="font-semibold text-slate-950">{value.toLocaleString()}</span>
    </div>
  );
}

export const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: DashboardHome
});
