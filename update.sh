#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

configure_defaults() {
  PROJECT_NAME_DEFAULT="$(basename "$ROOT_DIR" | tr '[:upper:]' '[:lower:]')"
  PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$PROJECT_NAME_DEFAULT}"
  BACKEND_SERVICE="${BACKEND_SERVICE:-backend}"
  FRONTEND_SERVICE="${FRONTEND_SERVICE:-frontend}"
  ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
  ADMIN_DISPLAY_NAME="${ADMIN_DISPLAY_NAME:-管理员}"
  ADMIN_ROLE="${ADMIN_ROLE:-admin}"
  STOCK_REVIEWS_APP_ID="${STOCK_REVIEWS_APP_ID:-3350200}"
  STOCK_REVIEWS_FILE="${STOCK_REVIEWS_FILE:-/app/data/情感反诈模拟器-steam评论 - 全部评论.csv}"
}

load_dotenv() {
  [[ -f .env ]] || return 0
  while IFS='=' read -r key value; do
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    [[ -z "${!key+x}" ]] || continue
    value="${value%$'\r'}"
    if [[ "$value" == \"*\" && "$value" == *\" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
      value="${value:1:${#value}-2}"
    fi
    export "$key=$value"
  done < <(grep -vE '^[[:space:]]*(#|$)' .env || true)
}

detect_compose() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)
    COMPOSE_IS_V1=0
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD=(docker-compose)
    COMPOSE_IS_V1=1
  else
    echo "未找到 docker compose/docker-compose" >&2
    exit 1
  fi
}

compose() {
  "${COMPOSE_CMD[@]}" -f docker-compose.yml "$@"
}

clean_for_compose_v1() {
  if [[ "${COMPOSE_IS_V1:-0}" -eq 1 ]]; then
    echo "检测到 docker-compose v1，执行兼容清理..."
    compose down --remove-orphans || true
    compose rm -f -s || true
    docker ps -a --filter "label=com.docker.compose.project=${PROJECT_NAME}" -q | xargs -r docker rm -f || true
    docker network rm "${PROJECT_NAME}_default" >/dev/null 2>&1 || true
  fi
}

run_migrations() {
  echo ">>> 执行数据库迁移"
  compose run --rm --no-deps "$BACKEND_SERVICE" \
    python -c "from alembic.config import main; main(argv=['-c','alembic.ini','upgrade','head'])"
}

admin_count() {
  compose run --rm --no-deps "$BACKEND_SERVICE" python -c '
import asyncio
from sqlalchemy import func, select
from app.core.database import AsyncSessionLocal
from app.models import User

async def main():
    async with AsyncSessionLocal() as session:
        count = await session.scalar(
            select(func.count(User.id)).where(User.role == "admin", User.is_active.is_(True))
        )
        print(count or 0)

asyncio.run(main())
'
}

ensure_admin() {
  echo ">>> 检查管理员账号"
  local count
  count="$(admin_count | tail -n 1 | tr -d '[:space:]')"
  if [[ "$count" =~ ^[0-9]+$ && "$count" -gt 0 ]]; then
    echo "已存在管理员账号，跳过创建。"
    return 0
  fi

  if [[ -z "${ADMIN_PASSWORD:-}" ]]; then
    echo "未检测到管理员账号，且未设置 ADMIN_PASSWORD。" >&2
    echo "请在 .env 或环境变量中设置 ADMIN_USERNAME/ADMIN_PASSWORD 后重新执行: ./update.sh no-pull" >&2
    exit 1
  fi

  compose run --rm --no-deps \
    -e ADMIN_USERNAME="$ADMIN_USERNAME" \
    -e ADMIN_PASSWORD="$ADMIN_PASSWORD" \
    -e ADMIN_DISPLAY_NAME="$ADMIN_DISPLAY_NAME" \
    -e ADMIN_ROLE="$ADMIN_ROLE" \
    "$BACKEND_SERVICE" sh -lc \
    'python -m app.cli.create_user --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD" --display-name "$ADMIN_DISPLAY_NAME" --role "$ADMIN_ROLE"'
}

review_count() {
  compose run --rm --no-deps \
    -e STOCK_REVIEWS_APP_ID="$STOCK_REVIEWS_APP_ID" \
    "$BACKEND_SERVICE" python -c '
import asyncio
import os
from sqlalchemy import func, select
from app.core.database import AsyncSessionLocal
from app.models import SteamReview

app_id = int(os.environ["STOCK_REVIEWS_APP_ID"])

async def main():
    async with AsyncSessionLocal() as session:
        count = await session.scalar(select(func.count(SteamReview.id)).where(SteamReview.app_id == app_id))
        print(count or 0)

asyncio.run(main())
'
}

