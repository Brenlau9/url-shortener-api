from fastapi import APIRouter, status, HTTPException, Depends
from fastapi.responses import RedirectResponse
from urlshortenerapi.schemas.links import CreateLinkRequest, LinkResponse
from sqlalchemy.orm import Session
from urlshortenerapi.db.session import get_db
from urlshortenerapi.db.models import Link
from datetime import datetime, timezone
import secrets

router = APIRouter(prefix="/api/v1")

@router.post("/links", 
          response_model=LinkResponse, 
          status_code=status.HTTP_201_CREATED
)
def create_link(req: CreateLinkRequest, db: Session = Depends(get_db)):
    code = secrets.token_urlsafe(6)

    link = Link(
        code=code,
        long_url=str(req.url),
        created_at=datetime.now(timezone.utc),
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

@router.get("/{code}")
def redirect(code: str):
    if code != "abc123":
        raise HTTPException(status_code=404, detail="Not found")
    
    return RedirectResponse(
        url="https://example.com",
        status_code=307
    )