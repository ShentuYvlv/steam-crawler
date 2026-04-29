import { Link, Outlet, createRootRoute } from "@tanstack/react-router";

export const rootRoute = createRootRoute({
  component: RootLayout
});

function RootLayout() {
  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-950">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-zinc-200 bg-white p-5 lg:block">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-400">Steam Admin</p>
        <nav className="mt-8 flex flex-col gap-2 text-sm">
          <Link
            to="/"
            className="border border-transparent px-3 py-2 text-zinc-600 [&.active]:border-zinc-900 [&.active]:text-zinc-950"
          >
            总览
          </Link>
          <Link
            to="/reviews"
            className="border border-transparent px-3 py-2 text-zinc-600 [&.active]:border-zinc-900 [&.active]:text-zinc-950"
          >
            评论列表
          </Link>
        </nav>
      </aside>
      <div className="lg:pl-64">
        <Outlet />
      </div>
    </div>
  );
}
