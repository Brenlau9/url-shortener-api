from pydantic import BaseModel, HttpUrl, ConfigDict, field_validator
from typing import Optional
from datetime import datetime
import re
from typing import List


_ALIAS_RE = re.compile(r"^[a-zA-Z0-9_-]{3,32}$")


class CreateLinkRequest(BaseModel):
    url: HttpUrl
    custom_alias: Optional[str] = None
    expires_in_seconds: Optional[int] = None
    max_clicks: Optional[int] = 0  # 0 means unlimited

    @field_validator("custom_alias")
    @classmethod
    def validate_custom_alias(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not _ALIAS_RE.fullmatch(v):
            raise ValueError("custom_alias must match ^[a-zA-Z0-9_-]{3,32}$")
        return v

    @field_validator("expires_in_seconds")
    @classmethod
    def validate_expires(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return None
        if v <= 0:
            raise ValueError("expires_in_seconds must be a positive integer")
        return v

    @field_validator("max_clicks")
    @classmethod
    def validate_max_clicks(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return 0
        if v < 0:
            raise ValueError("max_clicks must be >= 0")
        return v


class LinkResponse(BaseModel):
    code: str
    short_url: str
    long_url: str
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    max_clicks: Optional[int] = None  # None means unlimited


class LinkStatsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    long_url: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool
    click_count: int
    max_clicks: Optional[int] = None


class LinkListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    long_url: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool
    click_count: int
    last_accessed_at: Optional[datetime] = None
    max_clicks: Optional[int] = None


class LinkListResponse(BaseModel):
    items: List[LinkListItem]
    next_cursor: Optional[str] = None


class PatchLinkRequest(BaseModel):
    is_active: bool


class LinkAnalyticsResponse(BaseModel):
    click_count: int
    last_accessed_at: Optional[datetime] = None
