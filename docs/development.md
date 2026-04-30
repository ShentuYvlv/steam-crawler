# Steam 评论 AI 回复后台开发说明

## 当前阶段

本阶段只建立本地 Web 后台的工程基线，不改动现有 Steam 爬虫主流程。后续会按执行计划逐步接入评论存量导入、增量同步、AI 草稿、人工审核、开发者回复和统计。

## 目录

- `backend/`：FastAPI + SQLAlchemy 2.x async + Alembic 后端。
- `frontend/`：React + Vite + TypeScript 前端。
- `docker-compose.yml`：后端、前端本地联调环境；PostgreSQL 和 Redis 使用宿主机服务。
- `docs/plans/2026-04-29-steam-review-automation-execution-plan.md`：完整分阶段执行计划。

## 本地启动

1. 复制环境变量模板：

   ```bash
   cp .env.example .env
   ```

2. 按需填写：

   - `JWT_SECRET_KEY`：本地随机长字符串。
   - `ALIYUN_API_KEY`：阿里云模型 API Key，接入 AI 草稿阶段才必需。
   - `STEAM_COOKIE_FILE`：开发者回复阶段需要，默认读取 `data/steam_cookie.txt`。

3. 确保宿主机 PostgreSQL 和 Redis 已启动，且 `.env` 中的 `DATABASE_URL`、`REDIS_URL` 可连接。

4. 启动前后端服务：

   ```bash
   docker compose up --build
   ```

5. 健康检查：

   ```bash
   curl http://localhost:8000/api/health
   ```

## 数据约定

- 首次导入 `data/情感反诈模拟器-steam评论 - 全部评论.csv`，统一标记为存量数据。
- 后续 Steam API 同步只抓取最新增量评论，避免重复处理全部历史评论。
- 删除诉求先记录为待处理业务状态，不直接调用 Steam 删除接口。

## 存量 CSV 导入

先执行数据库迁移：

```bash
cd backend
alembic upgrade head
```

导入当前全部评论 CSV：

```bash
cd backend
python -m app.cli.import_stock_reviews \
  --file "../data/情感反诈模拟器-steam评论 - 全部评论.csv" \
  --app-id 3350200
```

如果只想验证字段解析，不写入数据库：

```bash
cd backend
python -m app.cli.import_stock_reviews \
  --file "../data/情感反诈模拟器-steam评论 - 全部评论.csv" \
  --app-id 3350200 \
  --limit 10 \
  --dry-run
```

## Steam 增量同步

后端已封装现有 `src.scrapers.comment_scraper.CommentScraper`，不会重新实现 Steam 请求逻辑。手动同步接口：

```bash
curl -X POST http://localhost:8000/api/reviews/sync \
  -H "Content-Type: application/json" \
  -d '{
    "app_id": 3350200,
    "limit": 100,
    "language": "schinese",
    "filter": "recent",
    "review_type": "all",
    "purchase_type": "all",
    "use_review_quality": true,
    "per_page": 100
  }'
```

查询同步任务：

```bash
curl http://localhost:8000/api/reviews/sync-jobs
curl http://localhost:8000/api/reviews/sync-jobs/1
```

同步结果写入 `steam_reviews`，新增数据标记为 `sync_type=incremental`、`source_type=steam_api`，并继续使用 `recommendation_id` 去重。

## 评论列表与筛选

评论后台页面：

```bash
http://localhost:5173/reviews
```

后端查询接口：

```bash
curl "http://localhost:8000/api/reviews?app_id=3350200&voted_up=false&keyword=差评&sort_by=votes_up&sort_order=desc&page=1&page_size=50"
curl http://localhost:8000/api/reviews/1
```

状态标记接口：

```bash
curl -X PATCH http://localhost:8000/api/reviews/1/status \
  -H "Content-Type: application/json" \
  -d '{"processing_status":"on_hold"}'

curl -X POST http://localhost:8000/api/reviews/bulk-status \
  -H "Content-Type: application/json" \
  -d '{"review_ids":[1,2,3],"processing_status":"ignored"}'
```

## 回复策略配置

策略配置页面：

```bash
http://localhost:5173/reply-strategies
```

后端接口：

```bash
curl http://localhost:8000/api/reply-strategies
curl http://localhost:8000/api/reply-strategies/active
curl -X POST http://localhost:8000/api/reply-strategies/1/activate
```

策略字段包括 Prompt 模板、回复规则、禁忌项、优秀案例、品牌调性、分类策略、模型名称和温度。每次编辑保存会递增 `version`，后续 AI 草稿会记录当时使用的策略版本。

## AI 回复草稿生成

生成草稿前必须配置：

- `ALIYUN_API_KEY`：阿里云 DashScope 兼容 OpenAI 模式 API Key。
- `ALIYUN_MODEL`：默认 `qwen-plus`，也可在回复策略里按策略覆盖模型名称。
- 至少存在一个已启用回复策略。

单条生成：

```bash
curl -X POST http://localhost:8000/api/reviews/1/generate-reply
```

批量生成：

```bash
curl -X POST http://localhost:8000/api/reviews/bulk-generate-reply \
  -H "Content-Type: application/json" \
  -d '{"review_ids":[1,2,3]}'
```

查询草稿：

```bash
curl http://localhost:8000/api/reply-drafts/1
```

生成结果会写入 `reply_drafts`，状态为 `pending_review`；生成失败会写入 `generation_failed` 草稿并记录 `error_message`，不会自动发送到 Steam。

## 审核、发送与回复记录

评论详情展开后会显示 AI 回复审核区。发送前必须人工点击确认，后端才会读取 `STEAM_COOKIE_FILE` 并调用 Steam Community 的 `setdeveloperresponse/{recommendationid}`。

核心接口：

```bash
curl -X PATCH http://localhost:8000/api/reply-drafts/1 \
  -H "Content-Type: application/json" \
  -d '{"content":"修改后的回复草稿"}'

curl -X POST http://localhost:8000/api/reviews/1/send-reply \
  -H "Content-Type: application/json" \
  -d '{"draft_id":1,"confirmed":true}'

curl http://localhost:8000/api/reply-records

curl -X POST http://localhost:8000/api/reply-records/1/delete-request \
  -H "Content-Type: application/json" \
  -d '{"confirmed":true,"reason":"运营后台记录删除诉求"}'
```

删除请求只写入本地数据库，不实际调用 Steam 删除接口。

## 任务与定时同步

任务页面：

```bash
http://localhost:5173/tasks
```

当前版本使用 FastAPI 后台任务承接手动同步，接口和数据结构已按后续 Redis/arq 队列迁移预留。

```bash
curl http://localhost:8000/api/tasks

curl -X POST http://localhost:8000/api/tasks/reviews-sync \
  -H "Content-Type: application/json" \
  -d '{"app_id":3350200,"limit":100,"language":"schinese","filter":"recent"}'

curl -X PATCH http://localhost:8000/api/tasks/schedule \
  -H "Content-Type: application/json" \
  -d '{"is_enabled":true,"app_id":3350200,"interval":"hourly","minute":0,"options":{"limit":100}}'
```

已发送回复页面：

```bash
http://localhost:5173/reply-records
```

## 约束

- 发送开发者回复必须经过人工审核。
- Steam Cookie 仅保存在本地环境或本地文件，不提交到 Git。
- 当前阶段暂不接入飞书数据源。
- 登录账号体系待留言板后台确认后再实现。
