import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Inbox,
  MessageSquareText,
  RefreshCcw,
  Search,
  SlidersHorizontal,
  Sparkles,
  ThumbsUp,
  UserRound,
  X
} from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  bulkUpdateReviewStatus,
  fetchReviewDetail,
  fetchReviews,
  updateReviewStatus,
  type ReviewDetail,
  type ReviewListItem,
  type ReviewQuery
} from "@/lib/api";
import { rootRoute } from "@/routes/__root";

const defaultFilters: ReviewQuery = {
  app_id: "3350200",
  voted_up: "",
  min_votes_up: "",
  max_votes_up: "",
  min_playtime: "",
  max_playtime: "",
  processing_status: "",
  reply_status: "",
  keyword: "",
  sort_by: "timestamp_created",
  sort_order: "desc",
  page: 1,
  page_size: 50
};

const processingStatusText: Record<string, string> = {
  pending: "待处理",
  on_hold: "待定",
  ignored: "已忽略"
};

const replyStatusText: Record<string, string> = {
  none: "未回复",
  drafted: "已生成草稿",
  replied: "已回复"
};

function ReviewsPage() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<ReviewQuery>(defaultFilters);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [activeReviewId, setActiveReviewId] = useState<number | null>(null);
  const reviewsQuery = useQuery({
    queryKey: ["reviews", filters],
    queryFn: () => fetchReviews(filters)
  });
  const detailQuery = useQuery({
    queryKey: ["review", activeReviewId],
    queryFn: () => fetchReviewDetail(activeReviewId as number),
    enabled: activeReviewId !== null
  });
  const bulkStatusMutation = useMutation({
    mutationFn: (processingStatus: string) =>
      bulkUpdateReviewStatus(selectedIds, { processing_status: processingStatus }),
    onSuccess: () => {
      setSelectedIds([]);
      void queryClient.invalidateQueries({ queryKey: ["reviews"] });
      void queryClient.invalidateQueries({ queryKey: ["review"] });
    }
  });
  const singleStatusMutation = useMutation({
    mutationFn: ({ reviewId, status }: { reviewId: number; status: string }) =>
      updateReviewStatus(reviewId, { processing_status: status }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reviews"] });
      void queryClient.invalidateQueries({ queryKey: ["review"] });
    }
  });
  const totalPages = useMemo(() => {
    const total = reviewsQuery.data?.total ?? 0;
    const pageSize = filters.page_size ?? 50;
    return Math.max(1, Math.ceil(total / pageSize));
  }, [filters.page_size, reviewsQuery.data?.total]);

  const items = reviewsQuery.data?.items ?? [];
  const activeFilters = getActiveFilters(filters);
  const allCurrentPageSelected =
    items.length > 0 && items.every((item) => selectedIds.includes(item.id));

  function updateFilter(key: keyof ReviewQuery, value: string | number) {
    setFilters((current) => ({ ...current, [key]: value, page: 1 }));
  }

  function resetFilters() {
    setFilters(defaultFilters);
    setSelectedIds([]);
  }

  function toggleReview(reviewId: number) {
    setSelectedIds((current) =>
      current.includes(reviewId) ? current.filter((id) => id !== reviewId) : [...current, reviewId]
    );
  }

  function toggleCurrentPage() {
    if (allCurrentPageSelected) {
      const pageIds = new Set(items.map((item) => item.id));
      setSelectedIds((current) => current.filter((id) => !pageIds.has(id)));
      return;
    }
    setSelectedIds((current) => [...new Set([...current, ...items.map((item) => item.id)])]);
  }

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:py-8 xl:px-8">
      <section className="rounded-[1.5rem] border border-white/80 bg-white/85 p-5 shadow-xl shadow-slate-200/70 backdrop-blur sm:rounded-[2rem] sm:p-6">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-sky-100 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              阶段 3 · Review Operations
            </div>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950 xl:text-4xl">
              评论列表与筛选
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
              面向 Steam 评论运营的管理视图，集中完成筛选、扫读、详情查看和批量状态标记。
            </p>
          </div>
          <div className="grid grid-cols-1 gap-3 rounded-3xl border border-slate-100 bg-slate-50/80 p-3 sm:grid-cols-3">
            <MetricCard label="评论总数" value={reviewsQuery.data?.total ?? 0} />
            <MetricCard label="当前页" value={items.length} />
            <MetricCard label="已选中" value={selectedIds.length} accent />
          </div>
        </div>
      </section>

      <section className="mt-5 rounded-[1.5rem] border border-white/80 bg-white/90 p-4 shadow-lg shadow-slate-200/60 backdrop-blur sm:mt-6 sm:rounded-[1.75rem] sm:p-5">
        <div className="flex flex-col gap-4 border-b border-slate-100 pb-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-600 text-white shadow-lg shadow-sky-500/20">
              <SlidersHorizontal className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-950">筛选控制面板</h2>
              <p className="mt-1 text-sm text-slate-500">组合条件会实时刷新评论列表。</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={resetFilters}>
              重置筛选
            </Button>
            <Button type="button" onClick={() => void queryClient.invalidateQueries({ queryKey: ["reviews"] })}>
              <RefreshCcw className="h-4 w-4" aria-hidden="true" />
              刷新数据
            </Button>
          </div>
        </div>

        <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
          <FilterInput
            label="App ID"
            value={filters.app_id}
            onChange={(value) => updateFilter("app_id", value)}
          />
          <FilterSelect
            label="评价"
            value={filters.voted_up}
            onChange={(value) => updateFilter("voted_up", value)}
          >
            <option value="">全部</option>
            <option value="true">好评</option>
            <option value="false">差评</option>
          </FilterSelect>
          <FilterInput
            label="最小点赞"
            value={filters.min_votes_up}
            onChange={(value) => updateFilter("min_votes_up", value)}
          />
          <FilterInput
            label="最大点赞"
            value={filters.max_votes_up}
            onChange={(value) => updateFilter("max_votes_up", value)}
          />
          <FilterInput
            label="最小游戏时长"
            value={filters.min_playtime}
            onChange={(value) => updateFilter("min_playtime", value)}
          />
          <FilterInput
            label="最大游戏时长"
            value={filters.max_playtime}
            onChange={(value) => updateFilter("max_playtime", value)}
          />
          <FilterSelect
            label="处理状态"
            value={filters.processing_status}
            onChange={(value) => updateFilter("processing_status", value)}
          >
            <option value="">全部</option>
            <option value="pending">待处理</option>
            <option value="on_hold">待定</option>
            <option value="ignored">忽略</option>
          </FilterSelect>
          <FilterSelect
            label="回复状态"
            value={filters.reply_status}
            onChange={(value) => updateFilter("reply_status", value)}
          >
            <option value="">全部</option>
            <option value="none">未回复</option>
            <option value="drafted">已生成草稿</option>
            <option value="replied">已回复</option>
          </FilterSelect>
          <FilterSelect
            label="排序字段"
            value={filters.sort_by}
            onChange={(value) => updateFilter("sort_by", value)}
          >
            <option value="timestamp_created">发布时间</option>
            <option value="votes_up">点赞数</option>
            <option value="playtime_forever">总游玩时长</option>
            <option value="playtime_at_review">评论时长</option>
          </FilterSelect>
          <FilterSelect
            label="排序"
            value={filters.sort_order}
            onChange={(value) => updateFilter("sort_order", value)}
          >
            <option value="desc">降序</option>
            <option value="asc">升序</option>
          </FilterSelect>
          <label className="flex flex-col gap-2 text-sm sm:col-span-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">关键词搜索</span>
            <span className="flex h-11 items-center rounded-2xl border border-slate-200 bg-slate-50 px-3 shadow-inner shadow-white transition focus-within:border-sky-300 focus-within:bg-white focus-within:ring-4 focus-within:ring-sky-100">
              <Search className="h-4 w-4 text-slate-400" aria-hidden="true" />
              <input
                className="ml-2 w-full bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400"
                value={filters.keyword}
                onChange={(event) => updateFilter("keyword", event.target.value)}
                placeholder="搜索评论、昵称、SteamID"
              />
            </span>
          </label>
        </div>

        {activeFilters.length > 0 ? (
          <div className="mt-5 flex flex-wrap gap-2">
            {activeFilters.map((filter) => (
              <span
                key={filter}
                className="rounded-full border border-sky-100 bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700"
              >
                {filter}
              </span>
            ))}
          </div>
        ) : null}
      </section>

      <section className="mt-5 flex flex-col gap-3 rounded-3xl border border-white/80 bg-white/82 px-4 py-4 shadow-lg shadow-slate-200/50 sm:flex-row sm:items-center sm:justify-between sm:px-5">
        <div>
          <p className="text-sm font-semibold text-slate-900">批量操作</p>
          <p className="mt-1 text-xs text-slate-500">
            已选择 {selectedIds.length} 条评论，可批量调整处理状态。
          </p>
        </div>
        <div className="flex w-full gap-2 sm:w-auto">
          <Button
            type="button"
            variant="outline"
            className="flex-1 sm:flex-none"
            disabled={selectedIds.length === 0 || bulkStatusMutation.isPending}
            onClick={() => bulkStatusMutation.mutate("on_hold")}
          >
            标记待定
          </Button>
          <Button
            type="button"
            variant="danger"
            className="flex-1 sm:flex-none"
            disabled={selectedIds.length === 0 || bulkStatusMutation.isPending}
            onClick={() => bulkStatusMutation.mutate("ignored")}
          >
            忽略
          </Button>
        </div>
      </section>

      <section className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px] 2xl:grid-cols-[minmax(0,1fr)_440px]">
        <div className="overflow-hidden rounded-[1.75rem] border border-white/70 bg-white shadow-xl shadow-slate-200/70">
          <div className="flex flex-col gap-3 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-950">评论数据</h2>
              <p className="mt-1 text-xs text-slate-500">按当前筛选条件展示，点击评论查看右侧详情。</p>
            </div>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
              {reviewsQuery.isFetching ? "同步视图中" : "视图已更新"}
            </span>
          </div>
          <div className="hidden md:block">
            <table className="w-full table-fixed border-collapse text-left text-sm">
              <colgroup>
                <col className="w-12" />
                <col className="w-24" />
                <col />
                <col className="w-24" />
                <col className="w-28" />
                <col className="w-28" />
                <col className="w-32" />
              </colgroup>
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="w-12 px-5 py-4">
                    <input
                      className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                      type="checkbox"
                      checked={allCurrentPageSelected}
                      onChange={toggleCurrentPage}
                    />
                  </th>
                  <th className="px-4 py-4">评价</th>
                  <th className="px-4 py-4">评论内容</th>
                  <th className="px-4 py-4">互动</th>
                  <th className="px-4 py-4">游玩时长</th>
                  <th className="px-4 py-4">状态</th>
                  <th className="px-4 py-4">发布时间</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {reviewsQuery.isLoading ? <TableMessage message="评论数据加载中..." /> : null}
                {items.map((item) => (
                  <ReviewRow
                    key={item.id}
                    item={item}
                    selected={selectedIds.includes(item.id)}
                    active={activeReviewId === item.id}
                    onToggle={() => toggleReview(item.id)}
                    onOpen={() => setActiveReviewId(item.id)}
                  />
                ))}
                {!reviewsQuery.isLoading && items.length === 0 ? <EmptyTableState /> : null}
              </tbody>
            </table>
          </div>
          <div className="grid gap-3 p-3 md:hidden">
            {reviewsQuery.isLoading ? (
              <div className="rounded-3xl border border-slate-100 bg-slate-50 p-5 text-sm text-slate-500">
                评论数据加载中...
              </div>
            ) : null}
            {items.map((item) => (
              <MobileReviewCard
                key={item.id}
                item={item}
                selected={selectedIds.includes(item.id)}
                active={activeReviewId === item.id}
                onToggle={() => toggleReview(item.id)}
                onOpen={() => setActiveReviewId(item.id)}
              />
            ))}
            {!reviewsQuery.isLoading && items.length === 0 ? (
              <div className="rounded-3xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center">
                <Inbox className="mx-auto h-10 w-10 text-slate-400" aria-hidden="true" />
                <h3 className="mt-4 text-base font-semibold text-slate-900">暂无匹配评论</h3>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  调整筛选条件，或先执行存量导入/Steam 增量同步。
                </p>
              </div>
            ) : null}
          </div>
        </div>

        {activeReviewId !== null ? (
          <button
            type="button"
            className="fixed inset-0 z-40 bg-slate-950/20 backdrop-blur-[2px] xl:hidden"
            aria-label="关闭评论详情"
            onClick={() => setActiveReviewId(null)}
          />
        ) : null}
        <aside
          className={
            activeReviewId === null
              ? "hidden rounded-[1.75rem] border border-white/80 bg-white p-5 shadow-xl shadow-slate-200/70 xl:block xl:sticky xl:top-6 xl:self-start"
              : "fixed inset-x-3 bottom-3 top-20 z-50 overflow-y-auto rounded-[1.75rem] border border-white/80 bg-white p-5 shadow-2xl shadow-slate-900/20 xl:sticky xl:inset-auto xl:top-6 xl:z-auto xl:self-start xl:shadow-xl xl:shadow-slate-200/70"
          }
        >
          {activeReviewId === null ? (
            <ReviewEmptyState />
          ) : detailQuery.isLoading ? (
            <div className="rounded-3xl border border-slate-100 bg-slate-50 p-5 text-sm text-slate-500">
              详情加载中...
            </div>
          ) : detailQuery.data ? (
            <>
              <button
                type="button"
                className="absolute right-4 top-4 rounded-full border border-slate-200 bg-white p-2 text-slate-500 shadow-sm xl:hidden"
                aria-label="关闭评论详情"
                onClick={() => setActiveReviewId(null)}
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
              <ReviewDetailPanel
                review={detailQuery.data}
                busy={singleStatusMutation.isPending}
                onMark={(status) => singleStatusMutation.mutate({ reviewId: detailQuery.data.id, status })}
              />
            </>
          ) : (
            <div className="rounded-3xl border border-rose-100 bg-rose-50 p-5 text-sm text-rose-600">
              详情加载失败。
            </div>
          )}
        </aside>
      </section>

      <footer className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-white/80 bg-white/82 px-4 py-4 shadow-lg shadow-slate-200/50 sm:justify-end sm:px-5">
        <Button
          type="button"
          variant="outline"
          disabled={(filters.page ?? 1) <= 1}
          onClick={() =>
            setFilters((current) => ({ ...current, page: Math.max(1, (current.page ?? 1) - 1) }))
          }
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          上一页
        </Button>
        <span className="rounded-full bg-slate-100 px-4 py-2 text-sm font-medium text-slate-600">
          第 {filters.page ?? 1} / {totalPages} 页
        </span>
        <Button
          type="button"
          variant="outline"
          disabled={(filters.page ?? 1) >= totalPages}
          onClick={() => setFilters((current) => ({ ...current, page: (current.page ?? 1) + 1 }))}
        >
          下一页
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </Button>
      </footer>
    </main>
  );
}

