"""
爬虫模块。

包含游戏信息爬虫和评价历史爬虫。
"""

from typing import Any

__all__ = ["CommentScraper", "GameScraper", "ReviewScraper"]


def __getattr__(name: str) -> Any:
    if name == "CommentScraper":
        from src.scrapers.comment_scraper import CommentScraper

        return CommentScraper
    if name == "GameScraper":
        from src.scrapers.game_scraper import GameScraper

        return GameScraper
    if name == "ReviewScraper":
        from src.scrapers.review_scraper import ReviewScraper

        return ReviewScraper
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
