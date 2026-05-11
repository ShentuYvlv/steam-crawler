import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import { CheckCircle2, Clock3, MessageSquareMore, RefreshCcw, ShieldCheck, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

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
    () => buildGameSummaries(auditQueueQuery.data ?? [], recordsQuery.data ?? [], gamesQuery.data ?? []),
    [auditQueueQuery.data, recordsQuery.data, gamesQuery.data],
  );

  useEffect(() => {
    if (gameSummaries.length === 0) {
      setSelectedAppId(null);
      return;
    }
    if (selectedAppId === null || !gameSummaries.some((game) => game.appId === selectedAppId)) {
      setSelectedAppId(gameSummaries[0].appId);
    }
  }, [gameSummaries, selectedAppId]);

  const daySummaries = useMemo(
    () => buildDaySummaries(selectedAppId, auditQueueQuery.data ?? [], recordsQuery.data ?? []),
    [selectedAppId, auditQueueQuery.data, recordsQuery.data],
  );

  useEffect(() => {
    if (daySummaries.length === 0) {
      setSelectedDayKey(null);
      return;
    }
    if (selectedDayKey === null || !daySummaries.some((day) => day.dayKey === selectedDayKey)) {
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
          item.app_id === selectedAppId &&
          getDraftDayKey(item) === selectedDayKey,
      )
      .sort((left, right) => compareTimestamps(getDraftTimestamp(right), getDraftTimestamp(left)));
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
      .sort((left, right) => compareTimestamps(getRecordTimestamp(right), getRecordTimestamp(left)));
  }, [recordsQuery.data, selectedAppId, selectedDayKey]);

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.08),_transparent_28%),linear-gradient(180deg,_#f8fbff_0%,_#f4f7fb_100%)] px-4 py-5 sm:px-6 lg:py-8 xl:px-8">
      <section className="rounded-[32px] bg-white/78 p-6 shadow-[0_20px_60px_rgba(15,23,42,0.06)] backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="icon-tile">
            <ShieldCheck className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-slate-950">回复审核与记录</h1>
            <p className="mt-1 text-sm text-slate-500">
              先选游戏，再按日期切换当天评论。左侧看待审核草稿，右侧看当天已经发送的回复记录。
            </p>
          </div>
        </div>
      </section>

      <section className="mt-6 grid gap-5 xl:grid-cols-[240px_220px_minmax(0,1fr)_minmax(0,1fr)]">
        <aside className="flex min-h-[720px] flex-col rounded-[28px] bg-white/72 p-4 shadow-[0_20px_50px_rgba(15,23,42,0.05)] backdrop-blur">
          <div className="px-2 pb-3">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">游戏</p>
            <p className="mt-2 text-sm text-slate-500">按游戏聚合查看草稿和已发送记录。</p>
          </div>
          <div className="mt-4 flex-1 space-y-3 overflow-y-auto pr-1">
            {gameSummaries.map((game) => {
              const active = game.appId === selectedAppId;
              return (
                <button
                  key={game.appId}
                  type="button"
                  onClick={() => setSelectedAppId(game.appId)}
                  className={`w-full rounded-[24px] px-4 py-4 text-left transition duration-200 ${
                    active
                      ? "bg-[linear-gradient(180deg,_rgba(239,246,255,0.96),_rgba(230,240,255,0.88))] shadow-[0_16px_36px_rgba(37,99,235,0.12)]"
                      : "bg-white/78 shadow-[0_10px_28px_rgba(15,23,42,0.05)] hover:bg-white hover:shadow-[0_14px_34px_rgba(15,23,42,0.08)]"
                  }`}
                >
                  <p className="text-sm font-semibold text-slate-900">{game.name}</p>
                  <p className="mt-1 text-xs text-slate-500">App {game.appId}</p>
                  <div className="mt-3 space-y-1 text-xs text-slate-500">
                    <p>待审核 {game.draftCount} 条</p>
                    <p>已发送 {game.sentCount} 条</p>
                    <p>{formatDateTime(game.latestAt)}</p>
                  </div>
                </button>
              );
            })}
            {!gamesQuery.isLoading && gameSummaries.length === 0 ? (
              <EmptyState text="暂无可查看的回复记录。" compact />
            ) : null}
          </div>
        </aside>

        <aside className="flex min-h-[720px] flex-col rounded-[28px] bg-white/72 p-4 shadow-[0_20px_50px_rgba(15,23,42,0.05)] backdrop-blur">
          <div className="px-2 pb-3">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">时间</p>
            <p className="mt-2 text-sm text-slate-500">同一游戏按日期筛选，当天帖子和回复在右侧显示。</p>
          </div>
          <div className="mt-4 flex-1 space-y-3 overflow-y-auto pr-1">
            {daySummaries.map((day) => {
              const active = day.dayKey === selectedDayKey;
              return (
                <button
                  key={day.dayKey}
                  type="button"
                  onClick={() => setSelectedDayKey(day.dayKey)}
                  className={`w-full rounded-[24px] px-4 py-4 text-left transition duration-200 ${
                    active
                      ? "bg-[linear-gradient(180deg,_rgba(239,246,255,0.96),_rgba(230,240,255,0.88))] shadow-[0_16px_36px_rgba(37,99,235,0.12)]"
                      : "bg-white/78 shadow-[0_10px_28px_rgba(15,23,42,0.05)] hover:bg-white hover:shadow-[0_14px_34px_rgba(15,23,42,0.08)]"
                  }`}
                >
                  <p className="text-sm font-semibold text-slate-900">{day.label}</p>
                  <div className="mt-3 space-y-1 text-xs text-slate-500">
                    <p>当天共 {day.totalCount} 条</p>
                    <p>待审核 {day.draftCount} 条</p>
                    <p>已发送 {day.sentCount} 条</p>
                  </div>
                </button>
              );
            })}
            {!auditQueueQuery.isLoading && !recordsQuery.isLoading && daySummaries.length === 0 ? (
              <EmptyState text="当前游戏暂无可筛选的日期。" compact />
            ) : null}
          </div>
        </aside>

        <section className="flex min-h-[720px] flex-col rounded-[32px] bg-white/82 p-5 shadow-[0_24px_60px_rgba(15,23,42,0.06)] backdrop-blur">
          <ColumnHeader
            eyebrow="待审核草稿"
            title={selectedGame ? `${selectedGame.name} · ${selectedDay?.label ?? "请选择日期"}` : "待审核草稿"}
            description="每条评论上方显示评论内容，下方直接编辑回复草稿。"
            count={selectedDrafts.length}
          />
          <div className="mt-5 flex-1 space-y-4 overflow-y-auto pr-1">
            {selectedDrafts.map((item) => (
              <DraftCard key={item.id} item={item} />
            ))}
            {!auditQueueQuery.isLoading && selectedGame && selectedDay && selectedDrafts.length === 0 ? (
              <EmptyState text="这一天没有待审核草稿。" />
            ) : null}
            {!selectedGame ? (
              <EmptyState text="先选择一个游戏。" />
            ) : null}
            {selectedGame && !selectedDay ? (
              <EmptyState text="先在中间选择一个日期。" />
            ) : null}
          </div>
        </section>

        <section className="flex min-h-[720px] flex-col rounded-[32px] bg-white/82 p-5 shadow-[0_24px_60px_rgba(15,23,42,0.06)] backdrop-blur">
          <ColumnHeader
            eyebrow="已发送评论"
            title={selectedGame ? `${selectedGame.name} · ${selectedDay?.label ?? "请选择日期"}` : "已发送评论"}
            description="显示所选游戏在该日期已经发送到 Steam 的评论回复。"
            count={selectedSentRecords.length}
          />
          <div className="mt-5 flex-1 space-y-4 overflow-y-auto pr-1">
            {selectedSentRecords.map((item) => (
              <SentRecordCard key={item.id} item={item} />
            ))}
            {!recordsQuery.isLoading && selectedGame && selectedDay && selectedSentRecords.length === 0 ? (
              <EmptyState text="这一天还没有已发送评论。" />
            ) : null}
            {!selectedGame ? (
              <EmptyState text="先选择一个游戏。" />
            ) : null}
            {selectedGame && !selectedDay ? (
              <EmptyState text="先在中间选择一个日期。" />
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
    <article className="rounded-[26px] bg-[linear-gradient(180deg,_rgba(248,250,252,0.95),_rgba(241,245,249,0.88))] p-4 shadow-[0_14px_34px_rgba(15,23,42,0.06)]">
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-slate-900">{item.persona_name || "匿名玩家"}</p>
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1 rounded-full bg-white/90 px-3 py-1">
                <MessageSquareMore className="h-3.5 w-3.5" />
                帖子 #{item.review_id}
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-white/90 px-3 py-1">
                <Clock3 className="h-3.5 w-3.5" />
                {formatDateTime(item.timestamp_created ?? item.created_at)}
              </span>
              <span className="badge-orange px-3">{getDraftStatusLabel(item.status)}</span>
            </div>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              className="h-10 px-4 text-sm"
              disabled={saveMutation.isPending || draftText.trim().length === 0}
              onClick={() => saveMutation.mutate()}
            >
              保存
            </Button>
            <Button
              type="button"
              variant="secondary"
              className="h-10 px-4 text-sm"
              disabled={regenerateMutation.isPending}
              onClick={() => regenerateMutation.mutate()}
            >
              <RefreshCcw className="h-4 w-4" aria-hidden="true" />
              {regenerateMutation.isPending ? "生成中" : "重生成"}
            </Button>
            <Button
              type="button"
              variant="outline"
              className="h-10 px-4 text-sm"
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
              className="h-10 px-4 text-sm"
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
        </div>

        {item.error_message ? (
          <div className="rounded-[18px] bg-rose-50/90 px-4 py-3 text-sm text-rose-700 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
            生成失败：{item.error_message}
          </div>
        ) : null}

        {sendMutation.isError ? (
          <div className="rounded-[18px] bg-rose-50/90 px-4 py-3 text-sm text-rose-700 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
            {(sendMutation.error as Error).message}
          </div>
        ) : null}
      </div>

      <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(0,0.82fr)_minmax(0,1.18fr)]">
        <section className="rounded-[22px] bg-white/92 p-4 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">评论内容</p>
            <span className="text-[11px] text-slate-400">{(item.review_text || "").length} 字</span>
          </div>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">
            {item.review_text || "暂无评论内容"}
          </p>
        </section>

        <section className="rounded-[22px] bg-white/92 p-4 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">回复草稿</p>
            <span className="text-[11px] text-slate-400">{draftText.trim().length} 字</span>
          </div>
          <textarea
            className="mt-3 min-h-[168px] w-full resize-y rounded-[16px] border border-slate-200 bg-slate-50/60 px-4 py-3 text-sm leading-7 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-200 focus:bg-white focus:ring-4 focus:ring-blue-100"
            value={draftText}
            onChange={(event) => setDraftText(event.target.value)}
          />
        </section>
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
    <article className="rounded-[26px] bg-[linear-gradient(180deg,_rgba(240,253,244,0.92),_rgba(248,250,252,0.9))] p-4 shadow-[0_14px_34px_rgba(15,23,42,0.06)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">{item.persona_name || "匿名玩家"}</p>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1 rounded-full bg-white/90 px-3 py-1">
              <MessageSquareMore className="h-3.5 w-3.5" />
              帖子 #{item.review_id}
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-white/90 px-3 py-1">
              <Clock3 className="h-3.5 w-3.5" />
              {formatDateTime(item.sent_at ?? item.created_at)}
            </span>
            <span className="badge-green px-3">已发送</span>
          </div>
        </div>
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

      <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(0,0.82fr)_minmax(0,1.18fr)]">
        <section className="rounded-[22px] bg-white/92 p-4 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">评论内容</p>
            <span className="text-[11px] text-slate-400">{(item.review_text || "").length} 字</span>
          </div>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">
            {item.review_text || "暂无评论内容"}
          </p>
        </section>

        <section className="rounded-[22px] bg-white/92 p-4 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">已发送回复</p>
            <span className="text-[11px] text-slate-400">{(item.content || "").length} 字</span>
          </div>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-800">
            {item.content || "暂无回复内容"}
          </p>
        </section>
      </div>
    </article>
  );
}