function MetricCard({ label, value, accent = false }: { label: string; value: number; accent?: boolean }) {
  return (
    <div
      className={
        accent
          ? "rounded-2xl bg-sky-600 px-4 py-3 text-white"
          : "rounded-2xl bg-white px-4 py-3 text-slate-900 shadow-sm"
      }
    >
      <p className={accent ? "text-xs text-sky-100" : "text-xs text-slate-500"}>{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value.toLocaleString()}</p>
    </div>
  );
}

function ReviewRow({
  item,
  selected,
  active,
  onToggle,
  onOpen
}: {
  item: ReviewListItem;
  selected: boolean;
  active: boolean;
  onToggle: () => void;
  onOpen: () => void;
}) {
  return (
    <tr className={active ? "bg-sky-50/80" : "bg-white transition-colors hover:bg-slate-50"}>
      <td className="px-5 py-4">
        <input
          className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
          type="checkbox"
          checked={selected}
          onChange={onToggle}
        />
      </td>
      <td className="px-4 py-4">
        <ReviewSentiment votedUp={item.voted_up} />
      </td>
      <td className="min-w-0 px-4 py-4">
        <button type="button" className="block text-left" onClick={onOpen}>
          <span className="line-clamp-2 font-medium leading-6 text-slate-900 hover:text-sky-700">
            {item.review_text || "无文本"}
          </span>
        </button>
        <div className="mt-2 flex min-w-0 items-center gap-2 text-xs text-slate-500">
          <UserRound className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="truncate">{item.persona_name ?? item.steam_id ?? item.recommendation_id}</span>
          <span className="h-1 w-1 rounded-full bg-slate-300" />
          <span className="shrink-0">{item.language ?? "unknown"}</span>
        </div>
      </td>
      <td className="px-4 py-4">
        <div className="flex items-center gap-2 font-semibold text-slate-900">
          <ThumbsUp className="h-4 w-4 text-sky-500" aria-hidden="true" />
          {item.votes_up}
        </div>
        <p className="mt-1 text-xs text-slate-400">有趣 {item.votes_funny}</p>
      </td>
      <td className="px-4 py-4">
        <div className="flex items-center gap-2 font-medium text-slate-900">
          <Clock3 className="h-4 w-4 text-cyan-500" aria-hidden="true" />
          {item.playtime_forever ?? "-"}h
        </div>
        <p className="mt-1 text-xs text-slate-400">评论时 {item.playtime_at_review ?? "-"}h</p>
      </td>
      <td className="px-4 py-4">
        <StatusBadge status={item.processing_status} />
        <p className="mt-2 text-xs text-slate-500">{replyStatusText[item.reply_status] ?? item.reply_status}</p>
      </td>
      <td className="px-4 py-4 text-xs font-medium text-slate-500">{formatDate(item.timestamp_created)}</td>
    </tr>
  );
}

