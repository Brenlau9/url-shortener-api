from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

class CreateLinkRequest(BaseModel):
    url: HttpUrl
    custom_alias: Optional[str] = None
    expires_in_seconds: Optional[int] = None

class LinkResponse(BaseModel):
    code: str
    long_url: HttpUrl
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool

