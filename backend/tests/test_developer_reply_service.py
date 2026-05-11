from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Base, DeveloperReply, ReplyDraft, SteamGame, SteamReview, User
from app.services.developer_replies import (
    DeveloperReplyError,
    DeveloperReplyService,
    create_steam_reply_client,
    process_pending_reply_send,
    resolve_cookie_file_path,
)


class FakeSteamReplyClient:
    async def set_developer_response(self, recommendation_id: str, response_text: str) -> dict:
        assert recommendation_id == "1001"
        assert response_text == "final reply content"
        return {"success": True, "response": {"success": 1}}

    async def close(self) -> None:
        return None


class CountingSteamReplyClient:
    calls = 0

    async def set_developer_response(self, recommendation_id: str, response_text: str) -> dict:
        type(self).calls += 1
        return {"success": True, "response": {"success": 1}}

    async def close(self) -> None:
        return None


class FailingSteamReplyClient:
    async def set_developer_response(self, recommendation_id: str, response_text: str) -> dict:
        raise RuntimeError("steam send failed: invalid cookie or session")

    async def close(self) -> None:
        return None


def test_resolve_cookie_file_path_maps_docker_app_path_to_local_repo(tmp_path, monkeypatch) -> None:
    import app.services.developer_replies as developer_replies_module

    cookie_file = tmp_path / "data" / "steam_cookie.txt"
    cookie_file.parent.mkdir(parents=True, exist_ok=True)
    cookie_file.write_text("sessionid=test-cookie", encoding="utf-8")
    monkeypatch.setattr(developer_replies_module, "REPO_ROOT", tmp_path)

    resolved = resolve_cookie_file_path("/app/data/steam_cookie.txt")

    assert resolved == cookie_file