function MobileReviewCard({
  item,
  selected,
  active,
  onToggle,
  onOpen
}: {
  item: ReviewListItem;
  selected: boolean;
  active: boolean;
  onToggle: () => void;
  onOpen: () => void;
}) {
  return (
    <article
      className={
        active
          ? "rounded-3xl border border-sky-200 bg-sky-50/80 p-4 shadow-sm"
          : "rounded-3xl border border-slate-100 bg-white p-4 shadow-sm shadow-slate-100"
      }
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <input
            className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
            type="checkbox"
            checked={selected}
            onChange={onToggle}
          />
          <ReviewSentiment votedUp={item.voted_up} />
        </div>
        <StatusBadge status={item.processing_status} />
      </div>
      <button type="button" className="mt-4 block text-left" onClick={onOpen}>
        <span className="line-clamp-3 text-sm font-semibold leading-6 text-slate-950">
          {item.review_text || "无文本"}
        </span>
      </button>
      <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
        <MiniStat label="点赞" value={item.votes_up} />
        <MiniStat label="时长" value={`${item.playtime_forever ?? "-"}h`} />
        <MiniStat label="回复" value={replyStatusText[item.reply_status] ?? item.reply_status} />
      </div>
      <div className="mt-3 flex items-center justify-between gap-3 text-xs text-slate-500">
        <span className="truncate">{item.persona_name ?? item.steam_id ?? item.recommendation_id}</span>
        <span className="shrink-0">{formatDate(item.timestamp_created)}</span>
      </div>
    </article>
  );
}

function MiniStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl bg-slate-50 px-3 py-2">
      <p className="text-[11px] text-slate-400">{label}</p>
      <p className="mt-1 truncate font-semibold text-slate-800">{value}</p>
    </div>
  );
}

function ReviewDetailPanel({
  review,
  busy,
  onMark
}: {
  review: ReviewDetail;
  busy: boolean;
  onMark: (status: string) => void;
}) {
  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Review Detail</p>
          <h2 className="mt-2 text-xl font-semibold text-slate-950">评论详情</h2>
        </div>
        <StatusBadge status={review.processing_status} />
      </div>

      <div className="mt-5 rounded-3xl border border-slate-100 bg-slate-50 p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white text-sky-600 shadow-sm">
            <UserRound className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-950">
              {review.persona_name ?? review.steam_id ?? "匿名用户"}
            </p>
            <p className="mt-1 text-xs text-slate-500">{review.steam_id ?? review.recommendation_id}</p>
          </div>
        </div>
        <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-700">{review.review_text}</p>
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
        <DetailItem label="评价" value={review.voted_up ? "好评" : "差评"} />
        <DetailItem label="回复状态" value={replyStatusText[review.reply_status] ?? review.reply_status} />
        <DetailItem label="点赞" value={review.votes_up} />
        <DetailItem label="有趣" value={review.votes_funny} />
        <DetailItem label="总时长" value={`${review.playtime_forever ?? "-"}h`} />
        <DetailItem label="评论时长" value={`${review.playtime_at_review ?? "-"}h`} />
        <DetailItem label="拥有游戏" value={review.num_games_owned ?? "-"} />
        <DetailItem label="测评数" value={review.num_reviews ?? "-"} />
      </dl>

      {review.developer_response ? (
        <div className="mt-5 rounded-3xl border border-emerald-100 bg-emerald-50 p-4">
          <p className="text-xs font-semibold text-emerald-700">已有开发者回复</p>
          <p className="mt-2 text-sm leading-6 text-emerald-900">{review.developer_response}</p>
        </div>
      ) : null}

      <div className="mt-5 flex gap-2">
        <Button type="button" variant="outline" disabled={busy} onClick={() => onMark("on_hold")}>
          标记待定
        </Button>
        <Button type="button" variant="danger" disabled={busy} onClick={() => onMark("ignored")}>
          忽略
        </Button>
      </div>
    </div>
  );
}

