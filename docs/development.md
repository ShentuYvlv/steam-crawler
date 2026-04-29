# Steam 评论 AI 回复后台开发说明

## 当前阶段

本阶段只建立本地 Web 后台的工程基线，不改动现有 Steam 爬虫主流程。后续会按执行计划逐步接入评论存量导入、增量同步、AI 草稿、人工审核、开发者回复和统计。

## 目录

- `backend/`：FastAPI + SQLAlchemy 2.x async + Alembic 后端。
- `frontend/`：React + Vite + TypeScript 前端。
- `docker-compose.yml`：PostgreSQL、Redis、后端、前端本地联调环境。
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

3. 启动基础服务：

   ```bash
   docker compose up --build
   ```

4. 健康检查：

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

## 约束

- 发送开发者回复必须经过人工审核。
- Steam Cookie 仅保存在本地环境或本地文件，不提交到 Git。
- 当前阶段暂不接入飞书数据源。
- 登录账号体系待留言板后台确认后再实现。
