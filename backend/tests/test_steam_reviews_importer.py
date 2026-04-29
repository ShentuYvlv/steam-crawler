from app.importers.steam_reviews import steam_api_review_to_values


def test_steam_api_review_to_values_maps_ajaxappreviews_payload() -> None:
    values = steam_api_review_to_values(
        3350200,
        {
            "recommendationid": "224190513",
            "author": {
                "steamid": "76561199114484931",
                "personaname": "tester",
                "playtime_forever": 120,
                "playtime_at_review": 60,
                "playtime_last_two_weeks": 30,
            },
            "language": "schinese",
            "review": "测试评论",
            "timestamp_created": 1777258404,
            "timestamp_updated": 1777258793,
            "voted_up": False,
            "votes_up": 3,
            "votes_funny": 0,
            "weighted_vote_score": "0.5",
            "comment_count": 1,
            "steam_purchase": False,
            "received_for_free": False,
            "refunded": False,
            "written_during_early_access": False,
        },
    )

    assert values["app_id"] == 3350200
    assert values["recommendation_id"] == "224190513"
    assert values["steam_id"] == "76561199114484931"
    assert values["persona_name"] == "tester"
    assert values["review_text"] == "测试评论"
    assert values["playtime_forever"] == 2.0
    assert values["sync_type"] == "incremental"
    assert values["source_type"] == "steam_api"
