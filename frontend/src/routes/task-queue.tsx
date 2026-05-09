import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import { ListOrdered } from "lucide-react";
import { useEffect, useState } from "react";

import {
  cancelTask,
  fetchGames,
  fetchProxyStatus,
  fetchTaskDetail,
  fetchTasksBySchedule,
  type ProxyModeStatus,
  type SyncJob,
  type TaskStatusGroup,
} from "@/lib/api";
import { rootRoute } from "@/routes/__root";

function TaskQueuePage() {
  const queryClient = useQueryClient();
  const [selectedAppId, setSelectedAppId] = useState<number | null>(null);
  const [selectedStatusGroup, setSelectedStatusGroup] = useState<TaskStatusGroup>("active");
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);

  const activeTasksQuery = useQuery({
    queryKey: ["task-queue", "active", selectedAppId ?? "all"],
    queryFn: () => fetchTasksBySchedule(undefined, selectedAppId, "active"),
    refetchInterval: 5000,
  });
  const terminalTasksQuery = useQuery({
    queryKey: ["task-queue", "terminal", selectedAppId ?? "all"],
    queryFn: () => fetchTasksBySchedule(undefined, selectedAppId, "terminal"),
    refetchInterval: 5000,
  });
  const gamesQuery = useQuery({
    queryKey: ["games"],
    queryFn: fetchGames,
  });

  const tasks =
    selectedStatusGroup === "terminal"
      ? (terminalTasksQuery.data ?? [])
      : (activeTasksQuery.data ?? []);
  const activeTaskCount = activeTasksQuery.data?.length ?? 0;
  const terminalTaskCount = terminalTasksQuery.data?.length ?? 0;

  useEffect(() => {
    if (!selectedTaskId && tasks.length > 0) {
      setSelectedTaskId(tasks[0]?.id ?? null);
    }
  }, [selectedTaskId, tasks]);

  useEffect(() => {
    if (tasks.length === 0) {
      setSelectedTaskId(null);
      return;
    }
    if (selectedTaskId && tasks.some((task) => task.id === selectedTaskId)) {
      return;
    }
    setSelectedTaskId(tasks[0]?.id ?? null);
  }, [selectedTaskId, tasks]);

  const detailQuery = useQuery({
    queryKey: ["task-queue-detail", selectedTaskId],
    queryFn: () => fetchTaskDetail(selectedTaskId as number),
    enabled: selectedTaskId !== null,
    refetchInterval: 5000,
  });
  const proxyStatusQuery = useQuery({
    queryKey: ["task-proxy-status"],
    queryFn: fetchProxyStatus,
    refetchInterval: 15000,
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
              默认只显示正在运行和排队中的任务。排序规则固定为：执行中、等待探针、排队中、取消中；已结束任务单独归档查看。
            </p>
          </div>
        </div>
      </section>

      <section className="mt-6 grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <div className="app-card p-4">
          <div className="flex flex-col gap-3">
            <h2 className="text-base font-semibold text-slate-950">任务列表</h2>
            <div className="grid grid-cols-2 gap-2">
              <StatusGroupButton
                title="进行中与排队"
                summary={`${activeTaskCount} 条`}
                active={selectedStatusGroup === "active"}
                onClick={() => setSelectedStatusGroup("active")}
              />
              <StatusGroupButton
                title="已结束任务"
                summary={`${terminalTaskCount} 条`}
                active={selectedStatusGroup === "terminal"}
                onClick={() => setSelectedStatusGroup("terminal")}
              />
            </div>
            <label className="flex flex-col gap-2 text-sm">
              <span className="field-label">按游戏筛选</span>
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
            {tasks.map((task) => (
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
                  {(task.game_name || `App ${task.app_id ?? "-"}`) +
                    " · " +
                    (task.trigger_type === "scheduled" ? "定时触发" : "手动触发")}
                </p>
                <p className="mt-3 text-sm text-slate-600">
                  新增 {task.inserted_count} / 更新 {task.updated_count} / 跳过 {task.skipped_count}
                </p>
                <div className="mt-3 space-y-1 text-xs text-slate-500">
                  <p>开始：{formatDateTimeNullable(task.started_at)}</p>
                  <p>结束：{formatDateTimeNullable(task.finished_at)}</p>
                </div>
              </button>
            ))}
            {!activeTasksQuery.isLoading && !terminalTasksQuery.isLoading && tasks.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-6 text-sm text-slate-500">
                {selectedStatusGroup === "active"
                  ? "当前没有正在运行或排队中的任务。"
                  : "当前没有已结束的任务。"}
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
                <Metric
                  label="游戏"
                  value={detailQuery.data.game_name ?? `App ${detailQuery.data.app_id ?? "-"}`}
                />
                <Metric label="App ID" value={String(detailQuery.data.app_id ?? "-")} />
                <Metric
                  label="触发方式"
                  value={detailQuery.data.trigger_type === "scheduled" ? "定时" : "手动"}
                />
                <Metric label="请求规模" value={String(detailQuery.data.requested_limit ?? "-")} />
                <Metric label="开始时间" value={formatDateTimeNullable(detailQuery.data.started_at)} />
                <Metric label="结束时间" value={formatDateTimeNullable(detailQuery.data.finished_at)} />
              </div>

              <div className="mt-6">
                <h3 className="text-base font-semibold text-slate-950">代理状态</h3>
                {proxyStatusQuery.data ? (
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <ProxyModeCard
                      title="抓取链"
                      mode={proxyStatusQuery.data.scraping}
                      host={proxyStatusQuery.data.host}
                      scheme={proxyStatusQuery.data.scheme}
                    />
                    <ProxyModeCard
                      title="发送链"
                      mode={proxyStatusQuery.data.sending}
                      host={proxyStatusQuery.data.host}
                      scheme={proxyStatusQuery.data.scheme}
                    />
                  </div>
                ) : (
                  <div className="mt-3 rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-4 text-sm text-slate-500">
                    正在获取代理状态...
                  </div>
                )}
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
                      {extractTransportSummary(log.details) ? (
                        <div className="mt-3 rounded-2xl border border-emerald-100 bg-emerald-50/70 p-3 text-xs text-emerald-800">
                          {extractTransportSummary(log.details)}
                        </div>
                      ) : null}
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

function StatusGroupButton({
  title,
  summary,
  active,
  onClick,
}: {
  title: string;
  summary: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-2xl border px-4 py-3 text-left transition ${
        active
          ? "border-blue-200 bg-blue-50 text-blue-700 shadow-sm"
          : "border-slate-200 bg-slate-50/70 text-slate-600 hover:border-blue-200 hover:bg-blue-50/40"
      }`}
    >
      <p className="text-sm font-semibold">{title}</p>
      <p className="mt-1 text-xs opacity-80">{summary}</p>
    </button>
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

function ProxyModeCard({
  title,
  mode,
  host,
  scheme,
}: {
  title: string;
  mode: ProxyModeStatus;
  host: string;
  scheme: string;
}) {
  const location = (mode.location ?? {}) as Record<string, unknown>;
  const ip = typeof location.ip === "string" ? location.ip : "—";
  const providers =
    location.providers && typeof location.providers === "object"
      ? (location.providers as Record<string, unknown>)
      : null;
  const dbip =
    providers?.dbip && typeof providers.dbip === "object"
      ? (providers.dbip as Record<string, unknown>)
      : null;
  const country = typeof dbip?.country === "string" ? dbip.country : "—";
  const city = typeof dbip?.city === "string" ? dbip.city : "—";

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-slate-950">{title}</p>
        <span className={mode.ok ? "badge-green" : "badge-orange"}>
          {mode.proxy_enabled ? (mode.ok ? "可用" : "异常") : "未启用"}
        </span>
      </div>
      <div className="mt-3 space-y-2 text-sm text-slate-600">
        <p>模式：{mode.proxy_mode}</p>
        <p>入口：{scheme}://{host}:{mode.proxy_port ?? "—"}</p>
        <p>IP：{ip}</p>
        <p>地区：{country} / {city}</p>
        <p>说明：{mode.exact_ip ? "精确会话 IP" : "示例诊断 IP"}</p>
        <p>回退：{mode.proxy_fallback_enabled ? "允许直连回退" : "仅代理"}</p>
        {mode.proxy_error ? <p className="text-rose-600">错误：{mode.proxy_error}</p> : null}
      </div>
      <p className="mt-3 text-xs leading-5 text-slate-500">{mode.note}</p>
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
    waiting: "等待探针",
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
  if (status === "waiting" || status === "cancel_requested" || status === "partial_success") {
    return "badge-orange";
  }
  if (status === "cancelled") {
    return "rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600";
  }
  if (status === "success") {
    return "badge-green";
  }
  return "badge-blue";
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function formatDateTimeNullable(value: string | null) {
  if (!value) {
    return "—";
  }
  return formatDateTime(value);
}

function extractTransportSummary(details: Record<string, unknown> | null) {
  if (!details) {
    return null;
  }
  const candidate =
    details.transport && typeof details.transport === "object"
      ? (details.transport as Record<string, unknown>)
      : details;
  const location =
    candidate.location && typeof candidate.location === "object"
      ? (candidate.location as Record<string, unknown>)
      : null;
  const ip = location && typeof location.ip === "string" ? location.ip : null;
  const port = typeof candidate.proxy_port === "number" ? candidate.proxy_port : null;
  const exact = typeof candidate.exact_ip === "boolean" ? candidate.exact_ip : null;
  if (!ip && port === null) {
    return null;
  }
  return `代理 ${candidate.proxy_mode ?? "unknown"} · 端口 ${port ?? "—"} · IP ${ip ?? "—"} · ${
    exact ? "精确会话 IP" : "示例诊断 IP"
  }`;
}

export const taskQueueRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/task-queue",
  component: TaskQueuePage,
});
