import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import { Clock3, Plus, RefreshCcw, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  createTaskSchedule,
  deleteTaskSchedule,
  enqueueReviewSync,
  fetchTaskSchedules,
  fetchTasksBySchedule,
  updateTaskSchedule,
  type SyncJob,
  type TaskSchedule
} from "@/lib/api";
import { rootRoute } from "@/routes/__root";

type ScheduleFormState = {
  name: string;
  appId: string;
  hour: string;
  enabled: boolean;
  language: string;
  filter: string;
  reviewType: string;
  purchaseType: string;
  useReviewQuality: boolean;
  perPage: string;
};

const defaultScheduleForm: ScheduleFormState = {
  name: "",
  appId: "3350200",
  hour: "9",
  enabled: true,
  language: "schinese",
  filter: "recent",
  reviewType: "all",
  purchaseType: "all",
  useReviewQuality: true,
  perPage: "100"
};

function TasksPage() {
  const queryClient = useQueryClient();
  const [selectedScheduleId, setSelectedScheduleId] = useState<number | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [form, setForm] = useState<ScheduleFormState>(defaultScheduleForm);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const schedulesQuery = useQuery({
    queryKey: ["task-schedules"],
    queryFn: fetchTaskSchedules
  });
  const jobsQuery = useQuery({
    queryKey: ["tasks", selectedScheduleId ?? "all"],
    queryFn: () => fetchTasksBySchedule(selectedScheduleId),
    refetchInterval: 5000
  });

  const selectedSchedule = useMemo(
    () => schedulesQuery.data?.find((item) => item.id === selectedScheduleId) ?? null,
    [schedulesQuery.data, selectedScheduleId]
  );

  useEffect(() => {
    if (!feedback) {
      return;
    }
    const timer = window.setTimeout(() => setFeedback(null), 3000);
    return () => window.clearTimeout(timer);
  }, [feedback]);

  useEffect(() => {
    if (selectedScheduleId !== null || isCreating) {
      return;
    }
    const firstSchedule = schedulesQuery.data?.[0];
    if (firstSchedule) {
      setSelectedScheduleId(firstSchedule.id);
    }
  }, [isCreating, selectedScheduleId, schedulesQuery.data]);

  useEffect(() => {
    if (!selectedSchedule) {
      return;
    }
    setIsCreating(false);
    setForm(scheduleToForm(selectedSchedule));
  }, [selectedSchedule]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = formToPayload(form);
      if (selectedSchedule) {
        return updateTaskSchedule(selectedSchedule.id, payload);
      }
      return createTaskSchedule(payload);
    },
    onSuccess: (schedule) => {
      void queryClient.invalidateQueries({ queryKey: ["task-schedules"] });
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      setIsCreating(false);
      setSelectedScheduleId(schedule.id);
      setFeedback({ type: "success", message: selectedSchedule ? "监控任务已更新。" : "监控任务已创建。" });
    },
    onError: (error) => {
      setFeedback({ type: "error", message: (error as Error).message || "保存失败。" });
    }
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!selectedSchedule) {
        return;
      }
      await deleteTaskSchedule(selectedSchedule.id);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["task-schedules"] });
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      setIsCreating(false);
      setSelectedScheduleId(null);
      setForm(defaultScheduleForm);
      setFeedback({ type: "success", message: "监控任务已删除。" });
    },
    onError: (error) => {
      setFeedback({ type: "error", message: (error as Error).message || "删除失败。" });
    }
  });

  const syncMutation = useMutation({
    mutationFn: async () => {
      if (!selectedSchedule) {
        throw new Error("请先选择一个监控任务");
      }
      if (selectedSchedule) {
        setIsCreating(false);
      }
      return enqueueReviewSync({
        app_id: selectedSchedule.app_id ?? Number(form.appId),
        schedule_id: selectedSchedule.id,
        language: String(selectedSchedule.options?.language ?? "schinese"),
        filter: String(selectedSchedule.options?.filter ?? "recent"),
        review_type: String(selectedSchedule.options?.review_type ?? "all"),
        purchase_type: String(selectedSchedule.options?.purchase_type ?? "all"),
        use_review_quality: Boolean(selectedSchedule.options?.use_review_quality ?? true),
        per_page: Number(selectedSchedule.options?.per_page ?? 100)
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      void queryClient.invalidateQueries({ queryKey: ["task-queue"] });
      setFeedback({ type: "success", message: "手动同步任务已提交。" });
    },
    onError: (error) => {
      setFeedback({ type: "error", message: (error as Error).message || "手动同步失败。" });
    }
  });

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:py-8 xl:px-8">
      <section className="app-card p-6">
        <div className="flex items-center gap-3">
          <div className="icon-tile">
            <Clock3 className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-slate-950">任务与同步</h1>
            <p className="mt-1 text-sm text-slate-500">
              维护多个游戏监控任务，并按每日固定小时执行 Steam 增量追新。
            </p>
          </div>
        </div>
      </section>

      <section className="mt-6 grid gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <div className="app-card p-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-slate-950">监控任务</h2>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setIsCreating(true);
                setSelectedScheduleId(null);
                setForm(defaultScheduleForm);
              }}
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              新建
            </Button>
          </div>
          <div className="mt-4 grid gap-3">
            {(schedulesQuery.data ?? []).map((schedule) => (
              <button
                key={schedule.id}
                type="button"
                onClick={() => setSelectedScheduleId(schedule.id)}
                className={`rounded-2xl border p-4 text-left transition ${
                  selectedScheduleId === schedule.id
                    ? "border-blue-200 bg-blue-50/80 shadow-sm"
                    : "border-slate-200 bg-slate-50/70 hover:border-blue-200 hover:bg-blue-50/40"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-950">{schedule.name}</p>
                    <p className="mt-1 text-xs text-slate-500">App {schedule.app_id ?? "-"} · 每天 {formatHour(schedule.hour)}</p>
                  </div>
                  <span className={schedule.is_enabled ? "badge-green" : "badge-orange"}>
                    {schedule.is_enabled ? "启用中" : "已停用"}
                  </span>
                </div>
              </button>
            ))}
            {!schedulesQuery.isLoading && (schedulesQuery.data?.length ?? 0) === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-6 text-sm text-slate-500">
                还没有监控任务，先创建一个。
              </div>
            ) : null}
          </div>
        </div>

        <div className="grid gap-6">
          <section className="app-card p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-slate-950">
                  {selectedSchedule && !isCreating ? "编辑监控任务" : "创建监控任务"}
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  每条任务绑定一个游戏，每天在固定小时执行一次增量追新。
                </p>
              </div>
              {selectedSchedule && !isCreating ? (
                <div className="flex gap-2">
                  <Button
                    type="button"
                    disabled={syncMutation.isPending}
                    onClick={() => syncMutation.mutate()}
                  >
                    <RefreshCcw className="h-4 w-4" aria-hidden="true" />
                    {syncMutation.isPending ? "提交中..." : "手动同步"}
                  </Button>
                  <Button
                    type="button"
                    variant="danger"
                    disabled={deleteMutation.isPending}
                    onClick={() => {
                      if (window.confirm("确认删除这个监控任务？")) {
                        deleteMutation.mutate();
                      }
                    }}
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                    删除
                  </Button>
                </div>
              ) : null}
            </div>

            <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              <InputField label="任务名称" value={form.name} onChange={(value) => setForm((current) => ({ ...current, name: value }))} />
              <InputField label="App ID" value={form.appId} onChange={(value) => setForm((current) => ({ ...current, appId: value }))} />
              <SelectField label="执行时间" value={form.hour} onChange={(value) => setForm((current) => ({ ...current, hour: value }))}>
                {Array.from({ length: 24 }, (_, hour) => (
                  <option key={hour} value={String(hour)}>
                    每天 {formatHour(hour)}
                  </option>
                ))}
              </SelectField>
              <SelectField label="语言" value={form.language} onChange={(value) => setForm((current) => ({ ...current, language: value }))}>
                <option value="schinese">简体中文</option>
                <option value="english">English</option>
              </SelectField>
              <SelectField label="显示顺序" value={form.filter} onChange={(value) => setForm((current) => ({ ...current, filter: value }))}>
                <option value="recent">最新</option>
                <option value="updated">最近更新</option>
                <option value="all">概览</option>
              </SelectField>
              <SelectField label="评价类型" value={form.reviewType} onChange={(value) => setForm((current) => ({ ...current, reviewType: value }))}>
                <option value="all">全部</option>
                <option value="positive">好评</option>
                <option value="negative">差评</option>
              </SelectField>
              <SelectField label="购买类型" value={form.purchaseType} onChange={(value) => setForm((current) => ({ ...current, purchaseType: value }))}>
                <option value="all">全部</option>
                <option value="steam">Steam 购买</option>
                <option value="non_steam_purchase">非 Steam 购买</option>
              </SelectField>
              <InputField label="每页抓取数" value={form.perPage} onChange={(value) => setForm((current) => ({ ...current, perPage: value }))} />
              <label className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-700 transition hover:border-blue-200 hover:bg-blue-50/30">
                <input
                  type="checkbox"
                  checked={form.useReviewQuality}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, useReviewQuality: event.target.checked }))
                  }
                />
                使用新版评论价值体系
              </label>
              <label className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-700 transition hover:border-blue-200 hover:bg-blue-50/30">
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(event) => setForm((current) => ({ ...current, enabled: event.target.checked }))}
                />
                启用定时同步
              </label>
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              <Button type="button" disabled={saveMutation.isPending} onClick={() => saveMutation.mutate()}>
                {saveMutation.isPending ? "保存中..." : selectedSchedule && !isCreating ? "保存修改" : "创建任务"}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() =>
                  setForm(selectedSchedule && !isCreating ? scheduleToForm(selectedSchedule) : defaultScheduleForm)
                }
              >
                重置表单
              </Button>
            </div>

            {feedback ? (
              <div
                className={`mt-4 rounded-2xl border px-4 py-3 text-sm ${
                  feedback.type === "success"
                    ? "border-emerald-200 bg-emerald-50/80 text-emerald-700"
                    : "border-rose-200 bg-rose-50/80 text-rose-700"
                }`}
              >
                {feedback.message}
              </div>
            ) : null}
          </section>

          <section className="app-card p-5">
            <h2 className="text-base font-semibold text-slate-950">
              {selectedSchedule ? `${selectedSchedule.name} · 最近执行` : "最近执行"}
            </h2>
            <div className="mt-4 grid gap-3">
              {(jobsQuery.data ?? []).map((job) => (
                <TaskCard key={job.id} job={job} />
              ))}
              {!jobsQuery.isLoading && (jobsQuery.data?.length ?? 0) === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-6 text-sm text-slate-500">
                  当前筛选下暂无任务记录。
                </div>
              ) : null}
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}

function InputField({
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
      <span className="field-label">{label}</span>
      <input className="form-input" value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function SelectField({
  label,
  value,
  onChange,
  children
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <label className="flex flex-col gap-2 text-sm">
      <span className="field-label">{label}</span>
      <select className="form-input" value={value} onChange={(event) => onChange(event.target.value)}>
        {children}
      </select>
    </label>
  );
}

function TaskCard({ job }: { job: SyncJob }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 transition hover:border-blue-200 hover:bg-blue-50/30">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-950">#{job.id} · {job.schedule_name ?? "手动同步"}</p>
          <p className="mt-1 text-xs text-slate-500">
            App {job.app_id ?? "-"} · {job.trigger_type === "scheduled" ? "定时触发" : "手动触发"}
          </p>
        </div>
        <span className={taskStatusBadge(job.status)}>{formatTaskStatus(job.status)}</span>
      </div>
      <p className="mt-3 text-sm text-slate-600">
        新增 {job.inserted_count} / 更新 {job.updated_count} / 跳过 {job.skipped_count}
      </p>
    </article>
  );
}

function scheduleToForm(schedule: TaskSchedule): ScheduleFormState {
  return {
    name: schedule.name,
    appId: String(schedule.app_id ?? ""),
    hour: String(schedule.hour ?? 0),
    enabled: schedule.is_enabled,
    language: String(schedule.options?.language ?? "schinese"),
    filter: String(schedule.options?.filter ?? "recent"),
    reviewType: String(schedule.options?.review_type ?? "all"),
    purchaseType: String(schedule.options?.purchase_type ?? "all"),
    useReviewQuality: Boolean(schedule.options?.use_review_quality ?? true),
    perPage: String(schedule.options?.per_page ?? 100)
  };
}

function formToPayload(form: ScheduleFormState) {
  return {
    name: form.name.trim(),
    is_enabled: form.enabled,
    app_id: Number(form.appId),
    interval: "daily" as const,
    hour: Number(form.hour),
    options: {
      language: form.language,
      filter: form.filter,
      review_type: form.reviewType,
      purchase_type: form.purchaseType,
      use_review_quality: form.useReviewQuality,
      per_page: Number(form.perPage)
    }
  };
}

function formatHour(value: number | null) {
  const hour = value ?? 0;
  return `${String(hour).padStart(2, "0")}:00`;
}

function formatTaskStatus(value: string) {
  const mapping: Record<string, string> = {
    pending: "排队中",
    running: "执行中",
    success: "成功",
    partial_success: "部分成功",
    failed: "失败"
  };
  return mapping[value] ?? value;
}

function taskStatusBadge(status: string) {
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

export const tasksRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/tasks",
  component: TasksPage
});
