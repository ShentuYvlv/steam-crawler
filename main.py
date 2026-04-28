"""
Steam 爬虫统一入口。

提供命令行接口来运行爬虫，支持异步并发抓取和数据库存储。
本模块是整个项目的 CLI 入口点，负责解析命令行参数并分发到对应的处理函数。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import signal
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import pyfiglet

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.database import DatabaseManager
from src.scrapers.comment_scraper import CommentScraper
from src.scrapers.game_scraper import GameScraper
from src.scrapers.review_scraper import ReviewScraper
from src.utils.checkpoint import Checkpoint
from src.utils.failure_manager import FailureManager
from src.utils.ui import UIManager

try:
    import uvloop
    uvloop.install()
except ImportError:
    pass


def _parse_app_id(value: str) -> int:
    """解析并校验命令行传入的 Steam AppID。"""
    try:
        app_id = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"无效的 AppID: {value}") from exc

    if app_id <= 0:
        raise argparse.ArgumentTypeError(f"AppID 必须是正整数: {value}")

    return app_id


def _parse_non_negative_int(value: str) -> int:
    """解析非负整数参数。"""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"必须是非负整数: {value}") from exc

    if parsed < 0:
        raise argparse.ArgumentTypeError(f"必须是非负整数: {value}")

    return parsed


def _parse_page_size(value: str) -> int:
    """解析 Steam 评论接口每页数量。"""
    parsed = _parse_non_negative_int(value)
    if parsed < 1 or parsed > 100:
        raise argparse.ArgumentTypeError("每页数量必须在 1 到 100 之间")
    return parsed


def _load_app_ids_from_file(file_path: str | Path) -> list[int]:
    """从文本文件读取 AppID 列表，每行一个 ID。"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"AppID 文件不存在: {path}")

    app_ids: list[int] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            value = line.strip()
            if not value:
                continue
            try:
                app_ids.append(_parse_app_id(value))
            except argparse.ArgumentTypeError as exc:
                raise ValueError(f"{path}:{line_number} {exc}") from exc

    return app_ids


def _get_target_app_ids(args: argparse.Namespace) -> list[int]:
    """合并 --appid 和 --input 指定的 AppID。"""
    app_ids = list(getattr(args, "appid", []) or [])

    input_file = getattr(args, "input", None)
    if input_file:
        app_ids.extend(_load_app_ids_from_file(input_file))

    return app_ids


def _resolve_comments_options(
    config: Config, args: argparse.Namespace
) -> dict[str, int | str | bool | None]:
    """合并 config.yaml 与命令行的真实评论抓取参数。"""
    comments = config.comments
    limit = comments.limit if args.limit is None else args.limit
    return {
        "language": comments.language if args.language is None else args.language,
        "filter": comments.filter if args.filter is None else args.filter,
        "review_type": comments.review_type if args.review_type is None else args.review_type,
        "purchase_type": (
            comments.purchase_type if args.purchase_type is None else args.purchase_type
        ),
        "per_page": comments.per_page if args.per_page is None else args.per_page,
        "limit": limit,
        "use_review_quality": comments.use_review_quality,
    }