function ReviewEmptyState() {
  return (
    <div className="flex min-h-[420px] flex-col items-center justify-center rounded-3xl border border-dashed border-slate-200 bg-slate-50/80 p-8 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-white text-sky-600 shadow-lg shadow-slate-200">
        <MessageSquareText className="h-7 w-7" aria-hidden="true" />
      </div>
      <h2 className="mt-5 text-lg font-semibold text-slate-950">选择一条评论查看详情</h2>
      <p className="mt-2 max-w-xs text-sm leading-6 text-slate-500">
        右侧会展示评论正文、用户信息、状态、互动数据和后续可执行的运营动作。
      </p>
    </div>
  );
}

function EmptyTableState() {
  return (
    <tr>
      <td className="px-6 py-16" colSpan={7}>
        <div className="mx-auto flex max-w-md flex-col items-center rounded-3xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center">
          <Inbox className="h-10 w-10 text-slate-400" aria-hidden="true" />
          <h3 className="mt-4 text-base font-semibold text-slate-900">暂无匹配评论</h3>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            调整筛选条件，或先执行存量导入/Steam 增量同步。
          </p>
        </div>
      </td>
    </tr>
  );
}

function TableMessage({ message }: { message: string }) {
  return (
    <tr>
      <td className="px-6 py-8 text-sm text-slate-500" colSpan={7}>
        {message}
      </td>
    </tr>
  );
}

