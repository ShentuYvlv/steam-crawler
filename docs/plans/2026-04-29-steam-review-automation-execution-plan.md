# Steam 评论 AI 回复后台系统执行计划

版本：V1.0  
日期：2026-04-29  
范围：本地 Web 后台，逐步演进到可部署的内部系统

## 1. 目标

基于现有 Steam 评论抓取和开发者回复能力，建设一个内部 Web 后台，实现：

- 抓取指定游戏下的 Steam 用户评论。
- 将评论结构化入库，支持存量导入和增量同步。
- 使用阿里云 API 生成 AI 回复草稿。
- 运营在后台审核、修改、通过后，系统再调用 Steam 开发者回复接口发送。
- 所有发送、修改、忽略、失败、删除申请等动作可追溯。
- 遵守“AI 辅助，人工把关”的原则，不做全自动发送。

## 2. 技术栈

前端：

- React + Vite + TypeScript
- Tailwind CSS v4
- shadcn/ui + Radix UI
- TanStack Router
- TanStack Query
- Zustand
- React Hook Form + Zod
- Recharts 或 ECharts
- Playwright

后端：

- FastAPI
- SQLAlchemy 2.x async
- Alembic
- PostgreSQL
- Redis
- Celery 或 arq
- Pytest

部署：

- Docker Compose
- Nginx
- GitHub Actions

权限：

- JWT + RBAC
- 登录体系暂缓，等待确认是否接入现有留言板后台账号体系。

## 3. 总体架构

系统分为五层：

1. 前端后台：评论列表、筛选、详情、AI 草稿、审核发送、策略配置、统计。
2. 后端 API：认证、评论、AI 草稿、审核、发送、策略、统计、任务调度。
3. 数据层：PostgreSQL 存储评论、草稿、发送记录、策略、操作日志。
4. 异步任务层：Redis + Celery 或 arq 处理抓取、AI 批量生成、Steam 发送、定时同步。
5. 外部集成层：Steam 评论接口、Steam Community 开发者回复接口、阿里云 AI API。

## 4. 数据模型规划

### 4.1 users

用于后续接入登录体系和 RBAC。

字段：

- id
- username
- password_hash 或 external_user_id
- display_name
- role
- is_active
- created_at
- updated_at

第一阶段可以保留表结构，不启用完整登录。

### 4.2 steam_games

字段：

- app_id
- name
- release_date
- price
- developers
- publishers
- genres
- description
- created_at
- updated_at

可迁移或复用现有游戏基础信息逻辑。

### 4.3 steam_reviews

字段：

- id
- app_id
- recommendation_id
- steam_id
- persona_name
- profile_url
- language
- review_text
- voted_up
- votes_up
- votes_funny
- weighted_vote_score
- comment_count
- steam_purchase
- received_for_free
- refunded
- playtime_forever
- playtime_at_review
- playtime_last_two_weeks
- timestamp_created
- timestamp_updated
- last_played
- sync_type
- official_response_status
- official_response_text
- process_status
- raw_payload
- created_at
- updated_at

唯一索引：

- app_id + recommendation_id

状态建议：

- pending_generation
- draft_ready
- pending_review
- sent
- ignored
- tentative
- send_failed
- delete_requested

### 4.4 ai_reply_drafts

字段：

- id
- review_id
- prompt_version
- strategy_version
- model_provider
- model_name
- prompt
- draft_text
- status
- generated_by
- generated_at
- edited_text
- edited_by
- edited_at
- created_at
- updated_at

状态建议：

- generated
- edited
- approved
- rejected
- superseded

### 4.5 reply_strategies

字段：

- id
- name
- rules_text
- taboo_text
- examples_text
- brand_voice_text
- category_strategy_text
- version
- is_active
- created_by
- created_at
- updated_at

### 4.6 steam_reply_records

字段：

- id
- review_id
- draft_id
- recommendation_id
- response_text
- steam_response_payload
- send_status
- error_message
- sent_by
- sent_at
- created_at

状态建议：

- success
- failed
- retrying

### 4.7 operation_logs

字段：

- id
- actor_id
- actor_name
- action
- target_type
- target_id
- before_payload
- after_payload
- created_at

### 4.8 sync_jobs

字段：