def main() -> None:
    """主入口函数。"""
    parser = argparse.ArgumentParser(
        description="Steam 游戏数据爬虫 (AsyncIO 版)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  # 基础用法
  python main.py games              # 爬取所有游戏基础信息
  python main.py games --appid 730  # 爬取指定游戏基础信息
  python main.py games --input appids.txt # 从文件读取 AppID 爬取游戏基础信息
  python main.py reviews            # 爬取已有游戏的评价历史
  python main.py comments --appid 730 --file comments.json # 爬取逐条用户评论

  # 高级用法
  python main.py all                # 完整流程：爬取游戏 -> 爬取评价 -> 导出
  python main.py all --resume       # 从上次中断处继续
  python main.py games --pages 10   # 仅测试爬取前 10 页

  # 数据管理
  python main.py export             # 导出数据库到 Excel
  python main.py export --format csv # 导出数据库到 CSV (适合大数据量)
  python main.py clean              # 清理临时文件和缓存
  python main.py reset              # 重置项目（删除所有数据，慎用！）
  python main.py retry              # 重试所有失败的任务

断点恢复机制:
  不带 --resume: 清除断点，从头开始爬取
  带   --resume: 保留断点，跳过已完成/已失败的项目继续爬取
  失败的项目会被记录，可通过 retry 命令专门处理

输出:
  data/steam_data.db    (SQLite 数据库，核心存储)
  data/steam_data.xlsx  (Excel 导出文件，包含 Games 和 Reviews 两个工作表)
  data/steam_*.csv      (CSV 导出文件，UTF-8-SIG 编码)
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # 启动界面命令
    subparsers.add_parser(
        "start",
        help=argparse.SUPPRESS,  # 在帮助中隐藏
    )

    # 游戏信息爬取命令
    games_parser = subparsers.add_parser(
        "games",
        help="爬取游戏基础信息",
        description="从 Steam 商店爬取游戏基础信息（异步并发）",
    )
    games_parser.add_argument(
        "--pages",
        type=int,
        default=None,
        metavar="N",
        help="爬取页数，不指定则爬取全部",
    )
    games_parser.add_argument(
        "--appid",
        type=_parse_app_id,
        action="append",
        default=None,
        metavar="APPID",
        help="指定要爬取的游戏 AppID，可重复传入",
    )
    games_parser.add_argument(
        "--input",
        type=str,
        default=None,
        metavar="FILE",
        help="可选：指定 app_id 列表文件（每行一个 ID）",
    )
    games_parser.add_argument(
        "--resume",
        action="store_true",
        help="从断点恢复爬取",
    )

    # 评价信息爬取命令
    reviews_parser = subparsers.add_parser(
        "reviews",
        help="爬取评价历史信息",
        description="根据已爬取的最新的游戏列表，异步并发爬取评价历史",
    )
    reviews_parser.add_argument(
        "--appid",
        type=_parse_app_id,
        action="append",
        default=None,
        metavar="APPID",
        help="指定要爬取评价的游戏 AppID，可重复传入",
    )
    reviews_parser.add_argument(
        "--input",
        type=str,
        default=None,
        metavar="FILE",
        help="可选：指定 app_id 列表文件（如果不指定则从数据库读取）",
    )
    reviews_parser.add_argument(
        "--resume",
        action="store_true",
        help="从断点恢复爬取",
    )

    # 真实评论爬取命令
    comments_parser = subparsers.add_parser(
        "comments",
        help="爬取逐条用户评论",
        description="从 Steam 商店评论接口爬取真实用户评论 JSON 数据",
    )
    comments_parser.add_argument(
        "--appid",
        type=_parse_app_id,
        action="append",
        default=None,
        metavar="APPID",
        help="指定要爬取评论的游戏 AppID，可重复传入",
    )
    comments_parser.add_argument(
        "--input",
        type=str,
        default=None,
        metavar="FILE",
        help="可选：指定 app_id 列表文件（每行一个 ID）",
    )
    comments_parser.add_argument(
        "--file",
        type=str,
        default=None,
        metavar="JSON",
        help="评论 JSON 输出文件，不指定时输出到 data/ 目录",
    )
    comments_parser.add_argument(
        "--limit",
        type=_parse_non_negative_int,
        default=None,
        metavar="N",
        help="每个游戏最多抓取 N 条评论；不指定则使用 config.yaml，0 表示尽量抓取全部",
    )
    comments_parser.add_argument(
        "--language",
        type=str,
        default=None,
        help="评论语言；不指定则使用 config.yaml，可用 all 抓取全部语言",
    )
    comments_parser.add_argument(
        "--filter",
        type=str,
        default=None,
        help="评论排序/过滤方式；不指定则使用 config.yaml",
    )
    comments_parser.add_argument(
        "--review-type",
        choices=["all", "positive", "negative"],
        default=None,
        help="评论类型过滤；不指定则使用 config.yaml",
    )
    comments_parser.add_argument(
        "--purchase-type",
        choices=["all", "steam", "non_steam_purchase"],
        default=None,
        help="购买来源过滤；不指定则使用 config.yaml",
    )
    comments_parser.add_argument(
        "--per-page",
        type=_parse_page_size,
        default=None,
        metavar="N",
        help="每页请求数量，1-100；不指定则使用 config.yaml",
    )

    # 完整流程命令
    all_parser = subparsers.add_parser(
        "all",
        help="运行完整爬取流程",
        description="先爬取游戏基础信息，再自动爬取所有游戏的评价历史，最后导出",
    )
    all_parser.add_argument(
        "--pages",
        type=int,
        default=None,
        metavar="N",
        help="爬取页数限制",
    )
    all_parser.add_argument(
        "--appid",
        type=_parse_app_id,
        action="append",
        default=None,
        metavar="APPID",
        help="指定完整流程要处理的游戏 AppID，可重复传入",
    )
    all_parser.add_argument(
        "--input",
        type=str,
        default=None,
        metavar="FILE",
        help="可选：指定 app_id 列表文件（每行一个 ID）",
    )
    all_parser.add_argument(
        "--resume",
        action="store_true",
        help="从断点恢复",
    )

    # 导出命令
    export_parser = subparsers.add_parser(
        "export",
        help="导出数据到 Excel",
        description="将数据库中的数据导出为 Excel 文件",
    )
    export_parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出文件名。默认值将根据 config.yaml 中的 data_dir 动态生成。",
    )
    export_parser.add_argument(
        "--format",
        choices=["excel", "csv"],
        default="excel",
        help="导出格式 (默认: excel)",
    )

    # 清理命令
    subparsers.add_parser(
        "clean",
        help="清理缓存和临时文件",
    )

    # 重置命令
    subparsers.add_parser(
        "reset",
        help="重置项目（删除所有生成的数据，慎用）",
    )

    # 重试命令
    retry_parser = subparsers.add_parser(
        "retry",
        help="重试失败的项目",
    )
    retry_parser.add_argument(
        "--type",
        choices=["game", "review", "all"],
        default="all",
        help="重试类型",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    config = Config.load()
    failure_manager = FailureManager(config)
    ui = UIManager()

    # 显示 Banner
    ui.print_panel(
        "[bold white]Simple Steam Scraper (AsyncIO)[/bold white]\n"
        "[dim]github.com/SeraphinaGlacia/steam-scraper[/dim]",
        style="header",
    )

    stop_event = threading.Event()

    def signal_handler(signum, frame):
        """处理信号（如 Ctrl+C）。

        通过设置 stop_event 标志来优雅地停止所有正在运行的爬虫线程/任务，
        而不是直接强制终止进程，这样可以确保数据完整性和断点保存。
        """
        print("\n")
        print("⚠️  接收到停止信号，正在停止... / Stopping...")
        # 设置事件标志通知所有工作线程/协程停止
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)

    if args.command == "games":
        run_games_scraper(config, args, failure_manager, ui, stop_event)
    elif args.command == "start":
        run_start(ui)
    elif args.command == "reviews":
        run_reviews_scraper(config, args, failure_manager, ui, stop_event)
    elif args.command == "comments":
        run_comments_scraper(config, args, failure_manager, ui, stop_event)
    elif args.command == "all":
        run_all(config, args, failure_manager, ui, stop_event)
    elif args.command == "export":
        run_export(config, args, ui)
    elif args.command == "clean":
        run_clean(failure_manager, ui)
    elif args.command == "reset":
        run_reset(config, failure_manager, ui)
    elif args.command == "retry":
        run_retry(config, args, failure_manager, ui)


def run_reset(config: Config, failure_manager: FailureManager, ui: UIManager) -> None:
    """重置项目，清除所有数据。"""
    ui.print_panel(
        "[bold red]⚠️  危险操作警告 / DANGER ZONE[/bold red]\n\n"
        "此操作将 [bold red]永久删除[/bold red] `data/` 目录下所有文件：\n"
        " - 数据库文件 (steam_data.db)\n"
        " - 导出文件 (Excel/CSV)\n"
        " - 失败日志 (failures.json)\n"
        " - 断点文件 (.checkpoint.json)\n\n"
        "此操作不可恢复！",
        title="重置项目 Reset Project",
        style="red",
    )

    if not ui.confirm("[bold red]确认要重置吗？[/bold red]"):
        ui.print("操作已取消。")
        return

    if not ui.confirm("[bold red]再次确认：真的要删除所有数据吗？[/bold red]"):
        ui.print("操作已取消。")
        return

    ui.print("\n[bold yellow]开始重置...[/bold yellow]")

    # 1. 清理 data 目录
    data_dir = Path(config.output.data_dir)
    if data_dir.exists():
        for item in data_dir.glob("*"):
            if item.name == ".gitkeep":
                continue
            try:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
                ui.print(f"已删除: [dim]{item}[/dim]")
            except Exception as e:
                ui.print_error(f"删除失败 {item}: {e}")
    else:
        ui.print_warning(f"目录不存在: {data_dir}")

    # 2. 运行常规清理
    run_clean(failure_manager, ui)

    ui.print_success("✨ 项目已重置 / Project Reset Completed")


