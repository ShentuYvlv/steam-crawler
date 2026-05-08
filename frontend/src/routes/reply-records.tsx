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
  type ReplyDraftAuditItem,
  type ReplyRecord
} from "@/lib/api";
import { rootRoute } from "@/routes/__root";

type WorkspaceItem =
  | {
      key: string;
      kind: "draft";
      app_id: number;
      game_name: string | null;
      timestamp: string | null;
      persona_name: string | null;
      review_text: string;
      reply_content: string;
      status: string;
      title: string;
      subtitle: string;
      draft: ReplyDraftAuditItem;
    }
  | {
      key: string;
      kind: "record";
      app_id: number;
      game_name: string | null;
      timestamp: string | null;
      persona_name: string | null;
      review_text: string;
      reply_content: string;
      status: string;
      title: string;
      subtitle: string;
      record: ReplyRecord;
    };

function ReplyRecordsPage() {
  const queryClient = useQueryClient();
  const [selectedAppId, setSelectedAppId] = useState<number | null>(null);
  const [selectedItemKey, setSelectedItemKey] = useState<string | null>(null);

  const gamesQuery = useQuery({ queryKey: ["games"], queryFn: fetchGames });
  const auditQueueQuery = useQuery({
    queryKey: ["reply-audit-queue"],
    queryFn: () => fetchReplyAuditQueue(null)
  });
  const recordsQuery = useQuery({
    queryKey: ["reply-records"],
    queryFn: () => fetchReplyRecords()
  });

  const allItems = useMemo<WorkspaceItem[]>(() => {
    const draftItems: WorkspaceItem[] = (auditQueueQuery.data ?? []).map((item) => ({
      key: `draft-${item.id}`,
      kind: "draft",
      app_id: item.app_id,
      game_name: item.game_name,
      timestamp: item.timestamp_created,
      persona_name: item.persona_name,
      review_text: item.review_text,
      reply_content: item.content ?? "",
      status: item.status,
      title: `草稿 #${item.id}`,
      subtitle: `帖子 #${item.review_id}`,
      draft: item
    }));

    const recordItems: WorkspaceItem[] = (recordsQuery.data ?? []).map((record) => ({
      key: `record-${record.id}`,
      kind: "record",
      app_id: record.app_id ?? 0,
      game_name: record.game_name ?? null,
      timestamp: record.timestamp_created ?? record.sent_at ?? record.created_at,
      persona_name: record.persona_name ?? null,
      review_text: record.review_text ?? "",
      reply_content: record.content,
      status: record.status,
      title: `回复记录 #${record.id}`,
      subtitle: `帖子 #${record.review_id}`,
      record
    }));

    return [...draftItems, ...recordItems].sort((left, right) => {
      const leftTime = left.timestamp ? new Date(left.timestamp).getTime() : 0;
      const rightTime = right.timestamp ? new Date(right.timestamp).getTime() : 0;
      return rightTime - leftTime;
    });
  }, [auditQueueQuery.data, recordsQuery.data]);

  const games = useMemo(() => {
    const counts = new Map<number, { count: number; latestAt: string | null; name: string | null }>();
    for (const item of allItems) {
      if (!item.app_id) continue;
      const current = counts.get(item.app_id);
      if (!current) {
        counts.set(item.app_id, {
          count: 1,
          latestAt: item.timestamp,
          name: item.game_name
        });
        continue;
      }
      counts.set(item.app_id, {
        count: current.count + 1,
        latestAt: current.latestAt && item.timestamp
          ? new Date(current.latestAt).getTime() > new Date(item.timestamp).getTime()
            ? current.latestAt
            : item.timestamp
          : current.latestAt ?? item.timestamp,
        name: current.name ?? item.game_name
      });
    }

    return Array.from(counts.entries())
      .map(([appId, summary]) => {
        const game = (gamesQuery.data ?? []).find((entry) => entry.app_id === appId);
        return {
          app_id: appId,
          name: summary.name ?? game?.name ?? `App ${appId}`,
          count: summary.count,
          latestAt: summary.latestAt
        };
      })
      .sort((left, right) => left.name.localeCompare(right.name, "zh-CN"));
  }, [allItems, gamesQuery.data]);

  useEffect(() => {
    if (!games.length) {
      setSelectedAppId(null);
      return;
    }
    if (selectedAppId === null || !games.some((game) => game.app_id === selectedAppId)) {
      setSelectedAppId(games[0].app_id);
    }
  }, [games, selectedAppId]);

  const gameItems = useMemo(
    () => allItems.filter((item) => item.app_id === selectedAppId),
    [allItems, selectedAppId]
  );

  useEffect(() => {
    if (!gameItems.length) {
      setSelectedItemKey(null);
      return;
    }
    if (!selectedItemKey || !gameItems.some((item) => item.key === selectedItemKey)) {
      setSelectedItemKey(gameItems[0].key);
    }
  }, [gameItems, selectedItemKey]);

  const selectedItem = useMemo(
    () => gameItems.find((item) => item.key === selectedItemKey) ?? null,
    [gameItems, selectedItemKey]
  );

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
              先按游戏选择，再按时间切换具体回复记录，在右侧完成审核、发送和查看已发送内容。
            </p>
          </div>
        </div>
      </section>

      <section className="mt-6 grid gap-5 xl:grid-cols-[240px_240px_minmax(0,1fr)_minmax(0,1fr)]">
        <aside className="flex min-h-[720px] flex-col rounded-[28px] bg-white/72 p-4 shadow-[0_20px_50px_rgba(15,23,42,0.05)] backdrop-blur">
          <div className="px-2 pb-3">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">游戏</p>
            <p className="mt-2 text-sm text-slate-500">按游戏聚合查看回复任务。</p>
          </div>
          <div className="mt-4 flex-1 space-y-3 overflow-y-auto pr-1">
            {games.map((game) => {
              const active = game.app_id === selectedAppId;
              return (
                <button
                  key={game.app_id}
                  type="button"
                  onClick={() => setSelectedAppId(game.app_id)}
                  className={`w-full rounded-[24px] px-4 py-4 text-left transition duration-200 ${
                    active
                      ? "bg-[linear-gradient(180deg,_rgba(239,246,255,0.96),_rgba(230,240,255,0.88))] shadow-[0_16px_36px_rgba(37,99,235,0.12)]"
                      : "bg-white/78 shadow-[0_10px_28px_rgba(15,23,42,0.05)] hover:bg-white hover:shadow-[0_14px_34px_rgba(15,23,42,0.08)]"
                  }`}
                >
                  <p className="text-sm font-semibold text-slate-900">{game.name}</p>
                  <p className="mt-1 text-xs text-slate-500">App {game.app_id}</p>
                  <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                    <span>{game.count} 条</span>
                    <span>{formatDateTime(game.latestAt)}</span>
                  </div>
                </button>
              );
            })}
            {!gamesQuery.isLoading && games.length === 0 ? <EmptyState text="暂无可查看的回复记录。" compact /> : null}
          </div>
        </aside>

        <aside className="flex min-h-[720px] flex-col rounded-[28px] bg-white/72 p-4 shadow-[0_20px_50px_rgba(15,23,42,0.05)] backdrop-blur">
          <div className="px-2 pb-3">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">时间</p>
            <p className="mt-2 text-sm text-slate-500">同一游戏下按时间切换不同回复条目。</p>
          </div>
          <div className="mt-4 flex-1 space-y-3 overflow-y-auto pr-1">
            {gameItems.map((item) => {
              const active = item.key === selectedItemKey;
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setSelectedItemKey(item.key)}
                  className={`w-full rounded-[24px] px-4 py-4 text-left transition duration-200 ${
                    active
                      ? "bg-[linear-gradient(180deg,_rgba(239,246,255,0.96),_rgba(230,240,255,0.88))] shadow-[0_16px_36px_rgba(37,99,235,0.12)]"
                      : "bg-white/78 shadow-[0_10px_28px_rgba(15,23,42,0.05)] hover:bg-white hover:shadow-[0_14px_34px_rgba(15,23,42,0.08)]"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-semibold text-slate-900">{formatDateTime(item.timestamp)}</p>
                    <span className={item.kind === "draft" ? "badge-orange px-2" : "badge-green px-2"}>
                      {item.kind === "draft" ? "待审核" : "已发送"}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-slate-500">{item.subtitle}</p>
                  <p className="mt-3 line-clamp-2 text-xs leading-6 text-slate-600">{item.reply_content || "暂无回复内容"}</p>
                </button>
              );
            })}
            {!auditQueueQuery.isLoading && !recordsQuery.isLoading && gameItems.length === 0 ? (
              <EmptyState text="当前游戏暂无回复记录。" compact />
            ) : null}
          </div>
        </aside>

        <section className="min-h-[720px] rounded-[32px] bg-white/82 p-6 shadow-[0_24px_60px_rgba(15,23,42,0.06)] backdrop-blur">
          <ReplyContentPane item={selectedItem} />
        </section>

        <section className="min-h-[720px] rounded-[32px] bg-white/82 p-6 shadow-[0_24px_60px_rgba(15,23,42,0.06)] backdrop-blur">
          <CommentContentPane item={selectedItem} />
        </section>
      </section>
    </main>
  );
}

function ReplyContentPane({ item }: { item: WorkspaceItem | null }) {
  const queryClient = useQueryClient();
  const [draftText, setDraftText] = useState("");

  useEffect(() => {
    setDraftText(item?.reply_content ?? "");
  }, [item]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!item || item.kind !== "draft") return null;
      return updateReplyDraft(item.draft.id, { content: draftText });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reply-audit-queue"] });
    }
  });

  const regenerateMutation = useMutation({
    mutationFn: async () => {
      if (!item || item.kind !== "draft") return null;
      return regenerateReplyDraft(item.draft.review_id);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reply-audit-queue"] });
      void queryClient.invalidateQueries({ queryKey: ["reviews"] });
    }
  });

  const sendMutation = useMutation({
    mutationFn: async () => {
      if (!item || item.kind !== "draft") return null;
      return sendReviewReply(item.draft.review_id, {
        draft_id: item.draft.id,
        content: draftText,
        confirmed: true
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reply-audit-queue"] });
      void queryClient.invalidateQueries({ queryKey: ["reply-records"] });
      void queryClient.invalidateQueries({ queryKey: ["reviews"] });
    }
  });
  const rejectMutation = useMutation({
    mutationFn: async () => {
      if (!item || item.kind !== "draft") return null;
      return updateReplyDraft(item.draft.id, { status: "rejected" });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reply-audit-queue"] });
      void queryClient.invalidateQueries({ queryKey: ["reviews"] });
      void queryClient.invalidateQueries({ queryKey: ["review"] });
    }
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!item || item.kind !== "record") return null;
      return createReplyDeleteRequest(item.record.id, {
        confirmed: true,
        reason: "运营后台手动标记删除需求"
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reply-records"] });
    }
  });

  if (!item) {
    return <EmptyDetail title="回复内容" description="先在左侧选择游戏，再在时间栏选择一条回复记录。" />;
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-4 pb-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">回复内容</p>
          <h2 className="mt-3 text-xl font-semibold text-slate-950">{item.title}</h2>
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1">
              <Clock3 className="h-3.5 w-3.5" />
              {formatDateTime(item.timestamp)}
            </span>
            <span className={item.kind === "draft" ? "badge-orange px-3" : "badge-green px-3"}>
              {item.kind === "draft" ? "待审核草稿" : "已发送记录"}
            </span>
          </div>
        </div>
        {item.kind === "draft" ? (
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={saveMutation.isPending || draftText.trim().length === 0}
              onClick={() => saveMutation.mutate()}
            >
              保存修改
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={regenerateMutation.isPending}
              onClick={() => regenerateMutation.mutate()}
            >
              <RefreshCcw className="h-4 w-4" aria-hidden="true" />
              {regenerateMutation.isPending ? "生成中..." : "重新生成"}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={rejectMutation.isPending}
              onClick={() => {
                if (window.confirm("确认驳回这条草稿？驳回后会从审核队列移除。")) {
                  rejectMutation.mutate();
                }
              }}
            >
              {rejectMutation.isPending ? "驳回中..." : "驳回草稿"}
            </Button>
            <Button
              type="button"
              disabled={sendMutation.isPending || draftText.trim().length === 0}
              onClick={() => {
                if (window.confirm("确认审核通过并发送这条回复到 Steam？")) {
                  sendMutation.mutate();
                }
              }}
            >
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              {sendMutation.isPending ? "发送中..." : "通过并发送"}
            </Button>
          </div>
        ) : (
          <Button
            type="button"
            variant="outline"
            disabled={deleteMutation.isPending || item.record.delete_status === "requested"}
            onClick={() => {
              if (window.confirm("确认记录这条回复的删除需求？不会实际调用 Steam 删除。")) {
                deleteMutation.mutate();
              }
            }}
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            {item.record.delete_status === "requested" ? "已记录删除需求" : "记录删除需求"}
          </Button>
        )}
      </div>

      {item.kind === "draft" && item.draft.error_message ? (
        <div className="mt-4 rounded-[24px] bg-rose-50/90 p-4 text-sm text-rose-700 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]">
          生成失败：{item.draft.error_message}
        </div>
      ) : null}

      <div className="mt-5 flex-1 rounded-[30px] bg-[linear-gradient(180deg,_rgba(239,246,255,0.88),_rgba(248,250,252,0.92))] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
        {item.kind === "draft" ? (
          <textarea
            className="h-full min-h-[540px] w-full resize-none rounded-[24px] bg-white/92 px-4 py-4 text-sm leading-7 text-slate-900 outline-none shadow-[0_12px_32px_rgba(15,23,42,0.06)] transition placeholder:text-slate-400 focus:bg-white focus:ring-4 focus:ring-blue-100"
            value={draftText}
            onChange={(event) => setDraftText(event.target.value)}
          />
        ) : (
          <div className="h-full min-h-[540px] whitespace-pre-wrap rounded-[24px] bg-white/92 p-4 text-sm leading-7 text-slate-800 shadow-[0_12px_32px_rgba(15,23,42,0.06)]">
            {item.reply_content || "暂无回复内容"}
          </div>
        )}
      </div>
    </div>
  );
}

function CommentContentPane({ item }: { item: WorkspaceItem | null }) {
  if (!item) {
    return <EmptyDetail title="评论内容" description="选择一条时间记录后，这里显示对应的玩家评论正文。" />;
  }

  return (
    <div className="flex h-full flex-col">
      <div className="pb-4">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">评论内容</p>
        <h2 className="mt-3 text-xl font-semibold text-slate-950">{item.persona_name || "匿名玩家"}</h2>
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1">
            <MessageSquareMore className="h-3.5 w-3.5" />
            {item.subtitle}
          </span>
          <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1">
            App {item.app_id}
          </span>
        </div>
      </div>
      <div className="mt-5 flex-1 rounded-[30px] bg-[linear-gradient(180deg,_rgba(248,250,252,0.95),_rgba(241,245,249,0.9))] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)]">
        <div className="h-full min-h-[540px] whitespace-pre-wrap rounded-[24px] bg-white/92 p-4 text-sm leading-7 text-slate-700 shadow-[0_12px_32px_rgba(15,23,42,0.05)]">
          {item.review_text || "暂无评论内容"}
        </div>
      </div>
    </div>
  );
}

function EmptyDetail({ title, description }: { title: string; description: string }) {
  return (
    <div className="flex h-full min-h-[720px] items-center justify-center rounded-[30px] bg-[linear-gradient(180deg,_rgba(248,250,252,0.9),_rgba(241,245,249,0.8))] p-8 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.9)]">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">{title}</p>
        <p className="mt-3 text-sm leading-7 text-slate-500">{description}</p>
      </div>
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

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "未知时间";
  }
  return new Date(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

export const replyRecordsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/reply-records",
  component: ReplyRecordsPage
});
