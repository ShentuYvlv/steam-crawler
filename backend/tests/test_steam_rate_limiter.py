import httpx

from src.utils.steam_rate_limiter import SteamRateLimiter


async def test_probe_success_resets_failure_streak_and_cooldown() -> None:
    limiter = SteamRateLimiter()

    for _ in range(4):
        await limiter.record_error(httpx.ReadTimeout("probe timeout"))

    snapshot = await limiter.snapshot()
    assert snapshot["failure_streak"] == 4
    assert snapshot["mode"] == "cooldown"

    await limiter.record_success(reset_failures=True)

    snapshot = await limiter.snapshot()
    assert snapshot["failure_streak"] == 0
    assert snapshot["cooldown_remaining_seconds"] == 0
    assert snapshot["mode"] == "fast"