def run_start(ui: UIManager) -> None:
    """显示启动界面。"""
    # 1. Big ASCII Art
    try:
        title = pyfiglet.figlet_format("Steam Scraper", font="slant")
        ui.print(title, style="bold cyan")
    except Exception:
        ui.print_panel("[bold cyan]Steam Scraper[/bold cyan]", style="cyan")

    # 2. Welcome Panel
    ui.print_panel(
        "[bold white]快速开始指南 / Getting Started:[/bold white]\n"
        "1. 运行 [cyan]python main.py --help[/cyan] 查看所有可用命令。\n"
        "2. 运行 [cyan]python main.py games[/cyan] 抓取游戏基础数据。\n"
        "3. 运行 [cyan]python main.py reviews[/cyan] 抓取评价历史数据。\n"
        "4. 运行 [cyan]python main.py export[/cyan] 导出最终 Excel 报表。\n\n"
        "[dim]项目地址: github.com/SeraphinaGlacia/steam-scraper[/dim]",
        title="欢迎使用 Simple Steam Scraper",
        style="blue",
    )


def run_clean(
    failure_manager: FailureManager | None = None, ui: Optional[UIManager] = None
) -> None:
    """清理缓存和临时文件。"""
    if ui is None:
        ui = UIManager()

    project_root = Path(__file__).parent
    cleaned = 0

    # 删除 __pycache__ 目录
    for pycache in project_root.rglob("__pycache__"):
        if pycache.is_dir():
            shutil.rmtree(pycache)
            ui.print(f"已删除: [dim]{pycache}[/dim]")
            cleaned += 1

    # 删除 .pyc 文件
    for pyc in project_root.rglob("*.pyc"):
        pyc.unlink()
        ui.print(f"已删除: [dim]{pyc}[/dim]")
        cleaned += 1

    # 删除断点文件
    checkpoint_files = [
        project_root / ".checkpoint.json",
        project_root / "data" / ".checkpoint.json",
    ]
    for cp in checkpoint_files:
        if cp.exists():
            cp.unlink()
            ui.print(f"已删除: [dim]{cp}[/dim]")
            cleaned += 1

    # 清除失败日志
    if failure_manager:
        failure_manager.clear()
        cleaned += 1

    if cleaned:
        ui.print_success(f"清理完成，共删除 {cleaned} 个文件/目录。")
    else:
        ui.print_info("没有需要清理的文件。")


def _get_game_failures(
    failure_manager: FailureManager, checkpoint: Checkpoint
) -> list[dict]:
    """获取所有 games 类型的失败记录（合并两个来源）。

    Args:
        failure_manager: 失败记录管理器。
        checkpoint: 断点管理器。

    Returns:
        list[dict]: 失败记录列表。
    """
    failures = failure_manager.get_failures("game")
    existing_ids = {f["id"] for f in failures}

    for app_id in checkpoint.get_failed_appids("game"):
        if app_id not in existing_ids:
            failures.append({
                "type": "game",
                "id": app_id,
                "reason": "从断点记录恢复（无详细原因）",
            })
            existing_ids.add(app_id)

    return failures


async def run_games_scraper_async(
    config: Config,
    args: argparse.Namespace,
    failure_manager: FailureManager,
    ui: UIManager,
    stop_event: threading.Event,
) -> None:
    """异步运行游戏信息爬虫逻辑。

    Args:
        config: 配置对象。
        args: 命令行参数。
        failure_manager: 失败管理器。
        ui: UI 管理器。
        stop_event: 停止事件标志。
    """
    checkpoint = Checkpoint(config=config)
    if not args.resume:
        checkpoint.clear_task("game")  # 只清除 games 状态

    scraper = GameScraper(
        config=config,
        checkpoint=checkpoint,
        failure_manager=failure_manager,
        ui_manager=ui,
        stop_event=stop_event,
    )

    start_time = time.time()
    try:
        try:
            target_app_ids = _get_target_app_ids(args)
        except (FileNotFoundError, ValueError) as e:
            ui.print_error(str(e))
            return

        if target_app_ids:
            if args.pages:
                ui.print_warning("已指定 AppID，--pages 参数将被忽略。")
            await scraper.scrape_from_list(target_app_ids)
        else:
            await scraper.run(max_pages=args.pages)
    finally:
        checkpoint.save()

    elapsed = time.time() - start_time
    duration = str(timedelta(seconds=int(elapsed)))

    # 为路径添加前缀，确保终端输出中点击行为一致且美观
    db_path = str(config.output.db_path)
    if not db_path.startswith("./") and not db_path.startswith("/"):
        db_path = f"./{db_path}"

    ui.print_success(f"游戏信息爬取完成！数据已存入: [bold]{db_path}[/bold] (耗时: {duration})")


