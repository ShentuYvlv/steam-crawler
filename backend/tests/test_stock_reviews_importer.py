from pathlib import Path

from app.importers.stock_reviews import stock_review_row_to_values


def test_stock_review_row_to_values_maps_csv_fields() -> None:
    row = {
        "ID": "224287030",
        "SteamID": "76561198768996864",
        "评论链接": "https://steamcommunity.com/profiles/76561198768996864/recommended/3350200",
        "拥有游戏数": "0",
        "发表测评数量": "2",
        "总游戏时长": "7.75",
        "两周游戏时长": "0",
        "评论时游戏时长": "7.75",
        "最后游玩时间": "2026-01-25 21:50:39",
        "语言": "schinese",
        "评论内容": "敢觉不好玩",
        "创建时间": "2026-04-28 22:42:32",
        "更新时间": "2026-04-28 22:42:32",
        "正面评价": "FALSE",
        "有用票数": "0",
        "有趣票数": "0",
        "参考价值分": "0.50",
        "回复数": "0",
        "Steam购买": "TRUE",
        "免费获取": "FALSE",
        "抢先体验评论": "FALSE",
        "开发者回复": "",
        "开发者回复时间": "",
    }

    values = stock_review_row_to_values(row)

    assert values["app_id"] == 3350200
    assert values["recommendation_id"] == "224287030"
    assert values["steam_id"] == "76561198768996864"
    assert values["review_text"] == "敢觉不好玩"
    assert values["voted_up"] is False
    assert values["steam_purchase"] is True
    assert values["sync_type"] == "stock"
    assert values["source_type"] == "csv"
    assert values["reply_status"] == "none"


def test_stock_csv_file_is_present() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assert (repo_root / "data/情感反诈模拟器-steam评论 - 全部评论.csv").exists()
