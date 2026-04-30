import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import { Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { createReplyDeleteRequest, fetchReplyRecords, type ReplyRecord } from "@/lib/api";
import { rootRoute } from "@/routes/__root";

function ReplyRecordsPage() {
  const queryClient = useQueryClient();
  const recordsQuery = useQuery({ queryKey: ["reply-records"], queryFn: fetchReplyRecords });
  const deleteMutation = useMutation({
    mutationFn: (recordId: number) =>
      createReplyDeleteRequest(recordId, {
        confirmed: true,
        reason: "运营后台手动标记删除需求"
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reply-records"] });
    }
  });

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:py-8 xl:px-8">
      <section className="rounded-[2rem] border border-white/80 bg-white/90 p-6 shadow-xl shadow-slate-200/70">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-600 text-white">
            <Send className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-slate-950">已发送回复</h1>
            <p className="mt-1 text-sm text-slate-500">查看 Steam 开发者回复发送记录，删除诉求只记录不调用 Steam。</p>
          </div>
        </div>
      </section>

      <section className="mt-6 grid gap-4">
        {(recordsQuery.data ?? []).map((record) => (
          <ReplyRecordCard
            key={record.id}
            record={record}
            deleting={deleteMutation.isPending}
            onDeleteRequest={() => {
              if (window.confirm("确认记录这条回复的删除需求？不会实际调用 Steam 删除。")) {
                deleteMutation.mutate(record.id);
              }
            }}
          />
        ))}
        {!recordsQuery.isLoading && (recordsQuery.data ?? []).length === 0 ? (
          <div className="rounded-[2rem] border border-dashed border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
            暂无已发送回复记录。
          </div>
        ) : null}
      </section>
    </main>
  );
}

function ReplyRecordCard({
  record,
  deleting,
  onDeleteRequest
}: {
  record: ReplyRecord;
  deleting: boolean;
  onDeleteRequest: () => void;
}) {
  return (
    <article className="rounded-[2rem] border border-white/80 bg-white p-5 shadow-lg shadow-slate-200/60">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-950">
            #{record.id} · {record.persona_name ?? record.recommendation_id}
          </p>
          <p className="mt-1 text-xs text-slate-500">状态 {record.status} · 删除需求 {record.delete_status}</p>
        </div>
        <Button
          type="button"
          variant="outline"
          disabled={deleting || record.delete_status === "requested"}
          onClick={onDeleteRequest}
        >
          记录删除需求
        </Button>
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div className="rounded-3xl bg-slate-50 p-4">
          <p className="text-xs font-semibold text-slate-500">原评论</p>
          <p className="mt-2 text-sm leading-7 text-slate-700">{record.review_text || "-"}</p>
        </div>
        <div className="rounded-3xl bg-sky-50 p-4">
          <p className="text-xs font-semibold text-sky-700">开发者回复</p>
          <p className="mt-2 text-sm leading-7 text-slate-800">{record.content}</p>
        </div>
      </div>
    </article>
  );
}

export const replyRecordsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/reply-records",
  component: ReplyRecordsPage
});