- id
- job_type
- app_id
- status
- started_at
- finished_at
- total_count
- success_count
- failed_count
- error_message
- created_at

## 5. 阶段计划

## 阶段 0：项目脚手架与工程基线

目标：

建立前后端工程结构、Docker Compose、本地开发流程和基础质量检查。

任务：

- 新建 `backend/` FastAPI 项目。
- 新建 `frontend/` Vite + React + TypeScript 项目。
- 配置 PostgreSQL、Redis、后端服务、前端服务的 Docker Compose。
- 配置 Alembic。
- 配置 Ruff 或后端基础格式检查。
- 配置前端 ESLint、TypeScript、Tailwind CSS v4、shadcn/ui。
- 配置基础 GitHub Actions。

交付物：

- `backend/`
- `frontend/`
- `docker-compose.yml`
- `.env.example`
- Alembic 初始化文件
- 前端基础布局和路由入口

验收标准：

- `docker compose up` 能启动 PostgreSQL、Redis、backend、frontend。
- 后端 `/health` 返回正常。
- 前端能打开本地后台首页。
- Alembic 能创建空数据库迁移。

## 阶段 1：数据库模型与迁移

目标：

建立核心数据表，为抓取、AI 生成、审核发送提供数据基础。

任务：

- 定义 SQLAlchemy async models。
- 创建 Alembic migration。
- 实现数据库 session 管理。
- 实现基础 Repository 或 Service 层。
- 给 `steam_reviews` 添加唯一约束和常用查询索引。
- 添加基础 Pytest 数据库测试。

交付物：

- 游戏表
- 评论表
- AI 草稿表
- 策略表
- 发送记录表
- 操作日志表
- 同步任务表

验收标准：

- Alembic upgrade 成功。
- Pytest 能验证评论 upsert、状态流转、发送记录写入。

## 阶段 2：评论抓取入库

目标：

将当前 CLI 的 `comments` 抓取能力迁移为后端服务，写入 PostgreSQL。

已有存量数据源：

- `data/情感反诈模拟器-steam评论 - 全部评论.csv`
- 该文件是当前已汇总的全部评论，第一版应优先导入该 CSV。
- 导入时统一标记为 `sync_type=stock` 或 `source_type=stock`。
- 后续 Steam 同步只抓取最新新增评论，新增评论标记为 `sync_type=incremental` 或 `source_type=incremental`。
- CSV 中已有字段包括 ID、SteamID、评论链接、拥有游戏数、发表测评数量、总游戏时长、两周游戏时长、评论时游戏时长、最后游玩时间、语言、评论内容、创建时间、更新时间、正面评价、有用票数、有趣票数、参考价值分、回复数、Steam购买、免费获取、抢先体验评论、开发者回复、开发者回复时间。

任务：

- 实现 CSV 存量评论导入命令或后台导入任务。
- 建立 CSV 字段到 `steam_reviews` 字段的映射。
- 复用当前 `ajaxappreviews` 请求逻辑。
- 实现按 app_id 抓取最新评论。
- 后续同步默认只做增量抓取，不再全量重爬全部历史评论。
- 支持按 limit 抓取。
- 支持筛选参数：language、filter、review_type、purchase_type、use_review_quality、per_page。
- 实现评论 upsert。
- 使用 `recommendation_id` 或 CSV 中的 ID 做唯一去重。
- 记录 sync_jobs。
- 添加手动同步 API。
- 添加后台任务版本的同步接口。

接口草案：

- `POST /api/reviews/sync`
- `GET /api/reviews/sync-jobs`
- `GET /api/reviews/sync-jobs/{id}`

验收标准：

- 指定 app_id 后能抓取评论并写入数据库。
- `data/情感反诈模拟器-steam评论 - 全部评论.csv` 可一次性导入数据库，且导入数据标记为存量。
- 导入后的存量评论不会在后续增量同步中重复插入。
- 后续同步只拉取新增评论并标记为增量。
- 重复抓取不会产生重复评论。
- 失败时有 sync_jobs 记录和错误信息。
- 不需要 Cookie。

## 阶段 3：评论列表与筛选后台

目标：

运营可以在 Web 后台浏览、搜索、筛选、排序评论。

任务：

