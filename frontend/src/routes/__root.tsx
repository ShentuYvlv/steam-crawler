import { Link, Outlet, createRootRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, Clock3, MessageSquareText, Send, Settings2, Sparkles } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { clearAccessToken, fetchMe, login, setAccessToken } from "@/lib/api";

export const rootRoute = createRootRoute({
  component: RootLayout
});

function RootLayout() {
  const queryClient = useQueryClient();
  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: fetchMe,
    retry: false
  });
  const currentUser = meQuery.data;

  if (meQuery.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-500">
        正在验证登录状态...
      </div>
    );
  }

  if (!currentUser) {
    return <LoginScreen />;
  }

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
            {currentUser.role === "admin" ? (
              <Link
                to="/users"
                className="rounded-xl px-3 py-2 text-slate-500 transition [&.active]:bg-white [&.active]:text-sky-700 [&.active]:shadow-sm"
              >
                用户
              </Link>
            ) : null}
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
          {currentUser.role === "admin" ? (
            <Link
              to="/users"
              className="group relative flex items-center gap-3 rounded-2xl border border-transparent px-3 py-3 text-slate-500 transition-all hover:bg-slate-50 hover:text-slate-950 [&.active]:border-sky-100 [&.active]:bg-sky-50 [&.active]:text-sky-700 [&.active]:shadow-sm"
            >
              <Settings2 className="h-4 w-4" aria-hidden="true" />
              用户管理
            </Link>
          ) : null}
        </nav>
        <div className="absolute inset-x-4 bottom-4 rounded-3xl border border-slate-100 bg-slate-50/80 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-900">
            <Settings2 className="h-4 w-4 text-sky-600" aria-hidden="true" />
            {currentUser.display_name ?? currentUser.username}
          </div>
          <p className="mt-2 text-[11px] leading-5 text-slate-500">
            当前角色：{currentUser.role}
          </p>
          <button
            type="button"
            className="mt-3 text-xs font-semibold text-sky-700"
            onClick={() => {
              clearAccessToken();
              queryClient.clear();
            }}
          >
            退出登录
          </button>
        </div>
      </aside>
      <div className="lg:pl-64">
        <Outlet />
      </div>
    </div>
  );
}

function LoginScreen() {
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const loginMutation = useMutation({
    mutationFn: () => login({ username, password }),
    onSuccess: (response) => {
      setAccessToken(response.access_token);
      void queryClient.invalidateQueries({ queryKey: ["me"] });
    }
  });

  return (
    <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.16),_transparent_30rem),linear-gradient(180deg,#f8fbff_0%,#eef5fb_100%)] px-4">
      <section className="w-full max-w-md rounded-[2rem] border border-white/80 bg-white/90 p-6 shadow-2xl shadow-slate-200/80">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-600 text-white">
            <Sparkles className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-slate-950">Steam Admin 登录</h1>
            <p className="mt-1 text-sm text-slate-500">账号由管理员创建，不开放注册。</p>
          </div>
        </div>
        <div className="mt-6 grid gap-4">
          <input
            className="h-11 rounded-2xl border border-slate-200 bg-slate-50 px-3 text-sm outline-none focus:border-sky-300 focus:ring-4 focus:ring-sky-100"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="用户名"
          />
          <input
            className="h-11 rounded-2xl border border-slate-200 bg-slate-50 px-3 text-sm outline-none focus:border-sky-300 focus:ring-4 focus:ring-sky-100"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="密码"
          />
          <Button
            type="button"
            disabled={loginMutation.isPending || !username || !password}
            onClick={() => loginMutation.mutate()}
          >
            登录
          </Button>
          {loginMutation.isError ? (
            <p className="text-sm font-medium text-rose-600">
              {(loginMutation.error as Error).message}
            </p>
          ) : null}
        </div>
      </section>
    </main>
  );
}
