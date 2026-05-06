import { useQuery } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import { ListOrdered } from "lucide-react";
import { useEffect, useState } from "react";

import { fetchTaskDetail, fetchTasks, type SyncJob } from "@/lib/api";
import { rootRoute } from "@/routes/__root";

function TaskQueuePage() {
  const tasksQuery = useQuery({
    queryKey: ["task-queue"],
    queryFn: fetchTasks,
    refetchInterval: 5000,
  });
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);

  useEffect(() => {
    if (!selectedTaskId && (tasksQuery.data?.length ?? 0) > 0) {
      setSelectedTaskId(tasksQuery.data?.[0]?.id ?? null);
    }
  }, [selectedTaskId, tasksQuery.data]);

  const detailQuery = useQuery({
    queryKey: ["task-queue-detail", selectedTaskId],
    queryFn: () => fetchTaskDetail(selectedTaskId as number),
    enabled: selectedTaskId !== null,
    refetchInterval: 5000,
  });

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:py-8 xl:px-8">
      <section className="app-card p-6">
        <div className="flex items-center gap-3">
          <div className="icon-tile">
            <ListOrdered className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-slate-950">任务队列</h1>
            <p className="mt-1 text-sm text-slate-500">
              查看所有异步任务的排队状态、执行结果和任务日志。
            </p>
          </div>
        </div>
      </section>

      <section className="mt-6 grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <div className="app-card p-4">
          <h2 className="text-base font-semibold text-slate-950">任务列表</h2>
          <div className="mt-4 grid gap-3">
            {(tasksQuery.data ?? []).map((task) => (
              <button
                key={task.id}
                type="button"
                onClick={() => setSelectedTaskId(task.id)}
                className={`rounded-2xl border p-4 text-left transition ${
                  selectedTaskId === task.id
                    ? "border-blue-200 bg-blue-50/80 shadow-sm"
                    : "border-slate-200 bg-slate-50/70 hover:border-blue-200 hover:bg-blue-50/40"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-slate-950">
                    #{task.id} · {formatTaskType(task.job_type)}
                  </p>
                  <span className={statusBadgeClass(task.status)}>{formatTaskStatus(task.status)}</span>
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  来源 {task.source_type} · App {task.app_id ?? "-"}
                </p>
                <p className="mt-3 text-sm text-slate-600">
                  新增 {task.inserted_count} / 更新 {task.updated_count} / 跳过 {task.skipped_count}
                </p>
              </button>
            ))}
            {!tasksQuery.isLoading && (tasksQuery.data?.length ?? 0) === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-6 text-sm text-slate-500">
                暂无异步任务。
              </div>
            ) : null}
          </div>
        </div>

        <div className="app-card p-5">
          {detailQuery.data ? (
            <div>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                    Task Detail
                  </p>
                  <h2 className="mt-2 text-xl font-semibold text-slate-950">
                    #{detailQuery.data.id} · {formatTaskType(detailQuery.data.job_type)}
                  </h2>
                </div>
                <span className={statusBadgeClass(detailQuery.data.status)}>
                  {formatTaskStatus(detailQuery.data.status)}
                </span>
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-3">
                <Metric label="App ID" value={String(detailQuery.data.app_id ?? "-")} />
                <Metric label="来源" value={detailQuery.data.source_type} />
                <Metric label="请求规模" value={String(detailQuery.data.requested_limit ?? "-")} />
              </div>

              {detailQuery.data.error_message ? (
                <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50/70 p-4 text-sm text-rose-700">
                  {detailQuery.data.error_message}
                </div>
              ) : null}

              <div className="mt-6">
                <h3 className="text-base font-semibold text-slate-950">任务日志</h3>
                <div className="mt-3 grid gap-3">
                  {detailQuery.data.logs.map((log) => (
                    <article
                      key={log.id}
                      className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className={log.level === "error" ? "badge-red" : "badge-blue"}>
                          {log.level}
                        </span>
                        <time className="text-xs text-slate-400">{formatDateTime(log.created_at)}</time>
                      </div>
                      <p className="mt-3 text-sm font-medium text-slate-800">{log.message}</p>
                      {log.details ? (
                        <pre className="mt-3 overflow-x-auto rounded-2xl border border-slate-200 bg-white p-3 text-xs text-slate-600">
                          {JSON.stringify(log.details, null, 2)}
                        </pre>
                      ) : null}
                    </article>
                  ))}
                  {detailQuery.data.logs.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-6 text-sm text-slate-500">
                      这个任务暂时还没有日志。
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-10 text-center text-sm text-slate-500">
              选择一条任务后，这里会显示执行日志。
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-2 text-lg font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function formatTaskType(value: string) {
  const mapping: Record<string, string> = {
    steam_review_sync: "Steam 评论同步",
    bulk_reply_generation: "批量生成草稿",
    bulk_developer_reply_send: "批量发送回复",
  };
  return mapping[value] ?? value;
}

function formatTaskStatus(value: string) {
  const mapping: Record<string, string> = {
    pending: "排队中",
    running: "执行中",
    success: "成功",
    partial_success: "部分成功",
    failed: "失败",
  };
  return mapping[value] ?? value;
}

function statusBadgeClass(status: string) {
  if (status === "failed") {
    return "badge-red";
  }
  if (status === "success") {
    return "badge-green";
  }
  if (status === "partial_success") {
    return "badge-orange";
  }
  return "badge-blue";
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

export const taskQueueRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/task-queue",
  component: TaskQueuePage,
});
