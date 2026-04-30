import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import { Clock3, RefreshCcw } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  enqueueReviewSync,
  fetchTaskSchedule,
  fetchTasks,
  updateTaskSchedule,
  type SyncJob
} from "@/lib/api";
import { rootRoute } from "@/routes/__root";

function TasksPage() {
  const queryClient = useQueryClient();
  const [appId, setAppId] = useState("3350200");
  const [enabled, setEnabled] = useState(false);
  const [interval, setInterval] = useState("daily");
  const jobsQuery = useQuery({ queryKey: ["tasks"], queryFn: fetchTasks });
  const scheduleQuery = useQuery({ queryKey: ["tasks-schedule"], queryFn: fetchTaskSchedule });

  useEffect(() => {
    if (scheduleQuery.data) {
      setEnabled(scheduleQuery.data.is_enabled);
      setInterval(scheduleQuery.data.interval);
      setAppId(String(scheduleQuery.data.app_id ?? 3350200));
    }
  }, [scheduleQuery.data]);

  const syncMutation = useMutation({
    mutationFn: () =>
      enqueueReviewSync({
        app_id: Number(appId),
        language: "schinese",
        filter: "recent",
        review_type: "all",
        purchase_type: "all",
        use_review_quality: true,
        per_page: 100
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
    }
  });
  const scheduleMutation = useMutation({
    mutationFn: () =>
      updateTaskSchedule({
        is_enabled: enabled,
        app_id: Number(appId),
        interval,
        minute: 0,
        options: {
          language: "schinese",
          filter: "recent",
          review_type: "all",
          purchase_type: "all",
          use_review_quality: true,
          per_page: 100
        }
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tasks-schedule"] });
    }
  });

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:py-8 xl:px-8">
      <section className="rounded-[2rem] border border-white/80 bg-white/90 p-6 shadow-xl shadow-slate-200/70">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-600 text-white">
            <Clock3 className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-slate-950">任务与同步</h1>
            <p className="mt-1 text-sm text-slate-500">
              按评论表最新时间增量追新，直到 Steam 没有更新评论为止。
            </p>
          </div>
        </div>

        <div className="mt-6 grid gap-4 rounded-3xl border border-slate-100 bg-slate-50/80 p-4 md:grid-cols-[1fr_1fr_1.1fr]">
          <Field label="App ID" value={appId} onChange={setAppId} />
          <label className="flex flex-col gap-2 text-sm">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">频率</span>
            <select
              className="h-11 rounded-2xl border border-slate-200 bg-white px-3 text-sm outline-none"
              value={interval}
              onChange={(event) => setInterval(event.target.value)}
            >
              <option value="hourly">每小时</option>
              <option value="daily">每天</option>
            </select>
          </label>
          <label className="flex items-center gap-2 rounded-2xl bg-white px-3 py-3 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(event) => setEnabled(event.target.checked)}
            />
            启用定时同步
          </label>
          <div className="rounded-2xl border border-sky-100 bg-sky-50/70 px-4 py-3 text-xs leading-5 text-sky-800 md:col-span-3">
            同步策略：固定使用 Steam 最新排序，从第一页开始抓取；遇到早于本地最新评论时间的数据即停止。
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button type="button" disabled={syncMutation.isPending} onClick={() => syncMutation.mutate()}>
            <RefreshCcw className="h-4 w-4" aria-hidden="true" />
            手动同步
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={scheduleMutation.isPending}
            onClick={() => scheduleMutation.mutate()}
          >
            保存定时配置
          </Button>
        </div>
      </section>

      <section className="mt-6 rounded-[2rem] border border-white/80 bg-white p-5 shadow-xl shadow-slate-200/70">
        <h2 className="text-base font-semibold text-slate-950">最近任务</h2>
        <div className="mt-4 grid gap-3">
          {(jobsQuery.data ?? []).map((job) => (
            <TaskCard key={job.id} job={job} />
          ))}
          {!jobsQuery.isLoading && (jobsQuery.data ?? []).length === 0 ? (
            <p className="rounded-3xl border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-500">
              暂无任务记录。
            </p>
          ) : null}
        </div>
      </section>
    </main>
  );
}

function Field({
  label,
  value,
  onChange
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-2 text-sm">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <input
        className="h-11 rounded-2xl border border-slate-200 bg-white px-3 text-sm outline-none"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function TaskCard({ job }: { job: SyncJob }) {
  return (
    <article className="rounded-3xl border border-slate-100 bg-slate-50/80 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-950">#{job.id} · {job.job_type}</p>
          <p className="mt-1 text-xs text-slate-500">
            App {job.app_id ?? "-"} · 按最新评论时间追新
          </p>
        </div>
        <span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700">
          {job.status}
        </span>
      </div>
      <p className="mt-3 text-sm text-slate-600">
        新增 {job.inserted_count} / 更新 {job.updated_count} / 跳过 {job.skipped_count}
      </p>
    </article>
  );
}

export const tasksRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/tasks",
  component: TasksPage
});
