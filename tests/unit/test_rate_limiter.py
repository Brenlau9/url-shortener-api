from unittest.mock import Mock

from urlshortenerapi.services.rate_limiter import check_rate_limit


def test_rate_limiter_first_hit_sets_expire():
    r = Mock()
    r.incr.return_value = 1
    r.ttl.return_value = 59

    res = check_rate_limit(r, key="k", limit=3, window_seconds=60)

    r.expire.assert_called_once_with("k", 60)
    assert res.allowed is True
    assert res.remaining == 2
    assert res.reset_seconds == 59


def test_rate_limiter_subsequent_hit_does_not_set_expire():
    r = Mock()
    r.incr.return_value = 2
    r.ttl.return_value = 10

    res = check_rate_limit(r, key="k", limit=3, window_seconds=60)

    r.expire.assert_not_called()
    assert res.allowed is True
    assert res.remaining == 1
    assert res.reset_seconds == 10


def test_rate_limiter_blocks_when_over_limit():
    r = Mock()
    r.incr.return_value = 4
    r.ttl.return_value = 20

    res = check_rate_limit(r, key="k", limit=3, window_seconds=60)

    assert res.allowed is False
    assert res.remaining == 0
    assert res.reset_seconds == 20


def test_rate_limiter_ttl_fallback_when_missing():
    r = Mock()
    r.incr.return_value = 2
    r.ttl.return_value = -1  # Redis returns -1 or -2 depending on state

    res = check_rate_limit(r, key="k", limit=3, window_seconds=60)

    assert res.reset_seconds == 60