- 前端搭建 App Shell。
- 实现评论列表页。
- 实现评论详情侧栏或详情页。
- 支持筛选：好评/差评、点赞数范围、发布时间范围、游玩时长范围、处理状态、关键词。
- 支持排序：点赞数、发布时间、游玩时长。
- 支持分页。
- 支持多选。
- 支持标记待定、忽略。
- 后端实现查询 API。

接口草案：

- `GET /api/reviews`
- `GET /api/reviews/{id}`
- `PATCH /api/reviews/{id}/status`
- `POST /api/reviews/bulk-status`

验收标准：

- 5 万条评论规模下分页查询可用。
- 常用筛选响应时间目标小于 2 秒。
- 多选批量标记状态成功。

## 阶段 4：回复策略配置

目标：

运营可以在后台编辑 AI 回复策略，并影响后续生成的草稿。

任务：

- 实现策略配置页面。
- 支持编辑回复规则、禁忌项、优秀案例、品牌调性、分类策略。
- 支持保存版本。
- 当前 active 策略用于后续 AI 生成。
- 已生成草稿保留当时使用的策略版本。

接口草案：

- `GET /api/reply-strategies/active`
- `POST /api/reply-strategies`
- `PATCH /api/reply-strategies/{id}`
- `POST /api/reply-strategies/{id}/activate`

验收标准：

- 运营可编辑并保存策略。
- 新生成草稿记录使用的策略版本。
- 已生成草稿不受新策略变更影响。

## 阶段 5：阿里云 AI 生成回复

目标：

接入阿里云 API，根据评论和策略生成回复草稿。

任务：

- 封装阿里云 API Client。
- 设计 prompt 模板。
- 输入包括评论原文、评价类型、游玩时长、点赞数、策略文档。
- 支持单条生成。
- 支持批量生成，进入队列。
- 记录 prompt、模型、策略版本、生成结果。
- 失败可重试。

接口草案：

- `POST /api/reviews/{id}/generate-reply`
- `POST /api/reviews/bulk-generate-reply`
- `GET /api/reply-drafts/{id}`

验收标准：

- 单条评论可生成草稿。
- 批量生成不会阻塞 Web 请求。
- 草稿进入待审核状态。
- AI 调用失败有错误记录。

## 阶段 6：审核与发送

目标：

运营审核 AI 草稿后，人工确认发送到 Steam。

任务：

- 实现评论详情里的回复审核区。
- 支持通过并发送。
- 支持修改后发送。
- 支持重新生成。
- 支持待定。
- 发送前二次确认。
- 后端调用 Steam `setdeveloperresponse/{recommendationid}`。
- Cookie 从本地文件读取。
- 发送结果写入 `steam_reply_records`。
- 评论状态更新为已发送或发送失败。

接口草案：

- `POST /api/reviews/{id}/send-reply`
- `POST /api/reviews/{id}/regenerate-reply`
- `POST /api/reviews/bulk-send-reply`
- `GET /api/reply-records`

验收标准：

- 不允许 AI 生成后自动发送。
- 发送前必须有人工确认。
- 发送成功后记录 Steam 返回结果。
- 发送失败可查看原因并重试。

## 阶段 7：定时同步与任务队列

目标：

支持手动同步和定时增量同步。

任务：

- 选择 Celery 或 arq。
- 实现 Redis 队列。
- 实现定时任务配置。
- 支持每小时或每日同步。
- 实现任务状态查询。
- 后台页面展示最近同步任务。

接口草案：

- `GET /api/tasks`
- `POST /api/tasks/reviews-sync`
- `PATCH /api/tasks/schedule`

验收标准：

- 可以手动触发同步。
- 可以配置定时同步。
- 后台能看到任务状态、成功数、失败数。

## 阶段 8：已发送回复管理

目标：

展示已发送回复，支持记录删除请求，但不实际调用 Steam 删除。

任务：

- 实现已发送回复列表。
- 展示原评论、回复内容、发送时间、操作人、发送状态。
- 支持创建删除请求。
- 删除请求只写入数据库，不调用 Steam。
- 删除请求需要二次确认。

接口草案：

- `GET /api/reply-records`
- `POST /api/reply-records/{id}/delete-request`

验收标准：

