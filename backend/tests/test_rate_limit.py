from app.rate_limit import DailyRateLimiter


def test_rate_limiter_blocks_after_limit() -> None:
    limiter = DailyRateLimiter(limit=2)
    assert limiter.check("client") == (True, 1)
    assert limiter.check("client") == (True, 0)
    assert limiter.check("client") == (False, 0)
    assert limiter.check("another-client")[0] is True
