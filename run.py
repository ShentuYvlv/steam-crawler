import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = REPO_ROOT / "backend"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Steam Review Admin backend locally.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Default: 127.0.0.1")
    parser.add_argument("--port", default=8000, type=int, help="Bind port. Default: 8000")
    parser.add_argument("--no-reload", action="store_true", help="Disable uvicorn auto reload.")
    parser.add_argument("--skip-migrate", action="store_true", help="Skip Alembic migration before start.")
    return parser.parse_args()


def configure_pythonpath() -> None:
    paths = [str(BACKEND_DIR), str(REPO_ROOT)]
    for path in reversed(paths):
        if path not in sys.path:
            sys.path.insert(0, path)

    current_pythonpath = os.environ.get("PYTHONPATH")
    pythonpath_parts = paths if current_pythonpath is None else [*paths, current_pythonpath]
    os.environ["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)


def main() -> None:
    args = parse_args()
    configure_pythonpath()
    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "缺少后端依赖 uvicorn。请先在当前 venv 中执行：\n"
            "  python -m pip install -e backend\n"
            "然后再运行：\n"
            "  python run.py"
        ) from exc

    if not args.skip_migrate:
        try:
            from alembic import command
            from alembic.config import Config
        except ModuleNotFoundError as exc:
            raise SystemExit(
                "缺少迁移依赖 alembic。请先执行：\n"
                "  python -m pip install -e backend\n"
                "或临时跳过迁移：\n"
                "  python run.py --skip-migrate"
            ) from exc

        alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
        alembic_config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        command.upgrade(alembic_config, "head")

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
        app_dir=str(BACKEND_DIR),
    )


if __name__ == "__main__":
    main()
