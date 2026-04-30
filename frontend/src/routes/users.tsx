import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import { UserPlus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { createUser, fetchUsers, updateUser, type User } from "@/lib/api";
import { rootRoute } from "@/routes/__root";

function UsersPage() {
  const queryClient = useQueryClient();
  const usersQuery = useQuery({ queryKey: ["users"], queryFn: fetchUsers });
  const [form, setForm] = useState({
    username: "",
    password: "",
    display_name: "",
    role: "operator",
    is_active: true
  });
  const createMutation = useMutation({
    mutationFn: () =>
      createUser({
        username: form.username,
        password: form.password,
        display_name: form.display_name || null,
        role: form.role,
        is_active: form.is_active
      }),
    onSuccess: () => {
      setForm({ username: "", password: "", display_name: "", role: "operator", is_active: true });
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    }
  });
  const updateMutation = useMutation({
    mutationFn: ({
      userId,
      payload
    }: {
      userId: number;
      payload: { role?: string; is_active?: boolean; display_name?: string | null; password?: string };
    }) =>
      updateUser(userId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    }
  });

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:py-8 xl:px-8">
      <section className="rounded-[2rem] border border-white/80 bg-white/90 p-6 shadow-xl shadow-slate-200/70">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-600 text-white">
            <UserPlus className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-slate-950">用户管理</h1>
            <p className="mt-1 text-sm text-slate-500">仅管理员可见；不开放注册和忘记密码。</p>
          </div>
        </div>

        <div className="mt-6 grid gap-3 rounded-3xl border border-slate-100 bg-slate-50/80 p-4 md:grid-cols-5">
          <Input label="用户名" value={form.username} onChange={(value) => setForm({ ...form, username: value })} />
          <Input label="密码" type="password" value={form.password} onChange={(value) => setForm({ ...form, password: value })} />
          <Input label="显示名" value={form.display_name} onChange={(value) => setForm({ ...form, display_name: value })} />
          <label className="flex flex-col gap-2 text-sm">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">角色</span>
            <select
              className="h-11 rounded-2xl border border-slate-200 bg-white px-3 text-sm outline-none"
              value={form.role}
              onChange={(event) => setForm({ ...form, role: event.target.value })}
            >
              <option value="operator">operator</option>
              <option value="viewer">viewer</option>
              <option value="admin">admin</option>
            </select>
          </label>
          <div className="flex items-end">
            <Button
              type="button"
              className="w-full"
              disabled={createMutation.isPending || !form.username || form.password.length < 8}
              onClick={() => createMutation.mutate()}
            >
              创建用户
            </Button>
          </div>
        </div>
      </section>

      <section className="mt-6 grid gap-3">
        {(usersQuery.data ?? []).map((user) => (
          <UserCard
            key={user.id}
            user={user}
            busy={updateMutation.isPending}
            onToggle={() =>
              updateMutation.mutate({ userId: user.id, payload: { is_active: !user.is_active } })
            }
            onRole={(role) => updateMutation.mutate({ userId: user.id, payload: { role } })}
          />
        ))}
      </section>
    </main>
  );
}

function UserCard({
  user,
  busy,
  onToggle,
  onRole
}: {
  user: User;
  busy: boolean;
  onToggle: () => void;
  onRole: (role: string) => void;
}) {
  return (
    <article className="flex flex-col gap-4 rounded-[2rem] border border-white/80 bg-white p-5 shadow-lg shadow-slate-200/60 md:flex-row md:items-center md:justify-between">
      <div>
        <p className="font-semibold text-slate-950">{user.display_name ?? user.username}</p>
        <p className="mt-1 text-sm text-slate-500">{user.username} · {user.role} · {user.is_active ? "启用" : "停用"}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <select
          className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm"
          value={user.role}
          disabled={busy}
          onChange={(event) => onRole(event.target.value)}
        >
          <option value="operator">operator</option>
          <option value="viewer">viewer</option>
          <option value="admin">admin</option>
        </select>
        <Button type="button" variant="outline" disabled={busy} onClick={onToggle}>
          {user.is_active ? "停用" : "启用"}
        </Button>
      </div>
    </article>
  );
}

function Input({
  label,
  value,
  onChange,
  type = "text"
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
}) {
  return (
    <label className="flex flex-col gap-2 text-sm">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <input
        className="h-11 rounded-2xl border border-slate-200 bg-white px-3 text-sm outline-none"
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

export const usersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/users",
  component: UsersPage
});
