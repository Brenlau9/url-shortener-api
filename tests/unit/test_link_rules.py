from datetime import datetime, timezone, timedelta

from urlshortenerapi.core.link_rules import is_expired, max_clicks_exceeded


def test_is_expired_false_when_no_expires_at():
    now = datetime.now(timezone.utc)
    assert is_expired(None, now) is False


def test_is_expired_true_when_now_is_past_expires_at():
    now = datetime.now(timezone.utc)
    expires_at = now - timedelta(seconds=1)
    assert is_expired(expires_at, now) is True


def test_is_expired_true_when_equal_boundary():
    now = datetime.now(timezone.utc)
    assert is_expired(now, now) is True


def test_max_clicks_unlimited_when_none():
    assert max_clicks_exceeded(None, 999) is False


def test_max_clicks_exceeded_boundary():
    assert max_clicks_exceeded(1, 0) is False
    assert max_clicks_exceeded(1, 1) is True
    assert max_clicks_exceeded(3, 3) is True
