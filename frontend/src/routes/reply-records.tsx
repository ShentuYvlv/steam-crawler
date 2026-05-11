import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import {
  CalendarDays,
  CheckCircle2,
  Clock3,
  ExternalLink,
  Gamepad2,
  MessageSquareMore,
  RefreshCcw,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  createReplyDeleteRequest,
  fetchGames,
  fetchReplyAuditQueue,
  fetchReplyRecords,
  regenerateReplyDraft,
  sendReviewReply,
  updateReplyDraft,
  type GameListItem,
  type ReplyDraftAuditItem,
  type ReplyRecord,
} from "@/lib/api";
import { rootRoute } from "@/routes/__root";

const AUDIT_QUEUE_QUERY = { limit: 500 };
const SENT_RECORD_QUERY = { status: "sent", limit: 500 };

type GameSummary = {
  appId: number;
  name: string;
  draftCount: number;
  sentCount: number;
  totalCount: number;
  latestAt: string | null;
};

type DaySummary = {
  dayKey: string;
  label: string;
  draftCount: number;
  sentCount: number;
  totalCount: number;
  latestAt: string | null;
};

function ReplyRecordsPage() {
  const [selectedAppId, setSelectedAppId] = useState<number | null>(null);
  const [selectedDayKey, setSelectedDayKey] = useState<string | null>(null);

  const gamesQuery = useQuery({ queryKey: ["games"], queryFn: fetchGames });
  const auditQueueQuery = useQuery({
    queryKey: ["reply-audit-queue", AUDIT_QUEUE_QUERY],
    queryFn: () => fetchReplyAuditQueue(AUDIT_QUEUE_QUERY),
  });
  const recordsQuery = useQuery({
    queryKey: ["reply-records", SENT_RECORD_QUERY],
    queryFn: () => fetchReplyRecords(SENT_RECORD_QUERY),
  });

  const gameSummaries = useMemo(
    () =>
      buildGameSummaries(
        auditQueueQuery.data ?? [],
        recordsQuery.data ?? [],
        gamesQuery.data ?? [],
      ),
    [auditQueueQuery.data, recordsQuery.data, gamesQuery.data],
  );

  useEffect(() => {
    if (gameSummaries.length === 0) {
      setSelectedAppId(null);
      return;
    }
    if (
      selectedAppId === null ||
      !gameSummaries.some((game) => game.appId === selectedAppId)
    ) {
      setSelectedAppId(gameSummaries[0].appId);
    }
  }, [gameSummaries, selectedAppId]);

  const daySummaries = useMemo(
    () =>
      buildDaySummaries(
        selectedAppId,
        auditQueueQuery.data ?? [],
        recordsQuery.data ?? [],
      ),
    [selectedAppId, auditQueueQuery.data, recordsQuery.data],
  );

  useEffect(() => {
    if (daySummaries.length === 0) {
      setSelectedDayKey(null);
      return;
    }
    if (
      selectedDayKey === null ||
      !daySummaries.some((day) => day.dayKey === selectedDayKey)
    ) {
      setSelectedDayKey(daySummaries[0].dayKey);
    }
  }, [daySummaries, selectedDayKey]);

  const selectedGame = useMemo(
    () => gameSummaries.find((game) => game.appId === selectedAppId) ?? null,
    [gameSummaries, selectedAppId],
  );
  const selectedDay = useMemo(
    () => daySummaries.find((day) => day.dayKey === selectedDayKey) ?? null,
    [daySummaries, selectedDayKey],
  );

  const selectedDrafts = useMemo(() => {
    if (selectedAppId === null || selectedDayKey === null) {
      return [];
    }
    return [...(auditQueueQuery.data ?? [])]
      .filter(
        (item) =>
          item.app_id === selectedAppId && getDraftDayKey(item) === selectedDayKey,
      )
      .sort((left, right) =>
        compareTimestamps(getDraftTimestamp(right), getDraftTimestamp(left)),
      );
  }, [auditQueueQuery.data, selectedAppId, selectedDayKey]);

  const selectedSentRecords = useMemo(() => {
    if (selectedAppId === null || selectedDayKey === null) {
      return [];
    }
    return [...(recordsQuery.data ?? [])]
      .filter(
        (item) =>
          (item.app_id ?? 0) === selectedAppId &&
          getRecordDayKey(item) === selectedDayKey,
      )
      .sort((left, right) =>
        compareTimestamps(getRecordTimestamp(right), getRecordTimestamp(left)),
      );
  }, [recordsQuery.data, selectedAppId, selectedDayKey]);

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:py-8 xl:px-8">
      <section className="grid gap-3 xl:grid-cols-[248px_208px_minmax(0,1fr)_minmax(0,1fr)]">
        <aside className="app-card flex min-h-[760px] flex-col p-4">
          <RailHeader
            icon={<Gamepad2 className="h-4 w-4" aria-hidden="true" />}
            title="游戏"
            description="按游戏聚合回复记录"
          />
          <div className="mt-4 flex-1 space-y-3 overflow-y-auto pr-1">
            {gameSummaries.map((game) => (
              <GameRailCard
                key={game.appId}
                game={game}
                active={game.appId === selectedAppId}
                onClick={() => setSelectedAppId(game.appId)}
              />
            ))}
            {!gamesQuery.isLoading && gameSummaries.length === 0 ? (
              <EmptyState text="暂无可查看的游戏记录。" compact />
            ) : null}
          </div>
        </aside>

        <aside className="app-card flex min-h-[760px] flex-col p-4">
          <RailHeader
            icon={<CalendarDays className="h-4 w-4" aria-hidden="true" />}
            title="时间"
            description="按日期切换审核与发送记录"
          />
          <div className="mt-4 flex-1 space-y-2.5 overflow-y-auto pr-1">
            {daySummaries.map((day) => (
              <DayRailCard
                key={day.dayKey}
                day={day}
                active={day.dayKey === selectedDayKey}
                onClick={() => setSelectedDayKey(day.dayKey)}
              />
            ))}
            {!auditQueueQuery.isLoading &&
            !recordsQuery.isLoading &&
            daySummaries.length === 0 ? (
              <EmptyState text="当前游戏暂无日期记录。" compact />
            ) : null}
          </div>
        </aside>

        <section className="app-card flex min-h-[760px] flex-col p-5">
          <ColumnHeader
            eyebrow="待审核草稿"
            title={selectedGame?.name ?? "请选择游戏"}
            description=""
            count={selectedDrafts.length}
            tone="amber"
          />
          <div className="mt-5 flex-1 space-y-4 overflow-y-auto pr-1">
            {selectedDrafts.map((item) => (
              <DraftCard key={item.id} item={item} />
            ))}
            {!auditQueueQuery.isLoading &&
            selectedGame &&
            selectedDay &&
            selectedDrafts.length === 0 ? (
              <EmptyState text="这一天没有待审核草稿。" />
            ) : null}
            {!selectedGame ? <EmptyState text="先在左侧选择一个游戏。" /> : null}
            {selectedGame && !selectedDay ? (
              <EmptyState text="再从第二列选择一个日期。" />
            ) : null}
          </div>
        </section>

        <section className="app-card flex min-h-[760px] flex-col p-5">
          <ColumnHeader
            eyebrow="已发送评论"
            title={selectedGame?.name ?? "请选择游戏"}
            description={
              selectedDay
                ? `当前查看 ${selectedDay.label} 已发往 Steam 的回复`
                : "先选择左侧日期，再查看已发送记录"
            }
            count={selectedSentRecords.length}
            tone="emerald"
          />
          <div className="mt-5 flex-1 space-y-4 overflow-y-auto pr-1">
            {selectedSentRecords.map((item) => (
              <SentRecordCard key={item.id} item={item} />
            ))}
            {!recordsQuery.isLoading &&
            selectedGame &&
            selectedDay &&
            selectedSentRecords.length === 0 ? (
              <EmptyState text="这一天还没有已发送评论。" />
            ) : null}
            {!selectedGame ? <EmptyState text="先在左侧选择一个游戏。" /> : null}
            {selectedGame && !selectedDay ? (
              <EmptyState text="再从第二列选择一个日期。" />
            ) : null}
          </div>
        </section>
      </section>
    </main>
  );
}