def run_games_scraper(
    config: Config,
    args: argparse.Namespace,
    failure_manager: FailureManager,
    ui: UIManager,
    stop_event: threading.Event,
) -> None:
    """运行游戏信息爬虫（入口包装）。"""
    asyncio.run(
        run_games_scraper_async(config, args, failure_manager, ui, stop_event)
    )


async def run_reviews_scraper_async(
    config: Config,
    args: argparse.Namespace,
    failure_manager: FailureManager,
    ui: UIManager,
    stop_event: threading.Event,
) -> None:
    """异步运行评价历史爬虫逻辑。

    Args:
        config: 配置对象。
        args: 命令行参数。
        failure_manager: 失败管理器。
        ui: UI 管理器。
        stop_event: 停止事件标志。
    """
    checkpoint = Checkpoint(config=config)

    # 确保在爬取评价前游戏数据完整，避免外键约束错误或数据缺失
    game_failures = _get_game_failures(failure_manager, checkpoint)
    if game_failures:
        ui.print_warning(
            f"检测到 {len(game_failures)} 个游戏爬取失败记录。\n"
            "这可能导致 reviews 爬取时缺少对应的游戏表数据。\n"
            "建议先运行 [cyan]python main.py retry --type game[/cyan] 处理失败项目。"
        )
        if not ui.confirm("是否忽略警告，继续爬取 reviews？", default=False):
            ui.print("操作已取消。请先处理 games 失败记录。")
            return

    if not args.resume:
        checkpoint.clear_task("review")  # 只清除 reviews 状态

    scraper = ReviewScraper(
        config=config,
        checkpoint=checkpoint,
        failure_manager=failure_manager,
        ui_manager=ui,
        stop_event=stop_event,
    )

    start_time = time.time()
    try:
        try:
            target_app_ids = _get_target_app_ids(args)
        except (FileNotFoundError, ValueError) as e:
            ui.print_error(str(e))
            return

        if target_app_ids:
            await scraper.scrape_from_list(target_app_ids)
        else:
            db = DatabaseManager(config.output.db_path)
            app_ids = db.get_all_app_ids()
            db.close()

            if not app_ids:
                ui.print_warning("数据库中没有游戏数据，请先运行 'python main.py games'")
                return

            await scraper.scrape_from_list(app_ids)
    finally:
        checkpoint.save()

    elapsed = time.time() - start_time
    duration = str(timedelta(seconds=int(elapsed)))

    # 为路径添加前缀，确保终端输出中点击行为一致且美观
    db_path = str(config.output.db_path)
    if not db_path.startswith("./") and not db_path.startswith("/"):
        db_path = f"./{db_path}"

    ui.print_success(f"评价数据爬取完成！数据已存入: [bold]{db_path}[/bold] (耗时: {duration})")


def run_reviews_scraper(
    config: Config,
    args: argparse.Namespace,
    failure_manager: FailureManager,
    ui: UIManager,
    stop_event: threading.Event,
) -> None:
    """运行评价历史爬虫（入口包装）。"""
    asyncio.run(
        run_reviews_scraper_async(config, args, failure_manager, ui, stop_event)
    )


def _get_comments_output_path(
    config: Config, args: argparse.Namespace, app_ids: list[int]
) -> Path:
    """获取真实评论 JSON 输出路径。"""
    if args.file:
        return Path(args.file)

    data_dir = Path(config.output.data_dir)
    if len(app_ids) == 1:
        return data_dir / f"steam_comments_{app_ids[0]}.json"
    return data_dir / "steam_comments.json"