function ReviewSentiment({ votedUp }: { votedUp: boolean | null }) {
  if (votedUp) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-100">
        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
        好评
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-700 ring-1 ring-rose-100">
      <AlertCircle className="h-3.5 w-3.5" aria-hidden="true" />
      差评
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const label = processingStatusText[status] ?? status;
  const className =
    status === "ignored"
      ? "bg-slate-100 text-slate-600 ring-slate-200"
      : status === "on_hold"
        ? "bg-amber-50 text-amber-700 ring-amber-100"
        : "bg-sky-50 text-sky-700 ring-sky-100";
  return <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ring-1 ${className}`}>{label}</span>;
}

function DetailItem({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-3 shadow-sm">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-1 break-all font-semibold text-slate-950">{value}</dd>
    </div>
  );
}

function FilterInput({
  label,
  value,
  onChange
}: {
  label: string;
  value: string | number | undefined;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-2 text-sm">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <input
        className="h-11 rounded-2xl border border-slate-200 bg-slate-50 px-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-sky-300 focus:bg-white focus:ring-4 focus:ring-sky-100"
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  children
}: {
  label: string;
  value: string | number | undefined;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <label className="flex flex-col gap-2 text-sm">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <select
        className="h-11 rounded-2xl border border-slate-200 bg-slate-50 px-3 text-sm text-slate-900 outline-none transition focus:border-sky-300 focus:bg-white focus:ring-4 focus:ring-sky-100"
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
      >
        {children}
      </select>
    </label>
  );
}

function getActiveFilters(filters: ReviewQuery) {
  const chips: string[] = [];
  if (filters.app_id) chips.push(`App ${filters.app_id}`);
  if (filters.voted_up === "true") chips.push("好评");
  if (filters.voted_up === "false") chips.push("差评");
  if (filters.min_votes_up) chips.push(`点赞 ≥ ${filters.min_votes_up}`);
  if (filters.max_votes_up) chips.push(`点赞 ≤ ${filters.max_votes_up}`);
  if (filters.min_playtime) chips.push(`时长 ≥ ${filters.min_playtime}h`);
  if (filters.max_playtime) chips.push(`时长 ≤ ${filters.max_playtime}h`);
  if (filters.processing_status) {
    chips.push(processingStatusText[filters.processing_status] ?? filters.processing_status);
  }
  if (filters.reply_status) chips.push(replyStatusText[filters.reply_status] ?? filters.reply_status);
  if (filters.keyword) chips.push(`关键词：${filters.keyword}`);
  return chips;
}

function formatDate(value: string | null) {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "short",
    timeStyle: "short"
  }).format(new Date(value));
}

export const reviewsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/reviews",
  component: ReviewsPage
});