function DraftCard({ item }: { item: ReplyDraftAuditItem }) {
  const queryClient = useQueryClient();
  const [draftText, setDraftText] = useState(item.content ?? "");

  useEffect(() => {
    setDraftText(item.content ?? "");
  }, [item.content, item.id]);

  const saveMutation = useMutation({
    mutationFn: async () => updateReplyDraft(item.id, { content: draftText }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reply-audit-queue"] });
    },
  });

  const regenerateMutation = useMutation({
    mutationFn: async () => regenerateReplyDraft(item.review_id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reply-audit-queue"] });
      void queryClient.invalidateQueries({ queryKey: ["reviews"] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: async () => updateReplyDraft(item.id, { status: "rejected" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reply-audit-queue"] });
      void queryClient.invalidateQueries({ queryKey: ["reviews"] });
      void queryClient.invalidateQueries({ queryKey: ["review"] });
    },
  });

  const refreshReplyState = () => {
    const refresh = () => {
      void queryClient.invalidateQueries({ queryKey: ["reply-audit-queue"] });
      void queryClient.invalidateQueries({ queryKey: ["reply-records"] });
      void queryClient.invalidateQueries({ queryKey: ["reviews"] });
    };
    refresh();
    window.setTimeout(refresh, 2000);
    window.setTimeout(refresh, 5000);
  };

  const sendMutation = useMutation({
    mutationFn: async () =>
      sendReviewReply(item.review_id, {
        draft_id: item.id,
        content: draftText,
        confirmed: true,
      }),
    onSuccess: () => {
      refreshReplyState();
    },
    onError: () => {
      refreshReplyState();
    },
  });

  return (
    <article className="soft-panel overflow-hidden border border-amber-100 bg-[linear-gradient(180deg,_rgba(255,251,235,0.9),_rgba(255,255,255,0.96))] p-3.5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge tone="amber">{getDraftStatusLabel(item.status)}</StatusBadge>
            <ReviewMoodBadge votedUp={item.voted_up} />
          </div>
          <p className="mt-2.5 text-[15px] font-semibold text-slate-950">
            {item.persona_name || "匿名玩家"}
            <span className="px-2 text-slate-300">|</span>
            <span className="text-[13px] font-medium text-slate-500">
              {formatDateTime(item.timestamp_created ?? item.created_at)}
            </span>
          </p>
        </div>
        {item.review_url ? (
          <Button
            asChild
            type="button"
            variant="outline"
            className="h-8 px-3 text-xs"
          >
            <a href={item.review_url} target="_blank" rel="noreferrer">
              <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              打开 Steam
            </a>
          </Button>
        ) : null}
      </div>

      {item.error_message ? (
        <div className="mt-3 rounded-2xl border border-rose-100 bg-rose-50 px-3 py-2.5 text-sm text-rose-700">
          生成失败：{item.error_message}
        </div>
      ) : null}

      {sendMutation.isError ? (
        <div className="mt-3 rounded-2xl border border-rose-100 bg-rose-50 px-3 py-2.5 text-sm text-rose-700">
          {(sendMutation.error as Error).message}
        </div>
      ) : null}

      <div className="mt-3 grid gap-2.5">
        <ContentPanel
          label="评论内容"
          count={(item.review_text || "").length}
          content={item.review_text || "暂无评论内容"}
          compact
        />

        <section className="rounded-[20px] border border-slate-200 bg-white p-3.5 shadow-sm shadow-slate-100/80">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              回复草稿
            </p>
            <span className="text-[11px] text-slate-400">
              {draftText.trim().length} 字
            </span>
          </div>
          <textarea
            className="mt-2.5 min-h-[128px] w-full resize-y rounded-2xl border border-slate-200 bg-slate-50/70 px-3 py-2.5 text-sm leading-6 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-300 focus:bg-white focus:ring-4 focus:ring-blue-100"
            value={draftText}
            onChange={(event) => setDraftText(event.target.value)}
          />
        </section>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <Button
          type="button"
          variant="outline"
          className="h-8 px-3 text-xs"
          disabled={saveMutation.isPending || draftText.trim().length === 0}
          onClick={() => saveMutation.mutate()}
        >
          {saveMutation.isPending ? "保存中" : "保存"}
        </Button>
        <Button
          type="button"
          variant="secondary"
          className="h-8 px-3 text-xs"
          disabled={regenerateMutation.isPending}
          onClick={() => regenerateMutation.mutate()}
        >
          <RefreshCcw className="h-4 w-4" aria-hidden="true" />
          {regenerateMutation.isPending ? "生成中" : "重生成"}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="h-8 px-3 text-xs"
          disabled={rejectMutation.isPending}
          onClick={() => {
            if (window.confirm("确认驳回这条草稿吗？驳回后会从待审核列表移除。")) {
              rejectMutation.mutate();
            }
          }}
        >
          {rejectMutation.isPending ? "驳回中" : "驳回"}
        </Button>
        <Button
          type="button"
          className="h-8 flex-1 px-3 text-xs"
          disabled={sendMutation.isPending || draftText.trim().length === 0}
          onClick={() => {
            if (window.confirm("确认通过并发送这条回复到 Steam 吗？")) {
              sendMutation.mutate();
            }
          }}
        >
          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
          {sendMutation.isPending ? "发送中" : "通过发送"}
        </Button>
      </div>
    </article>
  );
}

function SentRecordCard({ item }: { item: ReplyRecord }) {
  const queryClient = useQueryClient();
  const deleteMutation = useMutation({
    mutationFn: async () =>
      createReplyDeleteRequest(item.id, {
        confirmed: true,
        reason: "运营后台手动记录删除需求",
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reply-records"] });
    },
  });

  return (
    <article className="soft-panel overflow-hidden border border-emerald-100 bg-[linear-gradient(180deg,_rgba(236,253,245,0.9),_rgba(255,255,255,0.96))] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge tone="emerald">已发送</StatusBadge>
            <ReviewMoodBadge votedUp={item.voted_up} />
          </div>
          <p className="mt-3 text-base font-semibold text-slate-950">
            {item.persona_name || "匿名玩家"}
          </p>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
            <MetaChip icon={<MessageSquareMore className="h-3.5 w-3.5" />}>
              帖子 #{item.review_id}
            </MetaChip>
            <MetaChip icon={<Clock3 className="h-3.5 w-3.5" />}>
              {formatDateTime(item.sent_at ?? item.created_at)}
            </MetaChip>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {item.review_url ? (
            <Button
              asChild
              type="button"
              variant="outline"
              className="h-10 px-4 text-sm"
            >
              <a href={item.review_url} target="_blank" rel="noreferrer">
                <ExternalLink className="h-4 w-4" aria-hidden="true" />
                打开 Steam
              </a>
            </Button>
          ) : null}
          <Button
            type="button"
            variant="outline"
            className="h-10 px-4 text-sm"
            disabled={deleteMutation.isPending || item.delete_status === "requested"}
            onClick={() => {
              if (window.confirm("确认记录这条回复的删除需求吗？不会直接调用 Steam 删除。")) {
                deleteMutation.mutate();
              }
            }}
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            {item.delete_status === "requested" ? "已记录删除需求" : "记录删除需求"}
          </Button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 xl:grid-cols-2">
        <ContentPanel
          label="评论内容"
          count={(item.review_text || "").length}
          content={item.review_text || "暂无评论内容"}
        />
        <ContentPanel
          label="已发送回复"
          count={(item.content || "").length}
          content={item.content || "暂无回复内容"}
        />
      </div>
    </article>
  );
}

function RailHeader({
  icon,
  title,
  description,
}: {
  icon: ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="border-b border-slate-100 pb-4">
      <div className="flex items-center gap-3">
        <div className="icon-tile h-10 w-10 rounded-2xl">{icon}</div>
        <div>
          <h2 className="text-base font-semibold text-slate-950">{title}</h2>
          <p className="mt-1 text-sm text-slate-500">{description}</p>
        </div>
      </div>
    </div>
  );
}

function GameRailCard({
  game,
  active,
  onClick,
}: {
  game: GameSummary;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full rounded-[24px] border px-4 py-4 text-left transition ${
        active
          ? "border-blue-200 bg-blue-50 shadow-sm shadow-blue-100/80"
          : "border-slate-200 bg-white hover:border-blue-200 hover:bg-blue-50/40"
      }`}
    >
      <p className="text-sm font-semibold text-slate-950">{game.name}</p>
      <p className="mt-1 text-xs text-slate-500">App {game.appId}</p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <MiniCount label="待审核" value={game.draftCount} tone="amber" />
        <MiniCount label="已发送" value={game.sentCount} tone="emerald" />
      </div>
      <p className="mt-3 text-xs text-slate-400">{formatDateTime(game.latestAt)}</p>
    </button>
  );
}

function DayRailCard({
  day,
  active,
  onClick,
}: {
  day: DaySummary;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full rounded-[22px] border px-4 py-3 text-left transition ${
        active
          ? "border-blue-200 bg-blue-600 text-white shadow-sm shadow-blue-200/80"
          : "border-slate-200 bg-white hover:border-blue-200 hover:bg-blue-50/40"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">{day.label}</p>
          <p className={`mt-1 text-xs ${active ? "text-white/75" : "text-slate-400"}`}>
            {formatDateTime(day.latestAt)}
          </p>
        </div>
        <span
          className={`text-lg font-semibold tabular-nums ${
            active ? "text-white" : "text-slate-400"
          }`}
        >
          {day.totalCount}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        <span
          className={`rounded-full px-2.5 py-1 ${
            active ? "bg-white/15 text-white" : "bg-amber-50 text-amber-700"
          }`}
        >
          待审核 {day.draftCount}
        </span>
        <span
          className={`rounded-full px-2.5 py-1 ${
            active ? "bg-white/15 text-white" : "bg-emerald-50 text-emerald-700"
          }`}
        >
          已发送 {day.sentCount}
        </span>
      </div>
    </button>
  );
}

function MiniCount({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "amber" | "emerald";
}) {
  const classes =
    tone === "amber"
      ? "bg-amber-50 text-amber-700"
      : "bg-emerald-50 text-emerald-700";
  return (
    <div className={`rounded-2xl px-3 py-2 text-xs ${classes}`}>
      <p>{label}</p>
      <p className="mt-1 text-sm font-semibold">{value}</p>
    </div>
  );
}

function ColumnHeader({
  eyebrow,
  title,
  description,
  count,
  tone,
}: {
  eyebrow: string;
  title: string;
  description: string;
  count: number;
  tone: "amber" | "emerald";
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-100 pb-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
          {eyebrow}
        </p>
        <h2 className="mt-2 text-xl font-semibold text-slate-950">{title}</h2>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </div>
      <StatusBadge tone={tone}>{count} 条</StatusBadge>
    </div>
  );
}

function ContentPanel({
  label,
  count,
  content,
  compact = false,
}: {
  label: string;
  count: number;
  content: string;
  compact?: boolean;
}) {
  return (
    <section
      className={`rounded-[22px] border border-slate-200 bg-white shadow-sm shadow-slate-100/80 ${
        compact ? "p-3.5" : "p-4"
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
          {label}
        </p>
        <span className="text-[11px] text-slate-400">{count} 字</span>
      </div>
      <p
        className={`whitespace-pre-wrap text-sm text-slate-700 ${
          compact ? "mt-2.5 leading-6" : "mt-3 leading-7"
        }`}
      >
        {content}
      </p>
    </section>
  );
}

function MetaChip({
  icon,
  children,
}: {
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1">
      {icon}
      {children}
    </span>
  );
}

function ReviewMoodBadge({ votedUp }: { votedUp: boolean | null | undefined }) {
  if (votedUp === true) {
    return <StatusBadge tone="emerald">好评</StatusBadge>;
  }
  if (votedUp === false) {
    return <StatusBadge tone="rose">差评</StatusBadge>;
  }
  return <StatusBadge tone="slate">未标记</StatusBadge>;
}

function StatusBadge({
  tone,
  children,
}: {
  tone: "amber" | "emerald" | "rose" | "slate";
  children: ReactNode;
}) {
  const classes: Record<typeof tone, string> = {
    amber: "border-amber-100 bg-amber-50 text-amber-700",
    emerald: "border-emerald-100 bg-emerald-50 text-emerald-700",
    rose: "border-rose-100 bg-rose-50 text-rose-700",
    slate: "border-slate-200 bg-slate-100 text-slate-600",
  };

  return (
    <span
      className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${classes[tone]}`}
    >
      {children}
    </span>
  );
}

function EmptyState({
  text,
  compact = false,
}: {
  text: string;
  compact?: boolean;
}) {
  return (
    <div
      className={`rounded-[24px] border border-dashed border-slate-200 bg-slate-50/70 text-center text-sm text-slate-500 ${
        compact ? "p-5" : "p-8"
      }`}
    >
      {text}
    </div>
  );
}

function buildGameSummaries(
  drafts: ReplyDraftAuditItem[],
  records: ReplyRecord[],
  games: GameListItem[],
): GameSummary[] {
  const nameMap = new Map(
    games.map((game) => [game.app_id, game.name?.trim() || `App ${game.app_id}`]),
  );
  const summaries = new Map<number, GameSummary>();

  for (const draft of drafts) {
    upsertGameSummary(summaries, draft.app_id, draft.game_name, nameMap, {
      draftCount: 1,
      sentCount: 0,
      timestamp: getDraftTimestamp(draft),
    });
  }

  for (const record of records) {
    if (!record.app_id) {
      continue;
    }
    upsertGameSummary(summaries, record.app_id, record.game_name ?? null, nameMap, {
      draftCount: 0,
      sentCount: 1,
      timestamp: getRecordTimestamp(record),
    });
  }

  return [...summaries.values()].sort((left, right) =>
    compareTimestamps(right.latestAt, left.latestAt),
  );
}

function buildDaySummaries(
  appId: number | null,
  drafts: ReplyDraftAuditItem[],
  records: ReplyRecord[],
): DaySummary[] {
  if (appId === null) {
    return [];
  }

  const summaries = new Map<string, DaySummary>();

  for (const draft of drafts) {
    if (draft.app_id !== appId) {
      continue;
    }
    const dayKey = getDraftDayKey(draft);
    upsertDaySummary(summaries, dayKey, {
      draftCount: 1,
      sentCount: 0,
      timestamp: getDraftTimestamp(draft),
    });
  }

  for (const record of records) {
    if ((record.app_id ?? 0) !== appId) {
      continue;
    }
    const dayKey = getRecordDayKey(record);
    upsertDaySummary(summaries, dayKey, {
      draftCount: 0,
      sentCount: 1,
      timestamp: getRecordTimestamp(record),
    });
  }

  return [...summaries.values()].sort((left, right) =>
    compareTimestamps(right.latestAt, left.latestAt),
  );
}

function upsertGameSummary(
  summaries: Map<number, GameSummary>,
  appId: number,
  gameName: string | null,
  nameMap: Map<number, string>,
  delta: { draftCount: number; sentCount: number; timestamp: string | null },
) {
  const existing = summaries.get(appId);
  const resolvedName = (gameName?.trim() || nameMap.get(appId) || `App ${appId}`).trim();
  if (!existing) {
    summaries.set(appId, {
      appId,
      name: resolvedName,
      draftCount: delta.draftCount,
      sentCount: delta.sentCount,
      totalCount: delta.draftCount + delta.sentCount,
      latestAt: delta.timestamp,
    });
    return;
  }

  summaries.set(appId, {
    ...existing,
    draftCount: existing.draftCount + delta.draftCount,
    sentCount: existing.sentCount + delta.sentCount,
    totalCount: existing.totalCount + delta.draftCount + delta.sentCount,
    latestAt:
      compareTimestamps(existing.latestAt, delta.timestamp) >= 0
        ? existing.latestAt
        : delta.timestamp,
  });
}

function upsertDaySummary(
  summaries: Map<string, DaySummary>,
  dayKey: string,
  delta: { draftCount: number; sentCount: number; timestamp: string | null },
) {
  const existing = summaries.get(dayKey);
  if (!existing) {
    summaries.set(dayKey, {
      dayKey,
      label: formatDayLabel(dayKey),
      draftCount: delta.draftCount,
      sentCount: delta.sentCount,
      totalCount: delta.draftCount + delta.sentCount,
      latestAt: delta.timestamp,
    });
    return;
  }

  summaries.set(dayKey, {
    ...existing,
    draftCount: existing.draftCount + delta.draftCount,
    sentCount: existing.sentCount + delta.sentCount,
    totalCount: existing.totalCount + delta.draftCount + delta.sentCount,
    latestAt:
      compareTimestamps(existing.latestAt, delta.timestamp) >= 0
        ? existing.latestAt
        : delta.timestamp,
  });
}

function getDraftTimestamp(item: ReplyDraftAuditItem) {
  return item.timestamp_created ?? item.created_at;
}

function getRecordTimestamp(item: ReplyRecord) {
  return item.timestamp_created ?? item.sent_at ?? item.created_at;
}

function getDraftDayKey(item: ReplyDraftAuditItem) {
  return toDayKey(getDraftTimestamp(item));
}

function getRecordDayKey(item: ReplyRecord) {
  return toDayKey(getRecordTimestamp(item));
}

function toDayKey(value: string | null | undefined) {
  if (!value) {
    return "unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "unknown";
  }
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function compareTimestamps(
  left: string | null | undefined,
  right: string | null | undefined,
) {
  const leftTime = left ? new Date(left).getTime() : 0;
  const rightTime = right ? new Date(right).getTime() : 0;
  return leftTime - rightTime;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "未知时间";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "未知时间";
  }
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDayLabel(dayKey: string) {
  if (dayKey === "unknown") {
    return "未知日期";
  }
  const [year, month, day] = dayKey.split("-");
  return `${year}/${Number(month)}/${Number(day)}`;
}

function getDraftStatusLabel(status: string) {
  if (status === "generation_failed") {
    return "生成失败";
  }
  if (status === "send_failed") {
    return "发送失败";
  }
  return "待审核";
}

export const replyRecordsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/reply-records",
  component: ReplyRecordsPage,
});
