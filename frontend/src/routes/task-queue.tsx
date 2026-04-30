import { useQuery } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import { CheckCircle2, Clock3, FileText, ListChecks, RefreshCcw, XCircle } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { fetchTaskDetail, fetchTasks, type SyncJob, type TaskLog } from "@/lib/api";
import { rootRoute } from "@/routes/__root";

const statusText: Record<string, string> = {
  pending: "排队中",
  running: "执行中",
  success: "成功",
  failed: "失败",
  partial_success: "部分成功"
};

const jobTypeText: Record<string, string> = {
  steam_review_sync: "Steam 评论同步",
  stock_import: "存量评论导入",
  bulk_reply_generation: "批量生成回复草稿",
  bulk_developer_reply_send: "批量发送开发者回复"
};

function TaskQueuePage() {
  const [activeTaskId, setActiveTaskId] = useState<number | null>(null);
  const tasksQuery = useQuery({
    queryKey: ["task-queue"],
    queryFn: () => fetchTasks(100),
    refetchInterval: 5000
  });
  const tasks = tasksQuery.data ?? [];
  const activeTask = useMemo(
    () => tasks.find((task) => task.id === activeTaskId) ?? tasks[0],
    [activeTaskId, tasks]
  );
  const detailQuery = useQuery({
    queryKey: ["task-detail", activeTask?.id],
    queryFn: () => fetchTaskDetail(activeTask?.id as number),
    enabled: Boolean(activeTask?.id),
    refetchInterval: activeTask?.status === "pending" || activeTask?.status === "running" ? 3000 : false
  });

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:py-8 xl:px-8">
      <section className="app-card p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <div className="icon-tile">
              <ListChecks className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-slate-950">任务队列</h1>
              <p className="mt-1 text-sm text-slate-500">
                统一查看异步任务执行状态、结果统计和任务日志。
              </p>
            </div>
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={tasksQuery.isFetching}
            onClick={() => {
              void tasksQuery.refetch();
              void detailQuery.refetch();
            }}
          >
            <RefreshCcw className="h-4 w-4" aria-hidden="true" />
            刷新
          </Button>
        </div>
      </section>

      <section className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="app-card overflow-hidden">
          <div className="border-b border-slate-100 px-5 py-4">
            <h2 className="text-base font-semibold text-slate-950">队列列表</h2>
            <p className="mt-1 text-xs text-slate-500">包含同步、批量生成草稿、批量发送回复等后台任务。</p>
          </div>
          <div className="divide-y divide-slate-100">
            {tasks.map((task) => (
              <TaskQueueItem
                key={task.id}
                task={task}
                active={task.id === activeTask?.id}
                onSelect={() => setActiveTaskId(task.id)}
              />
            ))}
            {!tasksQuery.isLoading && tasks.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">暂无异步任务。</div>
            ) : null}
            {tasksQuery.isLoading ? (
              <div className="p-8 text-center text-sm text-slate-500">任务加载中...</div>
            ) : null}
          </div>
        </div>

        <aside className="app-card p-5">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-blue-600" aria-hidden="true" />
            <h2 className="text-base font-semibold text-slate-950">任务日志</h2>
          </div>
          {detailQuery.data ? (
            <TaskDetailPanel task={detailQuery.data} />
          ) : (
            <div className="mt-5 rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-6 text-sm text-slate-500">
              选择左侧任务查看执行日志。
            </div>
          )}
        </aside>
      </section>
    </main>
  );
}

function TaskQueueItem({
  task,
  active,
  onSelect
}: {
  task: SyncJob;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={
        active
          ? "block w-full bg-blue-50/70 px-5 py-4 text-left"
          : "block w-full bg-white px-5 py-4 text-left transition hover:bg-blue-50/30"
      }
      onClick={onSelect}
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold text-slate-950">#{task.id} · {jobTypeText[task.job_type] ?? task.job_type}</p>
            <StatusBadge status={task.status} />
          </div>
          <p className="mt-2 text-xs text-slate-500">
            App {task.app_id ?? "-"} · 来源 {task.source_type} · 创建 {formatDateTime(task.created_at)}
          </p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center text-xs">
          <QueueMetric label="成功" value={task.inserted_count} />
          <QueueMetric label="更新" value={task.updated_count} />
          <QueueMetric label="失败/跳过" value={task.skipped_count} />
        </div>
      </div>
    </button>
  );
}

function TaskDetailPanel({ task }: { task: SyncJob & { error_message: string | null; logs: TaskLog[] } }) {
  return (
    <div className="mt-5">
      <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-semibold text-slate-950">#{task.id} · {jobTypeText[task.job_type] ?? task.job_type}</p>
            <p className="mt-1 text-xs text-slate-500">开始 {formatDateTime(task.started_at)} · 结束 {formatDateTime(task.finished_at)}</p>
          </div>
          <StatusBadge status={task.status} />
        </div>
        {task.error_message ? (
          <p className="mt-3 rounded-xl border border-rose-100 bg-rose-50 p-3 text-xs leading-5 text-rose-700">
            {task.error_message}
          </p>
        ) : null}
      </div>
      <div className="mt-4 space-y-3">
        {task.logs.map((log) => (
          <TaskLogItem key={log.id} log={log} />
        ))}
        {task.logs.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-6 text-sm text-slate-500">
            暂无日志。
          </div>
        ) : null}
      </div>
    </div>
  );
}

function TaskLogItem({ log }: { log: TaskLog }) {
  const isError = log.level === "error";
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-start gap-3">
        <div
          className={
            isError
              ? "mt-0.5 flex h-8 w-8 items-center justify-center rounded-xl bg-rose-50 text-rose-700 ring-1 ring-rose-100"
              : "mt-0.5 flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100"
          }
        >
          {isError ? <XCircle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-slate-950">{log.message}</p>
          <p className="mt-1 text-xs text-slate-500">{formatDateTime(log.created_at)}</p>
          {log.details ? (
            <pre className="mt-3 max-h-40 overflow-auto rounded-xl border border-slate-200 bg-slate-50/70 p-3 text-xs leading-5 text-slate-600">
              {JSON.stringify(log.details, null, 2)}
            </pre>
          ) : null}
        </div>
      </div>
    </article>
  );
}

function QueueMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2">
      <p className="text-[11px] text-slate-400">{label}</p>
      <p className="mt-1 font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === "success") return <span className="badge-green">{statusText[status]}</span>;
  if (status === "failed") return <span className="badge-red">{statusText[status]}</span>;
  if (status === "partial_success") return <span className="badge-orange">{statusText[status]}</span>;
  if (status === "running") return <span className="badge-blue">{statusText[status]}</span>;
  return <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 ring-1 ring-slate-200">{statusText[status] ?? status}</span>;
}

function formatDateTime(value: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

export const taskQueueRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/task-queue",
  component: TaskQueuePage
});
