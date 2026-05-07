import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import { Gamepad2, Pencil, Plus, RefreshCcw } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  createGame,
  fetchGames,
  syncAllGames,
  syncGame,
  updateGame,
  type GameListItem,
  type GamePayload,
} from "@/lib/api";
import { rootRoute } from "@/routes/__root";

type GameFormState = {
  appId: string;
  name: string;
  hasSyncConfig: boolean;
  enabled: boolean;
  hour: string;
  language: string;
  filter: string;
  reviewType: string;
  purchaseType: string;
  useReviewQuality: boolean;
  perPage: string;
};

const defaultGameForm: GameFormState = {
  appId: "",
  name: "",
  hasSyncConfig: false,
  enabled: false,
  hour: "9",
  language: "schinese",
  filter: "recent",
  reviewType: "all",
  purchaseType: "all",
  useReviewQuality: true,
  perPage: "100",
};

function GamesPage() {
  const queryClient = useQueryClient();
  const [selectedAppId, setSelectedAppId] = useState<number | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [form, setForm] = useState<GameFormState>(defaultGameForm);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const gamesQuery = useQuery({
    queryKey: ["games"],
    queryFn: fetchGames,
  });

  const selectedGame = useMemo(
    () => gamesQuery.data?.find((game) => game.app_id === selectedAppId) ?? null,
    [gamesQuery.data, selectedAppId],
  );

  useEffect(() => {
    if (!feedback) {
      return;
    }
    const timer = window.setTimeout(() => setFeedback(null), 3000);
    return () => window.clearTimeout(timer);
  }, [feedback]);

  useEffect(() => {
    if (selectedAppId !== null || isCreating) {
      return;
    }
    const firstGame = gamesQuery.data?.[0];
    if (firstGame) {
      setSelectedAppId(firstGame.app_id);
    }
  }, [gamesQuery.data, isCreating, selectedAppId]);

  useEffect(() => {
    if (!selectedGame || isCreating) {
      return;
    }
    setForm(gameToForm(selectedGame));
  }, [isCreating, selectedGame]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = formToPayload(form);
      if (selectedGame && !isCreating) {
        return updateGame(selectedGame.app_id, payload);
      }
      return createGame(payload);
    },
    onSuccess: (game) => {
      void queryClient.invalidateQueries({ queryKey: ["games"] });
      void queryClient.invalidateQueries({ queryKey: ["task-schedules"] });
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      setSelectedAppId(game.app_id);
      setIsCreating(false);
      setFeedback({ type: "success", message: selectedGame && !isCreating ? "游戏已更新。" : "游戏已创建。" });
    },
    onError: (error) => {
      setFeedback({ type: "error", message: (error as Error).message || "保存失败。" });
    },
  });

  const syncSingleMutation = useMutation({
    mutationFn: (appId: number) => syncGame(appId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["games"] });
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      void queryClient.invalidateQueries({ queryKey: ["task-queue"] });
      setFeedback({ type: "success", message: "手动同步任务已提交。" });
    },
    onError: (error) => {
      setFeedback({ type: "error", message: (error as Error).message || "手动同步失败。" });
    },
  });

  const syncAllMutation = useMutation({
    mutationFn: () => syncAllGames(),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ["games"] });
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      void queryClient.invalidateQueries({ queryKey: ["task-queue"] });
      setFeedback({ type: "success", message: `已提交 ${result.accepted_count} 个同步任务。` });
    },
    onError: (error) => {
      setFeedback({ type: "error", message: (error as Error).message || "全部同步失败。" });
    },
  });

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:py-8 xl:px-8">
      <section className="app-card p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="icon-tile">
              <Gamepad2 className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-slate-950">游戏列表</h1>
              <p className="mt-1 text-sm text-slate-500">
                按游戏名维护监控清单，并在每个游戏上执行手动同步或同步配置编辑。
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setIsCreating(true);
                setSelectedAppId(null);
                setForm(defaultGameForm);
              }}
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              新增游戏
            </Button>
            <Button type="button" disabled={syncAllMutation.isPending} onClick={() => syncAllMutation.mutate()}>
              <RefreshCcw className="h-4 w-4" aria-hidden="true" />
              {syncAllMutation.isPending ? "提交中..." : "全部同步"}
            </Button>
          </div>
        </div>
      </section>

      <section className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_420px]">
        <section className="app-card overflow-hidden p-0">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <div>
              <h2 className="text-base font-semibold text-slate-950">游戏清单</h2>
              <p className="mt-1 text-sm text-slate-500">主视图按游戏名展示，App ID 作为辅助信息。</p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full table-fixed">
              <thead className="bg-slate-50/80 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3">游戏名</th>
                  <th className="px-4 py-3">App ID</th>
                  <th className="px-4 py-3">评论数</th>
                  <th className="px-4 py-3">监控状态</th>
                  <th className="px-4 py-3">执行时间</th>
                  <th className="px-4 py-3">最近同步</th>
                  <th className="px-5 py-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                {(gamesQuery.data ?? []).map((game) => (
                  <tr
                    key={game.app_id}
                    className={`border-t border-slate-100 transition ${
                      selectedAppId === game.app_id && !isCreating ? "bg-blue-50/50" : "hover:bg-slate-50/70"
                    }`}
                  >
                    <td className="px-5 py-4">
                      <div className="font-medium text-slate-950">{game.name || `App ${game.app_id}`}</div>
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-500">{game.app_id}</td>
                    <td className="px-4 py-4 text-sm text-slate-700">{game.review_count.toLocaleString()}</td>
                    <td className="px-4 py-4">
                      {game.has_schedule ? (
                        <span className={game.schedule_enabled ? "badge-green" : "badge-orange"}>
                          {game.schedule_enabled ? "已启用" : "已停用"}
                        </span>
                      ) : (
                        <span className="badge-blue">未配置</span>
                      )}
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-700">
                      {game.has_schedule ? formatHour(game.schedule_hour) : "-"}
                    </td>
                    <td className="px-4 py-4 text-sm text-slate-500">
                      {formatTaskSummary(game.latest_task_status, game.latest_task_finished_at)}
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex justify-end gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          disabled={syncSingleMutation.isPending}
                          onClick={() => syncSingleMutation.mutate(game.app_id)}
                        >
                          <RefreshCcw className="h-4 w-4" aria-hidden="true" />
                          同步
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => {
                            setSelectedAppId(game.app_id);
                            setIsCreating(false);
                          }}
                        >
                          <Pencil className="h-4 w-4" aria-hidden="true" />
                          编辑
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!gamesQuery.isLoading && (gamesQuery.data?.length ?? 0) === 0 ? (
            <div className="p-6 text-sm text-slate-500">暂无游戏，先新增一个。</div>
          ) : null}
        </section>

        <section className="app-card p-5">
          <div>
            <h2 className="text-base font-semibold text-slate-950">
              {selectedGame && !isCreating ? "编辑游戏" : "新增游戏"}
            </h2>
            <p className="mt-1 text-sm text-slate-500">可只维护游戏，也可顺手配置这款游戏的每日同步任务。</p>
          </div>

          <div className="mt-5 grid gap-4">
            <InputField
              label="游戏名"
              value={form.name}
              onChange={(value) => setForm((current) => ({ ...current, name: value }))}
            />
            <InputField
              label="App ID"
              value={form.appId}
              disabled={!!selectedGame && !isCreating}
              onChange={(value) => setForm((current) => ({ ...current, appId: value }))}
            />
            <label className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={form.hasSyncConfig}
                onChange={(event) => setForm((current) => ({ ...current, hasSyncConfig: event.target.checked }))}
              />
              同时维护这款游戏的监控任务
            </label>
          </div>

          {form.hasSyncConfig ? (
            <div className="mt-5 grid gap-4 rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(event) => setForm((current) => ({ ...current, enabled: event.target.checked }))}
                />
                启用定时同步
              </label>
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
              <InputField
                label="每页抓取数"
                value={form.perPage}
                onChange={(value) => setForm((current) => ({ ...current, perPage: value }))}
              />
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={form.useReviewQuality}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, useReviewQuality: event.target.checked }))
                  }
                />
                使用新版评论价值体系
              </label>
            </div>
          ) : null}

          <div className="mt-5 flex flex-wrap gap-2">
            <Button type="button" disabled={saveMutation.isPending} onClick={() => saveMutation.mutate()}>
              {saveMutation.isPending ? "保存中..." : selectedGame && !isCreating ? "保存修改" : "创建游戏"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setIsCreating(true);
                setSelectedAppId(null);
                setForm(defaultGameForm);
              }}
            >
              重新新增
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => setForm(selectedGame && !isCreating ? gameToForm(selectedGame) : defaultGameForm)}
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
      </section>
    </main>
  );
}

