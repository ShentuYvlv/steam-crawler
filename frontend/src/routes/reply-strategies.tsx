import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import { CheckCircle2, FileCode2, Plus, Save, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  activateReplyStrategy,
  createReplyStrategy,
  fetchDefaultReplySkill,
  fetchReplyStrategies,
  updateReplyStrategy,
  type ReplyStrategy,
  type ReplyStrategyPayload
} from "@/lib/api";
import { rootRoute } from "@/routes/__root";

const defaultForm: ReplyStrategyPayload = {
  name: "默认回复 Skill",
  description: "用于 Steam 评论回复生成的 Skill 文档。",
  skill_content: "",
  model_name: "qwen-plus",
  temperature: 0.4,
  is_active: true
};

function ReplyStrategiesPage() {
  const queryClient = useQueryClient();
  const strategiesQuery = useQuery({
    queryKey: ["reply-strategies"],
    queryFn: fetchReplyStrategies
  });
  const defaultSkillQuery = useQuery({
    queryKey: ["reply-strategies", "default-skill"],
    queryFn: fetchDefaultReplySkill
  });
  const strategies = strategiesQuery.data ?? [];
  const activeStrategy = useMemo(() => strategies.find((strategy) => strategy.is_active), [strategies]);
  const [selectedStrategyId, setSelectedStrategyId] = useState<number | "new">("new");
  const selectedStrategy =
    selectedStrategyId === "new"
      ? null
      : strategies.find((strategy) => strategy.id === selectedStrategyId) ?? null;
  const [form, setForm] = useState<ReplyStrategyPayload>(defaultForm);

  useEffect(() => {
    if (selectedStrategy) {
      setForm(strategyToForm(selectedStrategy));
      return;
    }
    if (defaultSkillQuery.data?.content) {
      setForm((current) =>
        current.skill_content
          ? current
          : {
              ...current,
              skill_content: defaultSkillQuery.data.content
            }
      );
    }
  }, [defaultSkillQuery.data?.content, selectedStrategy]);

  const saveMutation = useMutation({
    mutationFn: () =>
      selectedStrategy
        ? updateReplyStrategy(selectedStrategy.id, form)
        : createReplyStrategy({ ...form, is_active: form.is_active ?? false }),
    onSuccess: (strategy) => {
      setSelectedStrategyId(strategy.id);
      void queryClient.invalidateQueries({ queryKey: ["reply-strategies"] });
    }
  });

  const activateMutation = useMutation({
    mutationFn: (strategyId: number) => activateReplyStrategy(strategyId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reply-strategies"] });
    }
  });

  function startNewStrategy() {
    setSelectedStrategyId("new");
    setForm({
      ...defaultForm,
      name: `回复 Skill ${strategies.length + 1}`,
      is_active: false,
      skill_content: defaultSkillQuery.data?.content ?? ""
    });
  }

  function updateForm<K extends keyof ReplyStrategyPayload>(key: K, value: ReplyStrategyPayload[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:py-8 xl:px-8">
      <section className="app-card p-5 sm:p-6">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              Reply Skill
            </div>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950 xl:text-4xl">
              回复 Skill 配置
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
              直接维护完整 Skill 文档。AI 生成回复时会把当前激活版本连同评论上下文一起发送给阿里云模型。
            </p>
          </div>
          <div className="soft-panel p-4">
            <p className="text-xs text-slate-500">当前生效版本</p>
            <p className="mt-2 text-lg font-semibold text-slate-950">
              {activeStrategy?.name ?? "尚未设置"}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {activeStrategy ? `v${activeStrategy.version} · ${activeStrategy.model_name}` : "保存并激活后生效"}
            </p>
          </div>
        </div>
      </section>

      <section className="mt-5 grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="app-card p-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-950">Skill 版本</h2>
              <p className="mt-1 text-xs text-slate-500">选择已有版本或新建。</p>
            </div>
            <Button type="button" variant="outline" onClick={startNewStrategy}>
              <Plus className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>
          <div className="mt-4 space-y-2">
            {strategies.map((strategy) => (
              <button
                key={strategy.id}
                type="button"
                className={
                  selectedStrategyId === strategy.id
                    ? "w-full rounded-2xl border border-blue-200 bg-blue-50/80 p-4 text-left shadow-sm"
                    : "w-full rounded-2xl border border-slate-200 bg-white p-4 text-left transition hover:border-blue-200 hover:bg-blue-50/30"
                }
                onClick={() => setSelectedStrategyId(strategy.id)}
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="font-semibold text-slate-950">{strategy.name}</p>
                  {strategy.is_active ? <span className="badge-green px-2.5">Active</span> : null}
                </div>
                <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-500">
                  {strategy.description || "未填写说明"}
                </p>
                <p className="mt-3 text-xs text-slate-400">v{strategy.version} · {strategy.model_name}</p>
              </button>
            ))}
            <button
              type="button"
              className={
                selectedStrategyId === "new"
                  ? "w-full rounded-2xl border border-blue-200 bg-blue-50/80 p-4 text-left shadow-sm"
                  : "w-full rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 p-4 text-left text-slate-500 transition hover:border-blue-200 hover:bg-blue-50/30"
              }
              onClick={startNewStrategy}
            >
              <p className="font-semibold">新建 Skill</p>
              <p className="mt-2 text-xs">以默认 Skill 文档为基础编辑。</p>
            </button>
          </div>
        </aside>

        <section className="app-card p-5">
          <div className="flex flex-col gap-4 border-b border-slate-100 pb-5 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-3">
              <div className="icon-tile">
                <FileCode2 className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-slate-950">
                  {selectedStrategy ? "编辑回复 Skill" : "新建回复 Skill"}
                </h2>
                <p className="mt-1 text-sm text-slate-500">保存会生成新的策略版本，草稿会记录使用时的 Skill 快照。</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {selectedStrategy && !selectedStrategy.is_active ? (
                <Button
                  type="button"
                  variant="outline"
                  disabled={activateMutation.isPending}
                  onClick={() => activateMutation.mutate(selectedStrategy.id)}
                >
                  <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                  设为 Active
                </Button>
              ) : null}
              <Button type="button" disabled={saveMutation.isPending} onClick={() => saveMutation.mutate()}>
                <Save className="h-4 w-4" aria-hidden="true" />
                {saveMutation.isPending ? "保存中..." : "保存 Skill"}
              </Button>
            </div>
          </div>

          <div className="mt-5 grid gap-5 xl:grid-cols-2">
            <Field label="Skill 名称">
              <input
                className="form-input"
                value={form.name}
                onChange={(event) => updateForm("name", event.target.value)}
              />
            </Field>
            <Field label="模型名称">
              <input
                className="form-input"
                value={form.model_name}
                onChange={(event) => updateForm("model_name", event.target.value)}
              />
            </Field>
            <Field label="说明" className="xl:col-span-2">
              <textarea
                className="form-textarea min-h-20"
                value={form.description ?? ""}
                onChange={(event) => updateForm("description", event.target.value)}
              />
            </Field>
            <Field label="温度">
              <input
                className="form-input"
                type="number"
                min={0}
                max={2}
                step={0.1}
                value={form.temperature ?? 0.4}
                onChange={(event) => updateForm("temperature", Number(event.target.value))}
              />
            </Field>
            <div className="soft-panel flex items-center justify-between p-4">
              <div>
                <p className="text-sm font-semibold text-slate-950">保存后立即激活</p>
                <p className="mt-1 text-xs text-slate-500">用于新建 Skill 时控制是否直接生效。</p>
              </div>
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                checked={Boolean(form.is_active)}
                onChange={(event) => updateForm("is_active", event.target.checked)}
              />
            </div>
            <Field label="Skill 文档" className="xl:col-span-2">
              <textarea
                className="form-textarea min-h-[32rem] font-mono text-xs leading-6"
                value={form.skill_content}
                onChange={(event) => updateForm("skill_content", event.target.value)}
              />
            </Field>
          </div>
        </section>
      </section>
    </main>
  );
}

function Field({
  label,
  className = "",
  children
}: {
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <label className={`flex flex-col gap-2 ${className}`}>
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      {children}
    </label>
  );
}

function strategyToForm(strategy: ReplyStrategy): ReplyStrategyPayload {
  return {
    name: strategy.name,
    description: strategy.description,
    skill_content: strategy.skill_content,
    model_name: strategy.model_name,
    temperature: strategy.temperature,
    is_active: strategy.is_active
  };
}

export const replyStrategiesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/reply-strategies",
  component: ReplyStrategiesPage
});