ensure_stock_reviews() {
  echo ">>> 检查存量评论数据"
  local count
  count="$(review_count | tail -n 1 | tr -d '[:space:]')"
  if [[ "$count" =~ ^[0-9]+$ && "$count" -gt 0 ]]; then
    echo "App ${STOCK_REVIEWS_APP_ID} 已有 ${count} 条评论，跳过存量导入。"
    return 0
  fi

  if ! compose run --rm --no-deps \
    -e STOCK_REVIEWS_FILE="$STOCK_REVIEWS_FILE" \
    "$BACKEND_SERVICE" sh -lc 'test -f "$STOCK_REVIEWS_FILE"'; then
    echo "未找到存量评论文件: ${STOCK_REVIEWS_FILE}，跳过导入。"
    return 0
  fi

  compose run --rm --no-deps \
    -e STOCK_REVIEWS_FILE="$STOCK_REVIEWS_FILE" \
    -e STOCK_REVIEWS_APP_ID="$STOCK_REVIEWS_APP_ID" \
    "$BACKEND_SERVICE" sh -lc \
    'python -m app.cli.import_stock_reviews --file "$STOCK_REVIEWS_FILE" --app-id "$STOCK_REVIEWS_APP_ID"'
}

run_init() {
  run_migrations
  ensure_admin
  ensure_stock_reviews
}

usage() {
  cat <<'EOF'
用法:
  ./update.sh             # git pull + build + 迁移/初始化检查 + 重建启动
  ./update.sh full        # 同默认完整更新
  ./update.sh light       # git pull + 普通 build + 初始化检查 + 重建启动
  ./update.sh pull        # git pull + 不重建镜像，仅重启并初始化检查
  ./update.sh rebuild     # git pull + no-cache build + 初始化检查 + 重建启动
  ./update.sh no-migrate  # git pull + build + 重建启动，不迁移但仍检查管理员/存量数据
  ./update.sh no-init     # git pull + build + 迁移 + 重建启动，不做管理员/存量数据检查
  ./update.sh no-pull     # 不拉代码，只 build + 迁移/初始化检查 + 重建启动

关键环境变量:
  ADMIN_PASSWORD         首次创建管理员必填
  STOCK_REVIEWS_APP_ID   默认: 3350200
  STOCK_REVIEWS_FILE     默认: /app/data/情感反诈模拟器-steam评论 - 全部评论.csv
EOF
}

MODE="${1:-full}"
RUN_PULL=1
RUN_MIGRATE=1
RUN_INIT=1
NO_CACHE=0
ONLY_PULL_RESTART=0

case "$MODE" in
  full|light)
    ;;
  pull)
    ONLY_PULL_RESTART=1
    ;;
  rebuild)
    NO_CACHE=1
    ;;
  no-migrate)
    RUN_MIGRATE=0
    ;;
  no-init)
    RUN_INIT=0
    ;;
  no-pull)
    RUN_PULL=0
    ;;
  *)
    usage
    exit 1
    ;;
esac

load_dotenv
configure_defaults
detect_compose

if [[ "$RUN_PULL" -eq 1 ]]; then
  echo ">>> 拉取最新代码"
  git pull --ff-only
fi

if [[ "$ONLY_PULL_RESTART" -eq 1 ]]; then
  echo ">>> 不重建镜像，仅重启容器"
  clean_for_compose_v1
  compose up -d --force-recreate
else
  echo ">>> 构建镜像"
  if [[ "$NO_CACHE" -eq 1 ]]; then
    compose build --no-cache "$BACKEND_SERVICE" "$FRONTEND_SERVICE"
  else
    compose build "$BACKEND_SERVICE" "$FRONTEND_SERVICE"
  fi

  if [[ "$RUN_MIGRATE" -eq 1 ]]; then
    run_migrations
  fi

  echo ">>> 重建并启动容器"
  clean_for_compose_v1
  compose up -d --force-recreate
fi

if [[ "$RUN_INIT" -eq 1 ]]; then
  if [[ "$RUN_MIGRATE" -eq 1 && "$ONLY_PULL_RESTART" -eq 1 ]]; then
    run_migrations
  fi
  ensure_admin
  ensure_stock_reviews
fi

echo ">>> 更新完成"
