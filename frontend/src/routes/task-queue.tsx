import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import { ListOrdered } from "lucide-react";
import { useEffect, useState } from "react";

import { cancelTask, fetchGames, fetchTaskDetail, fetchTasksBySchedule, type SyncJob } from "@/lib/api";
import { rootRoute } from "@/routes/__root";

function TaskQueuePage() {
  const queryClient = useQueryClient();
  const [selectedAppId, setSelectedAppId] = useState<number | null>(null);
  const tasksQuery = useQuery({
    queryKey: ["task-queue", selectedAppId ?? "all"],
    queryFn: () => fetchTasksBySchedule(undefined, selectedAppId),
    refetchInterval: 5000,
  });
  const gamesQuery = useQuery({
    queryKey: ["games"],
    queryFn: fetchGames,
  });
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);

  useEffect(() => {
    if (!selectedTaskId && (tasksQuery.data?.length ?? 0) > 0) {
      setSelectedTaskId(tasksQuery.data?.[0]?.id ?? null);
    }
  }, [selectedTaskId, tasksQuery.data]);

  useEffect(() => {
    if ((tasksQuery.data?.length ?? 0) === 0) {
      setSelectedTaskId(null);
      return;
    }
    if (selectedTaskId && tasksQuery.data?.some((task) => task.id === selectedTaskId)) {
      return;
    }
    setSelectedTaskId(tasksQuery.data?.[0]?.id ?? null);
  }, [selectedTaskId, tasksQuery.data]);

  const detailQuery = useQuery({
    queryKey: ["task-queue-detail", selectedTaskId],
    queryFn: () => fetchTaskDetail(selectedTaskId as number),
    enabled: selectedTaskId !== null,
    refetchInterval: 5000,
  });
  const cancelMutation = useMutation({
    mutationFn: (taskId: number) => cancelTask(taskId),
    onSuccess: async (_, taskId) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["task-queue"] }),
        queryClient.invalidateQueries({ queryKey: ["task-indicator"] }),
        queryClient.invalidateQueries({ queryKey: ["task-queue-detail", taskId] }),
      ]);
    },
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
          <div className="flex flex-col gap-3">
            <h2 className="text-base font-semibold text-slate-950">任务列表</h2>
            <label className="flex flex-col gap-2 text-sm">
              <span className="field-label">按监控任务筛选</span>
              <select
                className="form-input"
                value={selectedAppId ?? ""}
                onChange={(event) =>
                  setSelectedAppId(event.target.value ? Number(event.target.value) : null)
                }
              >
                <option value="">全部任务</option>
                {(gamesQuery.data ?? []).map((game) => (
                  <option key={game.app_id} value={game.app_id}>
                    {game.name || `App ${game.app_id}`}
                  </option>
                ))}
              </select>
            </label>
          </div>
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
                  {(task.game_name || `App ${task.app_id ?? "-"}`) + " · " + (task.trigger_type === "scheduled" ? "定时触发" : "手动触发")}
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
                <div className="flex items-center gap-3">
                  {detailQuery.data.can_cancel ? (
                    <button
                      type="button"
                      className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={cancelMutation.isPending}
                      onClick={() => cancelMutation.mutate(detailQuery.data!.id)}
                    >
                      {cancelMutation.isPending ? "取消中..." : "取消任务"}
                    </button>
                  ) : null}
                  <span className={statusBadgeClass(detailQuery.data.status)}>
                    {formatTaskStatus(detailQuery.data.status)}
                  </span>
                </div>
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-3">
                <Metric label="监控任务" value={detailQuery.data.schedule_name ?? "手动同步"} />
                <Metric label="游戏" value={detailQuery.data.game_name ?? `App ${detailQuery.data.app_id ?? "-"}`} />
                <Metric label="App ID" value={String(detailQuery.data.app_id ?? "-")} />
                <Metric label="触发方式" value={detailQuery.data.trigger_type === "scheduled" ? "定时" : "手动"} />
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
    cancel_requested: "取消中",
    cancelled: "已取消",
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
  if (status === "cancel_requested") {
    return "badge-orange";
  }
  if (status === "cancelled") {
    return "rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600";
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