async def run_comments_scraper_async(
    config: Config,
    args: argparse.Namespace,
    failure_manager: FailureManager,
    ui: UIManager,
    stop_event: threading.Event,
) -> None:
    """异步运行逐条用户评论爬虫。"""
    try:
        app_ids = _get_target_app_ids(args)
    except (FileNotFoundError, ValueError) as e:
        ui.print_error(str(e))
        return

    if not app_ids:
        ui.print_warning("请通过 --appid 或 --input 指定要爬取评论的游戏。")
        return

    seen_appids: set[int] = set()
    unique_app_ids: list[int] = []
    for app_id in app_ids:
        if app_id in seen_appids:
            continue
        seen_appids.add(app_id)
        unique_app_ids.append(app_id)

    comment_options = _resolve_comments_options(config, args)
    limit_value = comment_options["limit"]
    limit = None if limit_value == 0 else limit_value
    output_path = _get_comments_output_path(config, args, unique_app_ids)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    scraper = CommentScraper(config=config, ui_manager=ui, stop_event=stop_event)
    results: list[dict] = []
    start_time = time.time()

    try:
        with ui.create_progress() as progress:
            task = progress.add_task("抓取真实评论...", total=len(unique_app_ids))

            for app_id in unique_app_ids:
                if stop_event.is_set():
                    break

                try:
                    result = await scraper.scrape_app_comments(
                        app_id=app_id,
                        limit=limit,
                        language=comment_options["language"],
                        filter_type=comment_options["filter"],
                        review_type=comment_options["review_type"],
                        purchase_type=comment_options["purchase_type"],
                        num_per_page=comment_options["per_page"],
                        use_review_quality=comment_options["use_review_quality"],
                    )
                    results.append(result)
                    failure_manager.remove_failure("comment", app_id)
                except Exception as e:
                    ui.print_error(f"爬取游戏 {app_id} 真实评论失败: {e}")
                    failure_manager.log_failure("comment", app_id, str(e))
                finally:
                    progress.update(task, advance=1)
    finally:
        await scraper.close()

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "https://store.steampowered.com/ajaxappreviews/{app_id}",
        "filters": {
            "language": comment_options["language"],
            "filter": comment_options["filter"],
            "review_type": comment_options["review_type"],
            "purchase_type": comment_options["purchase_type"],
            "limit": limit,
            "per_page": comment_options["per_page"],
            "use_review_quality": comment_options["use_review_quality"],
        },
        "games": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_time
    duration = str(timedelta(seconds=int(elapsed)))
    total_reviews = sum(game["review_count"] for game in results)
    ui.print_success(
        f"真实评论抓取完成：{len(results)} 个游戏，{total_reviews} 条评论。"
        f" 已保存到: [bold]{output_path}[/bold] (耗时: {duration})"
    )


def run_comments_scraper(
    config: Config,
    args: argparse.Namespace,
    failure_manager: FailureManager,
    ui: UIManager,
    stop_event: threading.Event,
) -> None:
    """运行逐条用户评论爬虫（入口包装）。"""
    asyncio.run(
        run_comments_scraper_async(config, args, failure_manager, ui, stop_event)
    )


