import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  bulkUpdateReviewStatus,
  fetchReviewDetail,
  fetchReviews,
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
  const totalPages = useMemo(() => {
    const total = reviewsQuery.data?.total ?? 0;
    const pageSize = filters.page_size ?? 50;
    return Math.max(1, Math.ceil(total / pageSize));
  }, [filters.page_size, reviewsQuery.data?.total]);

  const items = reviewsQuery.data?.items ?? [];
  const allCurrentPageSelected =
    items.length > 0 && items.every((item) => selectedIds.includes(item.id));

  function updateFilter(key: keyof ReviewQuery, value: string | number) {
    setFilters((current) => ({ ...current, [key]: value, page: 1 }));
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
    <main className="min-h-screen px-6 py-8">
      <header className="flex flex-col gap-3 border-b border-zinc-200 pb-6">
        <p className="text-sm font-medium text-zinc-500">阶段 3</p>
        <h1 className="text-3xl font-semibold">评论列表与筛选</h1>
        <p className="max-w-3xl text-sm leading-6 text-zinc-600">
          支持按评价、点赞数、游玩时长、状态和关键词筛选，并支持多选标记待定或忽略。
        </p>
      </header>

      <section className="mt-6 grid gap-3 border border-zinc-200 bg-white p-4 xl:grid-cols-6">
        <FilterInput label="App ID" value={filters.app_id} onChange={(value) => updateFilter("app_id", value)} />
        <FilterSelect label="评价" value={filters.voted_up} onChange={(value) => updateFilter("voted_up", value)}>
          <option value="">全部</option>
          <option value="true">好评</option>
          <option value="false">差评</option>
        </FilterSelect>
        <FilterInput label="最小点赞" value={filters.min_votes_up} onChange={(value) => updateFilter("min_votes_up", value)} />
        <FilterInput label="最大点赞" value={filters.max_votes_up} onChange={(value) => updateFilter("max_votes_up", value)} />
        <FilterInput label="最小游戏时长" value={filters.min_playtime} onChange={(value) => updateFilter("min_playtime", value)} />
        <FilterInput label="最大游戏时长" value={filters.max_playtime} onChange={(value) => updateFilter("max_playtime", value)} />
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
        <FilterSelect label="排序字段" value={filters.sort_by} onChange={(value) => updateFilter("sort_by", value)}>
          <option value="timestamp_created">发布时间</option>
          <option value="votes_up">点赞数</option>
          <option value="playtime_forever">总游玩时长</option>
          <option value="playtime_at_review">评论时长</option>
        </FilterSelect>
        <FilterSelect label="排序" value={filters.sort_order} onChange={(value) => updateFilter("sort_order", value)}>
          <option value="desc">降序</option>
          <option value="asc">升序</option>
        </FilterSelect>
        <label className="flex flex-col gap-1 text-sm xl:col-span-2">
          <span className="text-zinc-500">关键词</span>
          <span className="flex border border-zinc-300 bg-white">
            <Search className="m-2 h-5 w-5 text-zinc-400" />
            <input
              className="w-full px-2 py-2 outline-none"
              value={filters.keyword}
              onChange={(event) => updateFilter("keyword", event.target.value)}
              placeholder="搜索评论、昵称、SteamID"
            />
          </span>
        </label>
      </section>

      <section className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-zinc-600">
          共 {reviewsQuery.data?.total ?? 0} 条，已选 {selectedIds.length} 条
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={selectedIds.length === 0 || bulkStatusMutation.isPending}
            onClick={() => bulkStatusMutation.mutate("on_hold")}
          >
            标记待定
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={selectedIds.length === 0 || bulkStatusMutation.isPending}
            onClick={() => bulkStatusMutation.mutate("ignored")}
          >
            忽略
          </Button>
        </div>
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="overflow-hidden border border-zinc-200 bg-white">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="bg-zinc-100 text-xs uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="w-10 p-3">
                  <input type="checkbox" checked={allCurrentPageSelected} onChange={toggleCurrentPage} />
                </th>
                <th className="p-3">评价</th>
                <th className="p-3">评论</th>
                <th className="p-3">点赞</th>
                <th className="p-3">时长</th>
                <th className="p-3">状态</th>
                <th className="p-3">时间</th>
              </tr>
            </thead>
            <tbody>
              {reviewsQuery.isLoading ? (
                <tr>
                  <td className="p-6 text-zinc-500" colSpan={7}>
                    加载中...
                  </td>
                </tr>
              ) : null}
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
              {!reviewsQuery.isLoading && items.length === 0 ? (
                <tr>
                  <td className="p-6 text-zinc-500" colSpan={7}>
                    暂无评论数据。
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>

        <aside className="border border-zinc-200 bg-white p-5">
          {activeReviewId === null ? (
            <p className="text-sm text-zinc-500">点击左侧评论查看详情。</p>
          ) : detailQuery.isLoading ? (
            <p className="text-sm text-zinc-500">详情加载中...</p>
          ) : detailQuery.data ? (
            <ReviewDetailPanel review={detailQuery.data} />
          ) : (
            <p className="text-sm text-red-600">详情加载失败。</p>
          )}
        </aside>
      </section>

      <footer className="mt-4 flex items-center justify-end gap-2">
        <Button
          type="button"
          variant="outline"
          disabled={(filters.page ?? 1) <= 1}
          onClick={() => setFilters((current) => ({ ...current, page: Math.max(1, (current.page ?? 1) - 1) }))}
        >
          上一页
        </Button>
        <span className="text-sm text-zinc-500">
          第 {filters.page ?? 1} / {totalPages} 页
        </span>
        <Button
          type="button"
          variant="outline"
          disabled={(filters.page ?? 1) >= totalPages}
          onClick={() => setFilters((current) => ({ ...current, page: (current.page ?? 1) + 1 }))}
        >
          下一页
        </Button>
      </footer>
    </main>
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
    <tr className={active ? "bg-zinc-100" : "border-t border-zinc-100"}>
      <td className="p-3">
        <input type="checkbox" checked={selected} onChange={onToggle} />
      </td>
      <td className="p-3">{item.voted_up ? "好评" : "差评"}</td>
      <td className="max-w-xl p-3">
        <button type="button" className="text-left hover:underline" onClick={onOpen}>
          <span className="line-clamp-2">{item.review_text || "无文本"}</span>
        </button>
        <p className="mt-1 text-xs text-zinc-500">{item.persona_name ?? item.steam_id ?? item.recommendation_id}</p>
      </td>
      <td className="p-3">{item.votes_up}</td>
      <td className="p-3">{item.playtime_forever ?? "-"}h</td>
      <td className="p-3">
        <span className="border border-zinc-300 px-2 py-1 text-xs">{item.processing_status}</span>
      </td>
      <td className="p-3 text-xs text-zinc-500">{formatDate(item.timestamp_created)}</td>
    </tr>
  );
}

function ReviewDetailPanel({ review }: { review: ReviewListItem & Record<string, unknown> }) {
  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">评论详情</h2>
        <span className="border border-zinc-300 px-2 py-1 text-xs">{review.processing_status}</span>
      </div>
      <p className="mt-4 whitespace-pre-wrap text-sm leading-6">{review.review_text}</p>
      <dl className="mt-6 grid grid-cols-2 gap-3 text-sm">
        <DetailItem label="推荐 ID" value={review.recommendation_id} />
        <DetailItem label="SteamID" value={review.steam_id ?? "-"} />
        <DetailItem label="语言" value={review.language ?? "-"} />
        <DetailItem label="评价" value={review.voted_up ? "好评" : "差评"} />
        <DetailItem label="点赞" value={review.votes_up} />
        <DetailItem label="有趣" value={review.votes_funny} />
        <DetailItem label="总时长" value={`${review.playtime_forever ?? "-"}h`} />
        <DetailItem label="评论时长" value={`${review.playtime_at_review ?? "-"}h`} />
      </dl>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt className="text-xs text-zinc-500">{label}</dt>
      <dd className="mt-1 break-all text-zinc-900">{value}</dd>
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
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-zinc-500">{label}</span>
      <input
        className="border border-zinc-300 px-3 py-2 outline-none focus:border-zinc-900"
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
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-zinc-500">{label}</span>
      <select
        className="border border-zinc-300 bg-white px-3 py-2 outline-none focus:border-zinc-900"
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
      >
        {children}
      </select>
    </label>
  );
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