function InputField({
  label,
  value,
  onChange,
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <label className="flex flex-col gap-2 text-sm">
      <span className="field-label">{label}</span>
      <input
        className="form-input"
        disabled={disabled}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  onChange,
  children,
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

function gameToForm(game: GameListItem): GameFormState {
  return {
    appId: String(game.app_id),
    name: game.name ?? "",
    hasSyncConfig: game.has_schedule,
    enabled: game.schedule_enabled,
    hour: String(game.schedule_hour ?? 9),
    language: String(game.schedule_options?.language ?? "schinese"),
    filter: String(game.schedule_options?.filter ?? "recent"),
    reviewType: String(game.schedule_options?.review_type ?? "all"),
    purchaseType: String(game.schedule_options?.purchase_type ?? "all"),
    useReviewQuality: Boolean(game.schedule_options?.use_review_quality ?? true),
    perPage: String(game.schedule_options?.per_page ?? 100),
  };
}

function formToPayload(form: GameFormState): GamePayload {
  return {
    app_id: Number(form.appId),
    name: form.name.trim(),
    sync: form.hasSyncConfig
      ? {
          enabled: form.enabled,
          hour: Number(form.hour),
          language: form.language,
          filter: form.filter,
          review_type: form.reviewType,
          purchase_type: form.purchaseType,
          use_review_quality: form.useReviewQuality,
          per_page: Number(form.perPage),
        }
      : null,
  };
}

function formatHour(value: number | null) {
  const hour = value ?? 0;
  return `${String(hour).padStart(2, "0")}:00`;
}

function formatTaskSummary(status: string | null, finishedAt: string | null) {
  if (!status) {
    return "-";
  }
  const dateText = finishedAt ? new Date(finishedAt).toLocaleString("zh-CN", { hour12: false }) : "未完成";
  return `${formatTaskStatus(status)} · ${dateText}`;
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

export const gamesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/games",
  component: GamesPage,
});
