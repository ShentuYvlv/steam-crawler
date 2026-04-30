import { Link, Outlet, createRootRoute } from "@tanstack/react-router";
import { BarChart3, Clock3, MessageSquareText, Send, Settings2, Sparkles } from "lucide-react";

export const rootRoute = createRootRoute({
  component: RootLayout
});

function RootLayout() {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.12),_transparent_32rem),linear-gradient(180deg,#f8fbff_0%,#eef5fb_100%)] text-slate-950">
      <header className="sticky top-0 z-30 border-b border-white/80 bg-white/85 px-4 py-3 shadow-sm shadow-slate-200/60 backdrop-blur lg:hidden">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-sky-600 text-white shadow-lg shadow-sky-500/20">
              <Sparkles className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-950">Steam Admin</p>
              <p className="text-xs text-slate-500">Review Operations</p>
            </div>
          </div>
          <nav className="flex rounded-2xl border border-slate-200 bg-slate-50 p-1 text-sm">
            <Link
              to="/"
              className="rounded-xl px-3 py-2 text-slate-500 transition [&.active]:bg-white [&.active]:text-sky-700 [&.active]:shadow-sm"
            >
              总览
            </Link>
            <Link
              to="/reviews"
              className="rounded-xl px-3 py-2 text-slate-500 transition [&.active]:bg-white [&.active]:text-sky-700 [&.active]:shadow-sm"
            >
              评论
            </Link>
            <Link
              to="/reply-strategies"
              className="rounded-xl px-3 py-2 text-slate-500 transition [&.active]:bg-white [&.active]:text-sky-700 [&.active]:shadow-sm"
            >
              策略
            </Link>
            <Link
              to="/tasks"
              className="rounded-xl px-3 py-2 text-slate-500 transition [&.active]:bg-white [&.active]:text-sky-700 [&.active]:shadow-sm"
            >
              任务
            </Link>
          </nav>
        </div>
      </header>

      <aside className="fixed inset-y-4 left-4 hidden w-56 rounded-[2rem] border border-white/80 bg-white/88 p-4 text-slate-900 shadow-2xl shadow-slate-200/80 backdrop-blur-xl lg:block">
        <div className="flex items-center gap-3 rounded-3xl border border-slate-100 bg-gradient-to-br from-white to-sky-50/70 p-3 shadow-sm">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-600 text-white shadow-lg shadow-sky-500/20">
            <Sparkles className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-950">Steam Admin</p>
            <p className="text-xs text-slate-500">Review Operations</p>
          </div>
        </div>
        <nav className="mt-8 flex flex-col gap-2 text-sm">
          <Link
            to="/"
            className="group relative flex items-center gap-3 rounded-2xl border border-transparent px-3 py-3 text-slate-500 transition-all hover:bg-slate-50 hover:text-slate-950 [&.active]:border-sky-100 [&.active]:bg-sky-50 [&.active]:text-sky-700 [&.active]:shadow-sm"
          >
            <BarChart3 className="h-4 w-4" aria-hidden="true" />
            总览
          </Link>
          <Link
            to="/reviews"
            className="group relative flex items-center gap-3 rounded-2xl border border-transparent px-3 py-3 text-slate-500 transition-all hover:bg-slate-50 hover:text-slate-950 [&.active]:border-sky-100 [&.active]:bg-sky-50 [&.active]:text-sky-700 [&.active]:shadow-sm"
          >
            <MessageSquareText className="h-4 w-4" aria-hidden="true" />
            评论列表
          </Link>
          <Link
            to="/reply-strategies"
            className="group relative flex items-center gap-3 rounded-2xl border border-transparent px-3 py-3 text-slate-500 transition-all hover:bg-slate-50 hover:text-slate-950 [&.active]:border-sky-100 [&.active]:bg-sky-50 [&.active]:text-sky-700 [&.active]:shadow-sm"
          >
            <Settings2 className="h-4 w-4" aria-hidden="true" />
            回复策略
          </Link>
          <Link
            to="/tasks"
            className="group relative flex items-center gap-3 rounded-2xl border border-transparent px-3 py-3 text-slate-500 transition-all hover:bg-slate-50 hover:text-slate-950 [&.active]:border-sky-100 [&.active]:bg-sky-50 [&.active]:text-sky-700 [&.active]:shadow-sm"
          >
            <Clock3 className="h-4 w-4" aria-hidden="true" />
            任务同步
          </Link>
          <Link
            to="/reply-records"
            className="group relative flex items-center gap-3 rounded-2xl border border-transparent px-3 py-3 text-slate-500 transition-all hover:bg-slate-50 hover:text-slate-950 [&.active]:border-sky-100 [&.active]:bg-sky-50 [&.active]:text-sky-700 [&.active]:shadow-sm"
          >
            <Send className="h-4 w-4" aria-hidden="true" />
            回复记录
          </Link>
        </nav>
        <div className="absolute inset-x-4 bottom-4 rounded-3xl border border-slate-100 bg-slate-50/80 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
            <Settings2 className="h-4 w-4 text-sky-600" aria-hidden="true" />
            本地运营后台
          </div>
          <p className="mt-2 text-[11px] leading-5 text-slate-500">
            评论同步、筛选、AI 回复审核与发送会按阶段逐步接入。
          </p>
        </div>
      </aside>
      <div className="lg:pl-64">
        <Outlet />
      </div>
    </div>
  );
}
