from fastapi import APIRouter, status, HTTPException, Depends, Request
from urlshortenerapi.schemas.links import CreateLinkRequest, LinkResponse, LinkStatsResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from urlshortenerapi.db.session import get_db
from urlshortenerapi.db.models import Link, ApiKey
from datetime import datetime, timezone, timedelta
import secrets

from urlshortenerapi.api.deps import get_current_api_key
from fastapi import Request, Response
from urlshortenerapi.api.deps import create_rate_limiter



router = APIRouter(prefix="/api/v1")

_BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _base62_code(length: int) -> str:
    return "".join(secrets.choice(_BASE62_ALPHABET) for _ in range(length))


@router.post(
    "/links",
    response_model=LinkResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.post("/links", response_model=LinkResponse, status_code=status.HTTP_201_CREATED)
def create_link(
    req: CreateLinkRequest,
    request: Request,
    response: Response,
    _: None = Depends(create_rate_limiter),
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
):
    # set headers using what deps.py stored
    response.headers["X-RateLimit-Limit"] = str(request.state.create_rl_limit)
    response.headers["X-RateLimit-Remaining"] = str(request.state.create_rl_remaining)
    # Compute expires_at
    expires_at = None
    if req.expires_in_seconds is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=req.expires_in_seconds)

    # Normalize max_clicks: 0 => unlimited => store None
    max_clicks = None if (req.max_clicks is None or req.max_clicks == 0) else req.max_clicks

    # If custom alias is provided, try it once and return 409 on collision
    if req.custom_alias is not None:
        link = Link(
            code=req.custom_alias,
            long_url=str(req.url),
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            max_clicks=max_clicks,
            owner_api_key_id=api_key.id,
        )
        db.add(link)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Alias already taken")
        db.refresh(link)

        short_url = str(request.base_url).rstrip("/") + f"/{link.code}"
        return LinkResponse(
            code=link.code,
            short_url=short_url,
            long_url=link.long_url,
            created_at=link.created_at,
            expires_at=link.expires_at,
            is_active=link.is_active,
            max_clicks=link.max_clicks,
        )

    # Otherwise generate a random base62 code and retry on collision
    for _ in range(10):
        code = _base62_code(7)  # choose 7 chars (fits “6–8 chars” spec)

        link = Link(
            code=code,
            long_url=str(req.url),
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            max_clicks=max_clicks,
            owner_api_key_id=api_key.id,
        )
        db.add(link)
        try:
            db.commit()
            db.refresh(link)
            short_url = str(request.base_url).rstrip("/") + f"/{link.code}"
            return LinkResponse(
                code=link.code,
                short_url=short_url,
                long_url=link.long_url,
                created_at=link.created_at,
                expires_at=link.expires_at,
                is_active=link.is_active,
                max_clicks=link.max_clicks,
            )
        except IntegrityError:
            db.rollback()
            continue

    raise HTTPException(status_code=500, detail="Failed to generate unique short code")


@router.get("/links/{code}", response_model=LinkStatsResponse)
def get_link_stats(
    code: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
):
    link = (
        db.query(Link)
        .filter(Link.code == code, Link.owner_api_key_id == api_key.id)
        .first()
    )

    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")

    return link
