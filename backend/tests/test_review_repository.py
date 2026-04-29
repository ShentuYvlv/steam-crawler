from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, SteamReview
from app.repositories import SteamReviewRepository


async def test_review_upsert_inserts_then_updates() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        repository = SteamReviewRepository(session)
        values = {
            "app_id": 3350200,
            "recommendation_id": "224287030",
            "review_text": "first",
            "votes_up": 0,
            "votes_funny": 0,
            "comment_count": 0,
            "sync_type": "stock",
            "source_type": "csv",
            "processing_status": "pending",
            "reply_status": "none",
        }

        inserted = await repository.upsert_review(values)
        updated = await repository.upsert_review(
            {**values, "review_text": "updated", "votes_up": 2}
        )
        await session.commit()

        reviews = (await session.execute(select(SteamReview))).scalars().all()

    await engine.dispose()

    assert inserted.inserted == 1
    assert updated.updated == 1
    assert len(reviews) == 1
    assert reviews[0].review_text == "updated"
    assert reviews[0].votes_up == 2
