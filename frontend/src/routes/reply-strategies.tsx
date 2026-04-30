import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import { CheckCircle2, FileText, Plus, Save, Settings2, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  activateReplyStrategy,
  createReplyStrategy,
  fetchReplyStrategies,
  updateReplyStrategy,
  type ReplyExample,
  type ReplyStrategy,
  type ReplyStrategyPayload
} from "@/lib/api";
import { rootRoute } from "@/routes/__root";

const emptyExample: ReplyExample = { title: "", review: "", reply: "" };

const defaultStrategyForm: ReplyStrategyPayload = {
  name: "默认回复策略",
  description: "用于 Steam 评论的开发者回复策略。",
  prompt_template:
    "请基于以下 Steam 用户评论生成一条开发者回复。要求真诚、克制、具体，不攻击用户，不承诺无法兑现的内容。\n\n评论内容：{review_text}",
  reply_rules: "1. 先感谢用户反馈。\n2. 对负面体验表达理解。\n3. 给出清晰解释或后续改进方向。\n4. 语气自然，不要模板化。",
  forbidden_terms: ["攻击用户", "阴阳怪气", "承诺具体上线日期", "过度营销"],
  good_examples: [
    {
      title: "高赞差评安抚",
      review: "剧情后面有点突兀，体验变差了。",
      reply: "感谢你认真反馈。我们会继续复盘后段剧情的节奏和铺垫，也会把这类体验问题纳入后续优化讨论。"
    }
  ],
  brand_voice: "真诚、克制、友好、尊重玩家，不争辩，不甩锅。",
  classification_strategy: "优先处理高赞差评、长文本差评、包含明确问题建议的评论。",
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
  const strategies = strategiesQuery.data ?? [];
  const activeStrategy = useMemo(() => strategies.find((strategy) => strategy.is_active), [strategies]);
  const [selectedStrategyId, setSelectedStrategyId] = useState<number | "new">("new");
  const selectedStrategy =
    selectedStrategyId === "new"
      ? null
      : strategies.find((strategy) => strategy.id === selectedStrategyId) ?? null;
  const [form, setForm] = useState<ReplyStrategyPayload>(defaultStrategyForm);

  useEffect(() => {
    if (selectedStrategy) {
      setForm(strategyToForm(selectedStrategy));
    }
  }, [selectedStrategy]);

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
    setForm({ ...defaultStrategyForm, name: `回复策略 ${strategies.length + 1}`, is_active: false });
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
              阶段 4 · Strategy Configuration
            </div>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950 xl:text-4xl">
              回复策略配置
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
              配置 AI 回复规则、禁忌项、优秀案例、品牌调性和分类策略。后续生成草稿会记录当时使用的策略版本。
            </p>
          </div>
          <div className="soft-panel p-4">
            <p className="text-xs text-slate-500">当前 Active 策略</p>
            <p className="mt-2 text-lg font-semibold text-slate-950">
              {activeStrategy?.name ?? "尚未设置"}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {activeStrategy ? `v${activeStrategy.version} · ${activeStrategy.model_name}` : "保存并激活一个策略后生效"}
            </p>
          </div>
        </div>
      </section>

      <section className="mt-5 grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="app-card p-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-950">策略版本</h2>
              <p className="mt-1 text-xs text-slate-500">选择已有策略或新建版本。</p>
            </div>
            <Button type="button" variant="outline" onClick={startNewStrategy}>
              <Plus className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>
          <div className="mt-4 space-y-2">
            {strategiesQuery.isLoading ? (
              <p className="soft-panel p-4 text-sm text-slate-500">加载策略中...</p>
            ) : null}
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
                  {strategy.is_active ? (
                    <span className="badge-green px-2.5">
                      Active
                    </span>
                  ) : null}
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
              <p className="font-semibold">新建策略</p>
              <p className="mt-2 text-xs">从默认模板开始编辑。</p>
            </button>
          </div>
        </aside>

        <section className="app-card p-5">
          <div className="flex flex-col gap-4 border-b border-slate-100 pb-5 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-3">
              <div className="icon-tile">
                <Settings2 className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-slate-950">
                  {selectedStrategy ? "编辑回复策略" : "新建回复策略"}
                </h2>
                <p className="mt-1 text-sm text-slate-500">保存后会形成新的策略版本号。</p>
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
                保存策略
              </Button>
            </div>
          </div>

          <div className="mt-5 grid gap-5 xl:grid-cols-2">
            <Field label="策略名称">
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
            <Field label="策略说明" className="xl:col-span-2">
              <textarea
                className="form-textarea min-h-20"
                value={form.description ?? ""}
                onChange={(event) => updateForm("description", event.target.value)}
              />
            </Field>
            <Field label="Prompt 模板" className="xl:col-span-2">
              <textarea
                className="form-textarea min-h-44 font-mono text-xs"
                value={form.prompt_template}
                onChange={(event) => updateForm("prompt_template", event.target.value)}
              />
            </Field>
            <Field label="回复规则">
              <textarea
                className="form-textarea min-h-36"
                value={form.reply_rules ?? ""}
                onChange={(event) => updateForm("reply_rules", event.target.value)}
              />
            </Field>
            <Field label="品牌调性">
              <textarea
                className="form-textarea min-h-36"
                value={form.brand_voice ?? ""}
                onChange={(event) => updateForm("brand_voice", event.target.value)}
              />
            </Field>
            <Field label="分类策略">
              <textarea
                className="form-textarea min-h-32"
                value={form.classification_strategy ?? ""}
                onChange={(event) => updateForm("classification_strategy", event.target.value)}
              />
            </Field>
            <Field label="禁忌项">
              <textarea
                className="form-textarea min-h-32"
                value={(form.forbidden_terms ?? []).join("\\n")}
                onChange={(event) => updateForm("forbidden_terms", splitLines(event.target.value))}
              />
            </Field>
            <Field label="优秀案例" className="xl:col-span-2">
              <ExamplesEditor
                examples={form.good_examples ?? []}
                onChange={(examples) => updateForm("good_examples", examples)}
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

function ExamplesEditor({
  examples,
  onChange
}: {
  examples: ReplyExample[];
  onChange: (examples: ReplyExample[]) => void;
}) {
  const normalizedExamples = examples.length > 0 ? examples : [emptyExample];

  function updateExample(index: number, key: keyof ReplyExample, value: string) {
    onChange(
      normalizedExamples.map((example, itemIndex) =>
        itemIndex === index ? { ...example, [key]: value } : example
      )
    );
  }

  return (
    <div className="space-y-3">
      {normalizedExamples.map((example, index) => (
        <div key={index} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <FileText className="h-4 w-4 text-blue-600" aria-hidden="true" />
            案例 {index + 1}
          </div>
          <div className="mt-3 grid gap-3 lg:grid-cols-3">
            <input
              className="form-input"
              placeholder="标题"
              value={example.title}
              onChange={(event) => updateExample(index, "title", event.target.value)}
            />
            <textarea
              className="form-textarea min-h-24"
              placeholder="用户评论"
              value={example.review}
              onChange={(event) => updateExample(index, "review", event.target.value)}
            />
            <textarea
              className="form-textarea min-h-24"
              placeholder="优秀回复"
              value={example.reply}
              onChange={(event) => updateExample(index, "reply", event.target.value)}
            />
          </div>
        </div>
      ))}
      <Button type="button" variant="outline" onClick={() => onChange([...normalizedExamples, emptyExample])}>
        <Plus className="h-4 w-4" aria-hidden="true" />
        添加案例
      </Button>
    </div>
  );
}

function strategyToForm(strategy: ReplyStrategy): ReplyStrategyPayload {
  return {
    name: strategy.name,
    description: strategy.description,
    prompt_template: strategy.prompt_template,
    reply_rules: strategy.reply_rules,
    forbidden_terms: strategy.forbidden_terms ?? [],
    good_examples: strategy.good_examples ?? [],
    brand_voice: strategy.brand_voice,
    classification_strategy: strategy.classification_strategy,
    model_name: strategy.model_name,
    temperature: strategy.temperature,
    is_active: strategy.is_active
  };
}

function splitLines(value: string): string[] {
  return value
    .split("\\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

export const replyStrategiesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/reply-strategies",
  component: ReplyStrategiesPage
});
