from fastapi import APIRouter, status, HTTPException, Depends
from fastapi.responses import RedirectResponse
from urlshortenerapi.schemas.links import CreateLinkRequest, LinkResponse, LinkStatsResponse
from sqlalchemy.orm import Session
from urlshortenerapi.db.session import get_db
from urlshortenerapi.db.models import Link
from datetime import datetime, timezone
import secrets

from urlshortenerapi.api.deps import get_current_api_key
from urlshortenerapi.db.models import ApiKey


router = APIRouter(prefix="/api/v1")

@router.post("/links", 
          response_model=LinkResponse, 
          status_code=status.HTTP_201_CREATED
)
def create_link(
    req: CreateLinkRequest, 
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key)
    ):
    code = secrets.token_urlsafe(6)

    link = Link(
        code=code,
        long_url=str(req.url),
        created_at=datetime.now(timezone.utc),
        owner_api_key_id=api_key.id,
    )

    db.add(link)
    db.commit()
    db.refresh(link)

    return LinkResponse(
        code=link.code,
        long_url=link.long_url,
        created_at=link.created_at,
        expires_at=None,
        is_active=link.is_active,
    )

@router.get("/links/{code}", response_model=LinkStatsResponse)
def get_link_stats(
    code: str, 
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key)
    ):
    link = (
    db.query(Link)
    .filter(Link.code == code, Link.owner_api_key_id == api_key.id)
    .first()
    )

    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    
    return link

