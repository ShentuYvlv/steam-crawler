import { createRoute } from "@tanstack/react-router";
import { BarChart3, Bot, CheckCircle2, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { rootRoute } from "@/routes/__root";

const workflowItems = [
  {
    icon: RefreshCcw,
    title: "评论同步",
    description: "导入存量 CSV，并定时同步 Steam 新增评论。"
  },
  {
    icon: Bot,
    title: "AI 草稿",
    description: "基于运营策略和评论内容生成可审核的回复草稿。"
  },
  {
    icon: CheckCircle2,
    title: "人工审核",
    description: "运营确认后再发送，保留修改和重试记录。"
  },
  {
    icon: BarChart3,
    title: "运营统计",
    description: "追踪待处理、已回复、好评率和发送成功率。"
  }
];

function DashboardHome() {
  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-950">
      <section className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-6 py-8">
        <header className="flex flex-col gap-4 border-b border-zinc-200 pb-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-medium text-zinc-500">Steam Review Admin</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-normal text-zinc-950">
              Steam 评论 AI 回复后台
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-600">
              第一阶段工程基线已建立，后续会逐步接入评论入库、筛选、AI 生成、审核发送和统计。
            </p>
          </div>
          <Button type="button">进入评论列表</Button>
        </header>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {workflowItems.map((item) => (
            <article key={item.title} className="border border-zinc-200 bg-white p-5">
              <item.icon className="h-5 w-5 text-zinc-700" aria-hidden="true" />
              <h2 className="mt-4 text-base font-semibold text-zinc-950">{item.title}</h2>
              <p className="mt-2 text-sm leading-6 text-zinc-600">{item.description}</p>
            </article>
          ))}
        </section>
      </section>
    </main>
  );
}

export const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: DashboardHome
});