- 已发送记录可查询。
- 删除请求可创建和审计。
- 不实际删除 Steam 上的回复。

## 阶段 9：统计面板

目标：

为运营提供整体进度和质量指标。

任务：

- 评论总数。
- 好评/差评数量。
- 已回复数。
- 待处理数。
- 已忽略数。
- 当前好评率。
- 回复发送成功率。
- 按时间维度展示新增评论和回复数量。

接口草案：

- `GET /api/stats/overview`
- `GET /api/stats/timeseries`

验收标准：

- 首页可展示核心统计。
- 统计与数据库状态一致。

## 阶段 10：登录、RBAC 与操作日志

目标：

接入或实现登录体系，并记录关键操作。

当前决策：

- 登录体系暂缓。
- 等待确认是否复用公司留言板审核后台账号体系。

预留方案：

- 方案 A：接入现有账号体系。
- 方案 B：本系统独立账号密码登录。

任务：

- JWT 登录。
- RBAC 权限。
- 操作日志中记录 actor。
- 前端根据权限隐藏或禁用操作。

验收标准：

- 运营人员和技术人员权限区分。
- 发送、修改、忽略、删除请求都有操作日志。

## 阶段 11：测试与部署

目标：

形成可部署、可回归的工程闭环。

任务：

- Pytest 覆盖后端核心服务。
- Playwright 覆盖核心用户流程。
- Docker Compose 完整部署。
- Nginx 反向代理。
- GitHub Actions 跑测试和构建。
- 生产环境变量模板。

核心 E2E 流程：

1. 手动同步评论。
2. 筛选差评。
3. 单条生成 AI 草稿。
4. 修改草稿。
5. 审核发送。
6. 查看发送记录。
7. 查看统计变化。

验收标准：

- 一键启动本地开发环境。
- 关键流程有自动化测试。
- 部署文档清晰。

## 6. 推荐里程碑

### 里程碑 1：本地后台可启动

包含阶段 0、1。

结果：

- 前后端工程成型。
- PostgreSQL、Redis、FastAPI、React 能跑通。
- 数据库迁移可用。

### 里程碑 2：评论数据入库与浏览

包含阶段 2、3。

结果：

- 指定游戏评论可抓取入库。
- 后台可筛选和查看评论。

### 里程碑 3：AI 草稿生成

包含阶段 4、5。

结果：

- 策略可编辑。
- 评论可生成 AI 回复草稿。

### 里程碑 4：审核发送闭环

包含阶段 6。

结果：

- 运营人工审核后可发送 Steam 开发者回复。
- 发送结果可追踪。

### 里程碑 5：运营效率增强

包含阶段 7、8、9。

结果：

- 定时同步。
- 已发送管理。
- 统计面板。

### 里程碑 6：权限与部署

包含阶段 10、11。

结果：

- 登录和权限接入。
- Docker Compose 和 CI 可用。

## 7. 当前待确认事项

1. 登录是否复用留言板后台账号体系。
2. 阿里云 API 具体产品、模型名、调用方式、鉴权配置。
3. Steam Cookie 是否长期使用本地文件，还是后续做安全配置管理。
4. 第一版是否允许批量通过并发送，还是先只做单条发送。
5. AI 回复策略的初始内容由谁提供。
6. 增量同步的默认频率：每小时或每天。
7. `data/情感反诈模拟器-steam评论 - 全部评论.csv` 的字段是否完全以当前文件为准，后续是否还会新增列。

## 8. 第一阶段建议执行顺序

如果开始编码，建议先做以下最小闭环：

1. 创建 `backend/` 和 `frontend/` 工程。
2. 建立 Docker Compose：PostgreSQL、Redis、backend、frontend。
3. 建立 SQLAlchemy models 和 Alembic migration。
4. 先导入 `data/情感反诈模拟器-steam评论 - 全部评论.csv`，写入 PostgreSQL 并标记为存量。
5. 把当前 `comments` 抓取能力迁移到后端，只用于后续新增评论同步。
6. 做一个最小评论列表页。
7. 接入单条 AI 生成草稿。
8. 接入单条人工确认发送。

这个顺序能最快验证“抓取 → 展示 → AI → 审核 → 发送”的核心业务闭环。