async def run_all_async(
    config: Config,
    args: argparse.Namespace,
    failure_manager: FailureManager,
    ui: UIManager,
    stop_event: threading.Event,
) -> None:
    """异步运行完整爬取流程逻辑。

    Args:
        config: 配置对象。
        args: 命令行参数。
        failure_manager: 失败管理器。
        ui: UI 管理器。
        stop_event: 停止事件标志。
    """
    checkpoint = Checkpoint(config=config)
    if not args.resume:
        checkpoint.clear()

    start_time = time.time()
    try:
        target_app_ids = _get_target_app_ids(args)
    except (FileNotFoundError, ValueError) as e:
        ui.print_error(str(e))
        return

    try:
        ui.print_panel("Step 1/3: 爬取游戏基础信息", style="blue")
        game_scraper = GameScraper(
            config=config,
            checkpoint=checkpoint,
            failure_manager=failure_manager,
            ui_manager=ui,
            stop_event=stop_event,
        )
        if target_app_ids:
            if args.pages:
                ui.print_warning("已指定 AppID，--pages 参数将被忽略。")
            await game_scraper.scrape_from_list(target_app_ids)
        else:
            await game_scraper.run(max_pages=args.pages)
        # 阶段性保存，防止Step 2崩溃导致Step 1进度丢失
        checkpoint.save()
        
        # 为路径添加前缀，确保终端输出中点击行为一致且美观
        db_path = str(config.output.db_path)
        if not db_path.startswith("./") and not db_path.startswith("/"):
            db_path = f"./{db_path}"
        ui.print_success(f"游戏信息爬取完成！数据已存入: [bold]{db_path}[/bold]")

        if stop_event.is_set():
            return

        # 检查 games 是否有失败记录
        game_failures = _get_game_failures(failure_manager, checkpoint)
        if game_failures:
            ui.print_warning(
                f"\n游戏爬取阶段有 {len(game_failures)} 个失败项目。\n"
                "继续爬取 reviews 可能导致数据不完整。"
            )
            if not ui.confirm("是否继续爬取 reviews？（建议先处理失败项目）", default=True):
                ui.print(
                    "已停止。请使用 [cyan]python main.py retry --type game[/cyan] 处理失败项目后重试。"
                )
                return

        ui.print("\n")
        ui.print_panel("Step 2/3: 爬取评价历史信息", style="blue")
        app_ids = target_app_ids or game_scraper.get_app_ids()

        review_scraper = ReviewScraper(
            config=config,
            checkpoint=checkpoint,
            failure_manager=failure_manager,
            ui_manager=ui,
            stop_event=stop_event,
        )
        await review_scraper.scrape_from_list(app_ids)
        checkpoint.save()
        
        # 为路径添加前缀，确保终端输出中点击行为一致且美观
        db_path = str(config.output.db_path)
        if not db_path.startswith("./") and not db_path.startswith("/"):
            db_path = f"./{db_path}"
        ui.print_success(f"评价数据爬取完成！数据已存入: [bold]{db_path}[/bold]")

        if stop_event.is_set():
            return

        ui.print("\n")
        ui.print_panel("Step 3/3: 导出数据", style="blue")

        # 同时导出 Excel 和 CSV 两种格式
        # 使用 None 作为 output，让 run_export 内部根据 config 动态生成默认路径
        await asyncio.to_thread(run_export, config, argparse.Namespace(output=None, format="excel"), ui)
        await asyncio.to_thread(run_export, config, argparse.Namespace(output=None, format="csv"), ui)

        elapsed = time.time() - start_time
        duration = str(timedelta(seconds=int(elapsed)))
        ui.print_success(f"🎉 全部完成！Enjoy your data. (总耗时: {duration})")
    finally:
        checkpoint.save()


def run_all(
    config: Config,
    args: argparse.Namespace,
    failure_manager: FailureManager,
    ui: UIManager,
    stop_event: threading.Event,
) -> None:
    """运行完整爬取流程（入口包装）。"""
    asyncio.run(run_all_async(config, args, failure_manager, ui, stop_event))


def run_export(config: Config, args: argparse.Namespace, ui: UIManager) -> None:
    """导出数据。"""
    ui.print_info(f"正在导出数据 ({args.format})...")

    if not Path(config.output.db_path).exists():
        ui.print_error(
            f"数据库文件不存在: {config.output.db_path}\n"
            "请先运行 'python main.py games' 等相关命令抓取数据。"
        )
        return

    db = DatabaseManager(config.output.db_path)
    try:
        with ui.create_progress() as progress:
            # 导出操作较快，使用模拟进度条提升用户体验
            task = progress.add_task("导出中...", total=100)
            progress.update(task, advance=50)
            
            if args.format == "csv":
                # CSV 模式下，args.output 被视为目录
                if args.output:
                    output_dir = Path(args.output)
                else:
                    # 默认使用 config 中的 data_dir
                    output_dir = Path(config.output.data_dir)
                
                # 格式化路径显示
                path_str = str(output_dir)
                if not path_str.startswith("./") and not path_str.startswith("/"):
                    path_str = f"./{path_str}"
                
                ui.print_success(f"导出成功！文件保存在: [bold]{path_str}/steam_games.csv[/bold] & [bold]{path_str}/steam_reviews.csv[/bold]")
            else:
                # Excel 模式
                if args.output:
                    output_file = args.output
                else:
                    # 默认: {data_dir}/steam_data.xlsx
                    output_file = Path(config.output.data_dir) / "steam_data.xlsx"
                    
                db.export_to_excel(output_file)
                
                # 格式化路径显示
                path_str = str(output_file)
                if not path_str.startswith("./") and not path_str.startswith("/"):
                    path_str = f"./{path_str}"

                ui.print_success(f"导出成功！文件保存在: [bold]{path_str}[/bold]")
                
            progress.update(task, completed=100)

    except Exception as e:
        ui.print_error(f"导出失败: {e}")
    finally:
        db.close()