function ColumnHeader({
  eyebrow,
  title,
  description,
  count,
}: {
  eyebrow: string;
  title: string;
  description: string;
  count: number;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 pb-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">{eyebrow}</p>
        <h2 className="mt-2 text-lg font-semibold text-slate-950">{title}</h2>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </div>
      <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
        {count} 条
      </span>
    </div>
  );
}

function EmptyState({ text, compact = false }: { text: string; compact?: boolean }) {
  return (
    <div
      className={`rounded-[24px] bg-white/82 text-center text-sm text-slate-500 shadow-[0_12px_30px_rgba(15,23,42,0.05)] ${
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
  const nameMap = new Map(games.map((game) => [game.app_id, game.name?.trim() || `App ${game.app_id}`]));
  const summaries = new Map<number, GameSummary>();

  for (const draft of drafts) {
    upsertGameSummary(
      summaries,
      draft.app_id,
      draft.game_name,
      nameMap,
      { draftCount: 1, sentCount: 0, timestamp: getDraftTimestamp(draft) },
    );
  }

  for (const record of records) {
    if (!record.app_id) {
      continue;
    }
    upsertGameSummary(
      summaries,
      record.app_id,
      record.game_name ?? null,
      nameMap,
      { draftCount: 0, sentCount: 1, timestamp: getRecordTimestamp(record) },
    );
  }

  return [...summaries.values()].sort((left, right) => compareTimestamps(right.latestAt, left.latestAt));
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

  return [...summaries.values()].sort((left, right) => compareTimestamps(right.latestAt, left.latestAt));
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
    latestAt: compareTimestamps(existing.latestAt, delta.timestamp) >= 0 ? existing.latestAt : delta.timestamp,
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
    latestAt: compareTimestamps(existing.latestAt, delta.timestamp) >= 0 ? existing.latestAt : delta.timestamp,
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

function compareTimestamps(left: string | null | undefined, right: string | null | undefined) {
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