def test_create_steam_reply_client_reads_local_cookie_for_docker_style_env(
    tmp_path,
    monkeypatch,
) -> None:
    import app.services.developer_replies as developer_replies_module

    cookie_file = tmp_path / "data" / "steam_cookie.txt"
    cookie_file.parent.mkdir(parents=True, exist_ok=True)
    cookie_file.write_text("sessionid=test-cookie", encoding="utf-8")

    class FakeSettings:
        steam_cookie_file = "/app/data/steam_cookie.txt"
        steam_reply_proxy_url = "http://127.0.0.1:7890"
        steam_reply_proxy_direct_fallback = False

    class FakeClient:
        def __init__(
            self,
            cookie_header: str,
            proxy_url: str | None = None,
            proxy_direct_fallback: bool = False,
        ) -> None:
            self.cookie_header = cookie_header
            self.proxy_url = proxy_url
            self.proxy_direct_fallback = proxy_direct_fallback

    monkeypatch.setattr(developer_replies_module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(developer_replies_module, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(
        "src.scrapers.comment_reply.load_cookie_header",
        lambda path: f"loaded:{path}",
    )
    monkeypatch.setattr("src.scrapers.comment_reply.DeveloperReplyClient", FakeClient)

    client = create_steam_reply_client()

    assert isinstance(client, FakeClient)
    assert client.cookie_header == f"loaded:{cookie_file}"
    assert client.proxy_url == "http://127.0.0.1:7890"
    assert client.proxy_direct_fallback is False


async def test_developer_reply_send_updates_record_review_and_draft() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        review, draft = await seed_review_with_draft(session)
        service = DeveloperReplyService(session, client_factory=FakeSteamReplyClient)

        record = await service.send_reply(
            review.id,
            confirmed=True,
            draft_id=draft.id,
            content="final reply content",
            sent_by_user_id=7,
        )

        stored_review = await session.get(SteamReview, review.id)
        stored_draft = await session.get(ReplyDraft, draft.id)

    await engine.dispose()

    assert record.content == "final reply content"
    assert record.status == "sent"
    assert record.sent_at is not None
    assert stored_review is not None
    assert stored_review.reply_status == "replied"
    assert stored_review.developer_response == "final reply content"
    assert stored_draft is not None
    assert stored_draft.content == "final reply content"
    assert stored_draft.status == "sent"
    assert stored_draft.reviewed_by_user_id == 7
    assert stored_draft.reviewed_at is not None


async def test_developer_reply_requires_confirmation() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        review, draft = await seed_review_with_draft(session)
        service = DeveloperReplyService(session, client_factory=FakeSteamReplyClient)

        with pytest.raises(DeveloperReplyError):
            await service.send_reply(review.id, confirmed=False, draft_id=draft.id)

    await engine.dispose()


async def test_developer_reply_queue_marks_review_and_draft_as_sending() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        review, draft = await seed_review_with_draft(session)
        service = DeveloperReplyService(session, client_factory=FakeSteamReplyClient)

        record = await service.queue_reply(
            review.id,
            confirmed=True,
            draft_id=draft.id,
            content="final reply content",
            sent_by_user_id=9,
        )

        stored_review = await session.get(SteamReview, review.id)
        stored_draft = await session.get(ReplyDraft, draft.id)

    await engine.dispose()

    assert record.status == "pending"
    assert record.content == "final reply content"
    assert stored_review is not None
    assert stored_review.reply_status == "sending"
    assert stored_draft is not None
    assert stored_draft.status == "sending"
    assert stored_draft.content == "final reply content"
    assert stored_draft.reviewed_by_user_id == 9
    assert stored_draft.reviewed_at is not None


async def test_developer_reply_blocks_duplicate_send_when_pending_or_sent() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        review, draft = await seed_review_with_draft(session)
        service = DeveloperReplyService(session, client_factory=FakeSteamReplyClient)

        queued_record = await service.queue_reply(
            review.id,
            confirmed=True,
            draft_id=draft.id,
            content="final reply content",
        )

        with pytest.raises(DeveloperReplyError, match="Reply send already in progress"):
            await service.queue_reply(
                review.id,
                confirmed=True,
                draft_id=draft.id,
                content="final reply content",
            )

        await service.perform_send(queued_record.id)

        with pytest.raises(DeveloperReplyError, match="Review reply already sent"):
            await service.queue_reply(
                review.id,
                confirmed=True,
                draft_id=draft.id,
                content="final reply content",
            )

    await engine.dispose()


async def test_developer_reply_failure_updates_draft_and_review_error_state() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        review, draft = await seed_review_with_draft(session)
        service = DeveloperReplyService(session, client_factory=FailingSteamReplyClient)

        queued_record = await service.queue_reply(
            review.id,
            confirmed=True,
            draft_id=draft.id,
            content="final reply content",
        )

        with pytest.raises(DeveloperReplyError, match="steam send failed"):
            await service.perform_send(queued_record.id)

        stored_record = await session.get(DeveloperReply, queued_record.id)
        stored_review = await session.get(SteamReview, review.id)
        stored_draft = await session.get(ReplyDraft, draft.id)

    await engine.dispose()

    assert stored_record is not None
    assert stored_record.status == "failed"
    assert "steam send failed" in (stored_record.error_message or "")
    assert stored_review is not None
    assert stored_review.reply_status == "send_failed"
    assert stored_draft is not None
    assert stored_draft.status == "send_failed"
    assert "steam send failed" in (stored_draft.error_message or "")


async def test_process_pending_reply_send_recreates_default_client_and_completes(monkeypatch) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        review, draft = await seed_review_with_draft(session)
        service = DeveloperReplyService(session, client_factory=FakeSteamReplyClient)
        record = await service.queue_reply(
            review.id,
            confirmed=True,
            draft_id=draft.id,
            content="final reply content",
        )

    import app.services.developer_replies as developer_replies_module

    CountingSteamReplyClient.calls = 0
    monkeypatch.setattr(developer_replies_module, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(
        developer_replies_module,
        "create_steam_reply_client",
        lambda: CountingSteamReplyClient(),
    )

    await process_pending_reply_send(record.id)

    async with session_factory() as session:
        stored_record = await session.get(DeveloperReply, record.id)
        stored_review = await session.get(SteamReview, review.id)

    await engine.dispose()

    assert CountingSteamReplyClient.calls == 1
    assert stored_record is not None
    assert stored_record.status == "sent"
    assert stored_review is not None
    assert stored_review.reply_status == "replied"


async def test_reply_records_delete_request_route() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as seed_session:
        review, _ = await seed_review_with_draft(seed_session)
        record = DeveloperReply(
            review_id=review.id,
            recommendation_id=review.recommendation_id,
            content="sent reply content",
            status="sent",
        )
        seed_session.add(record)
        admin = User(
            username="admin",
            password_hash=hash_password("password123"),
            role="admin",
            is_active=True,
        )
        seed_session.add(admin)
        await seed_session.commit()
        record_id = record.id
        token = create_access_token(admin)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}
            list_response = await client.get("/api/reply-records")
            audit_response = await client.get("/api/reply-records/audit-queue")
            delete_response = await client.post(
                f"/api/reply-records/{record_id}/delete-request",
                headers=headers,
                json={"confirmed": True, "reason": "delete request for test"},
            )
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert list_response.status_code == 200
    assert list_response.json()[0]["content"] == "sent reply content"
    assert list_response.json()[0]["game_name"] == "test game"
    assert audit_response.status_code == 200
    assert audit_response.json()[0]["content"] == "initial draft content"
    assert audit_response.json()[0]["game_name"] == "test game"
    assert delete_response.status_code == 200
    assert delete_response.json()["delete_status"] == "requested"
    assert delete_response.json()["delete_request_reason"] == "delete request for test"


async def test_reply_records_audit_queue_excludes_replied_reviews() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        review, draft = await seed_review_with_draft(session)
        service = DeveloperReplyService(session, client_factory=FakeSteamReplyClient)
        await service.send_reply(
            review.id,
            confirmed=True,
            draft_id=draft.id,
            content="final reply content",
        )
        session.add(
            ReplyDraft(
                review_id=review.id,
                content="stale pending draft",
                status="pending_review",
                model_name="qwen-plus",
            )
        )
        await session.commit()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reply-records/audit-queue")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 200
    assert response.json() == []


async def test_reply_records_audit_queue_returns_latest_active_draft_per_review() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        review, _ = await seed_review_with_draft(session)
        newer_draft = ReplyDraft(
            review_id=review.id,
            content="latest draft content",
            status="pending_review",
            model_name="qwen-plus",
        )
        session.add(newer_draft)
        await session.commit()
        newer_draft_id = newer_draft.id
        review_id = review.id

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reply-records/audit-queue")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == newer_draft_id
    assert response.json()[0]["content"] == "latest draft content"
    assert response.json()[0]["review_id"] == review_id


async def test_reply_records_audit_queue_keeps_sending_items_visible() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        review, draft = await seed_review_with_draft(session)
        service = DeveloperReplyService(session, client_factory=FakeSteamReplyClient)
        await service.queue_reply(
            review.id,
            confirmed=True,
            draft_id=draft.id,
            content="final reply content",
        )

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reply-records/audit-queue")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "sending"


async def test_reply_records_audit_queue_returns_send_failure_message() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        review, draft = await seed_review_with_draft(session)
        service = DeveloperReplyService(session, client_factory=FailingSteamReplyClient)
        queued_record = await service.queue_reply(
            review.id,
            confirmed=True,
            draft_id=draft.id,
            content="final reply content",
        )
        with pytest.raises(DeveloperReplyError):
            await service.perform_send(queued_record.id)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reply-records/audit-queue")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "send_failed"
    assert "steam send failed" in (response.json()[0]["error_message"] or "")


async def seed_review_with_draft(session: AsyncSession) -> tuple[SteamReview, ReplyDraft]:
    session.add(SteamGame(app_id=3350200, name="test game"))
    review = SteamReview(
        app_id=3350200,
        recommendation_id="1001",
        steam_id="steam-a",
        review_text="test review",
        voted_up=False,
        votes_up=10,
        votes_funny=1,
        comment_count=0,
        timestamp_created=datetime(2026, 4, 28, 12, tzinfo=UTC),
        sync_type="stock",
        source_type="csv",
        processing_status="pending",
        reply_status="drafted",
    )
    session.add(review)
    await session.flush()
    draft = ReplyDraft(
        review_id=review.id,
        content="initial draft content",
        status="pending_review",
        model_name="qwen-plus",
    )
    session.add(draft)
    await session.commit()
    await session.refresh(review)
    await session.refresh(draft)
    return review, draft