async def run_retry_async(
    config: Config,
    args: argparse.Namespace,
    failure_manager: FailureManager,
    ui: UIManager,
) -> None:
    """异步运行重试逻辑。

    Args:
        config: 配置对象。
        args: 命令行参数。
        failure_manager: 失败管理器。
        ui: UI 管理器。
    """
    ui.print_info("开始检查失败项目...")

    # 1. 从 FailureManager 获取失败记录
    failures = failure_manager.get_failures()

    # 2. 从 Checkpoint 获取 failed_appids（合并到 failures 列表）
    checkpoint = Checkpoint(config=config)

    # 2.1 Games 失败记录
    existing_ids = {(f["type"], f["id"]) for f in failures}
    for app_id in checkpoint.get_failed_appids("game"):
        if ("game", app_id) not in existing_ids:
            failures.append({
                "type": "game",
                "id": app_id,
                "reason": "从断点记录恢复（无详细原因）",
            })
            existing_ids.add(("game", app_id))

    # 2.2 Reviews 失败记录
    for app_id in checkpoint.get_failed_appids("review"):
        if ("review", app_id) not in existing_ids:
            failures.append({
                "type": "review",
                "id": app_id,
                "reason": "从断点记录恢复（无详细原因）",
            })
            existing_ids.add(("review", app_id))

    if not failures:
        ui.print_success("没有找到失败记录，Perfect!")
        return

    # 创建表格展示失败项目
    table = ui.create_table(title="失败任务清单")
    table.add_column("Type", style="cyan")
    table.add_column("ID", style="magenta")
    table.add_column("Reason", style="red")

    for f in failures:
        table.add_row(f["type"], str(f["id"]), f["reason"][:50])

    ui.console.print(table)

    if not ui.confirm("是否立即重试这些项目？", default=True):
        ui.print("操作已取消。")
        return

    # 使用同一个 checkpoint 实例，确保 retry 成功后状态被正确更新
    game_scraper = GameScraper(
        config=config, checkpoint=checkpoint, failure_manager=failure_manager, ui_manager=ui
    )
    review_scraper = ReviewScraper(
        config=config, checkpoint=checkpoint, failure_manager=failure_manager, ui_manager=ui
    )

    # 先处理 games，再处理 reviews
    failures.sort(key=lambda f: 0 if f["type"] == "game" else 1)

    retry_count = 0
    success_count = 0

    try:
        with ui.create_progress() as progress:
            task = progress.add_task("重试中...", total=len(failures))

            for failure in failures:
                item_type = failure["type"]
                item_id = int(failure["id"])

                if args.type != "all" and item_type != args.type:
                    progress.update(task, advance=1)
                    continue

                retry_count += 1
                is_success = False

                try:
                    if item_type == "game":
                        info, _ = await game_scraper.process_game(item_id, force=True)
                        if info:
                            is_success = True
                    elif item_type == "review":
                        reviews, _ = await review_scraper.scrape_reviews(item_id, force=True)
                        if reviews:
                            is_success = True
                except Exception:
                    pass

                if is_success:
                    failure_manager.remove_failure(item_type, item_id)
                    success_count += 1

                progress.update(task, advance=1)
    finally:
        checkpoint.save()
    
    # 最后关闭客户端连接
    await game_scraper.client.close()
    await review_scraper.client.close()

    ui.print_panel(
        f"重试结束。\n"
        f"尝试: {retry_count}\n"
        f"成功: [green]{success_count}[/green]\n"
        f"剩余: [red]{retry_count - success_count}[/red]",
        title="重试报告",
    )


def run_retry(
    config: Config,
    args: argparse.Namespace,
    failure_manager: FailureManager,
    ui: UIManager,
) -> None:
    """运行重试逻辑（入口包装）。"""
    asyncio.run(run_retry_async(config, args, failure_manager, ui))


if __name__ == "__main__":
    main()
