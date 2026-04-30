from src.scrapers.comment_scraper import CommentScraper


class FakeHttpClient:
    def __init__(self) -> None:
        self.calls = 0
        self.closed = False

    async def get_json(self, url, params):
        self.calls += 1
        if self.calls == 1:
            return {
                "success": 1,
                "cursor": "next",
                "query_summary": {"total_reviews": 3},
                "reviews": [
                    {"recommendationid": "new", "timestamp_created": 200},
                    {"recommendationid": "same-second", "timestamp_created": 100},
                    {"recommendationid": "old", "timestamp_created": 99},
                ],
            }
        return {"success": 1, "cursor": "", "reviews": []}

    async def close(self) -> None:
        self.closed = True


async def test_comment_scraper_stops_when_reviews_are_older_than_local_latest() -> None:
    scraper = CommentScraper()
    fake_client = FakeHttpClient()
    scraper.client = fake_client

    result = await scraper.scrape_app_comments(app_id=3350200, since_timestamp=100)
    await scraper.close()

    assert [review["recommendationid"] for review in result["reviews"]] == [
        "new",
        "same-second",
    ]
    assert fake_client.calls == 1
    assert fake_client.closed is True
