from __future__ import annotations
from datetime import datetime
from typing import Optional


def is_expired(expires_at: Optional[datetime], now: datetime) -> bool:
    return expires_at is not None and now >= expires_at


def max_clicks_exceeded(max_clicks: Optional[int], click_count: int) -> bool:
    # max_clicks None means unlimited
    if max_clicks is None:
        return False
    return click_count >= max_clicks
