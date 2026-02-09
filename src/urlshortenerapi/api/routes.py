from __future__ import annotations

import base64
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, status, HTTPException, Depends, Request, Response, Query
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from urlshortenerapi.api.deps import get_current_api_key, create_rate_limiter
from urlshortenerapi.db.models import Link, ApiKey
from urlshortenerapi.db.session import get_db
from urlshortenerapi.schemas.links import (
    CreateLinkRequest,
    LinkResponse,
    LinkStatsResponse,
    LinkListResponse,
    LinkListItem,
    PatchLinkRequest,
)

router = APIRouter(prefix="/api/v1")

_BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _base62_code(length: int) -> str:
    return "".join(secrets.choice(_BASE62_ALPHABET) for _ in range(length))


def _encode_cursor(created_at: datetime, link_id) -> str:
    raw = f"{created_at.isoformat()}|{str(link_id)}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        ts_s, id_s = raw.split("|", 1)
        return datetime.fromisoformat(ts_s), id_s
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cursor")


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
    if getattr(req, "expires_in_seconds", None) is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=req.expires_in_seconds)

    # Normalize max_clicks: 0 => unlimited => store None
    max_clicks = None
    if hasattr(req, "max_clicks"):
        max_clicks = None if (req.max_clicks is None or req.max_clicks == 0) else req.max_clicks

    # If custom alias is provided, try it once and return 409 on collision
    if getattr(req, "custom_alias", None) is not None:
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
        code = _base62_code(7)  # 6–8 chars spec

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


@router.get("/links", response_model=LinkListResponse)
def list_links(
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
):
    q = (
        db.query(Link)
        .filter(Link.owner_api_key_id == api_key.id)
        .order_by(Link.created_at.desc(), Link.id.desc())
    )

    if cursor is not None:
        cursor_created_at, cursor_id = _decode_cursor(cursor)
        q = q.filter(
            or_(
                Link.created_at < cursor_created_at,
                and_(Link.created_at == cursor_created_at, Link.id < cursor_id),
            )
        )

    rows = q.limit(limit + 1).all()
    has_next = len(rows) > limit
    items = rows[:limit]

    next_cursor = None
    if has_next and items:
        last = items[-1]
        next_cursor = _encode_cursor(last.created_at, last.id)

    return LinkListResponse(
        items=[LinkListItem.model_validate(x) for x in items],
        next_cursor=next_cursor,
    )


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


@router.patch("/links/{code}", response_model=LinkStatsResponse)
def patch_link(
    code: str,
    req: PatchLinkRequest,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_current_api_key),
):
    link = (
        db.query(Link)
        .filter(Link.code == code, Link.owner_api_key_id == api_key.id)
        .first()
    )

    if link is None:
        # 404 prevents leaking link existence across tenants
        raise HTTPException(status_code=404, detail="Link not found")

    link.is_active = req.is_active
    db.commit()
    db.refresh(link)
    return link
