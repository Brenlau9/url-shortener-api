import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from sqlalchemy import update, func

from urlshortenerapi.api.routes import router as api_router
from urlshortenerapi.api.deps import redirect_rate_limiter
from urlshortenerapi.db.session import get_db, SessionLocal
from urlshortenerapi.db.models import Link
from urlshortenerapi.core.errors import normalize_http_exception, STATUS_TO_ERROR_CODE
from urlshortenerapi.core.redis import get_redis_client as _make_redis_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Single shared Redis client (lru_cache = one instance, one pool)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_redis_client():
    """
    Returns a single shared Redis client for the lifetime of the process.
    lru_cache ensures the underlying connection pool is reused across requests
    instead of constructing a new client object on every call.
    """
    return _make_redis_client()


# ---------------------------------------------------------------------------
# Click-count buffering (Redis -> Postgres flush)
# ---------------------------------------------------------------------------

CLICK_KEY_PREFIX = "clicks:"
LAST_ACCESSED_KEY_PREFIX = "last_accessed:"
FLUSH_INTERVAL_SECONDS = 5


async def _flush_click_counts() -> None:
    """
    Background task: every FLUSH_INTERVAL_SECONDS, drain all
    'clicks:{code}' keys from Redis and apply them to Postgres.
    Uses GETDEL so counts are never double-counted if the flush is slow.
    """
    r = get_redis_client()
    while True:
        await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
        try:
            keys = list(r.scan_iter(f"{CLICK_KEY_PREFIX}*"))
            if not keys:
                continue

            with SessionLocal() as db:
                for key in keys:
                    raw = r.getdel(key)
                    if not raw:
                        continue
                    count = int(raw)
                    code = key[len(CLICK_KEY_PREFIX) :]

                    ts_raw = r.getdel(f"{LAST_ACCESSED_KEY_PREFIX}{code}")
                    last_accessed = datetime.fromisoformat(ts_raw) if ts_raw else func.now()

                    db.execute(
                        update(Link)
                        .where(Link.code == code)
                        .values(
                            click_count=Link.click_count + count,
                            last_accessed_at=last_accessed,
                        )
                    )
                db.commit()

        except Exception:
            logger.exception("Error flushing click counts from Redis to Postgres")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_flush_click_counts())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# Redis link cache
# ---------------------------------------------------------------------------

LINK_CACHE_PREFIX = "link_cache:"
LINK_CACHE_TTL = 60  # seconds — tune to taste


def _get_link(code: str, db: Session, r) -> Link | None:
    """
    Look up a link by code. Checks Redis first; falls back to Postgres on
    a cache miss and populates the cache for subsequent requests.

    Only immutable / slow-changing fields are cached (long_url, is_active,
    expires_at, max_clicks). click_count is intentionally stored as the
    Postgres value at cache-fill time; the redirect path adds the live Redis
    buffer on top before enforcing max_clicks, so accuracy is maintained.
    """
    cache_key = f"{LINK_CACHE_PREFIX}{code}"
    cached = r.get(cache_key)

    if cached:
        data = json.loads(cached)
        link = Link()
        link.id = data["id"]
        link.code = data["code"]
        link.long_url = data["long_url"]
        link.is_active = data["is_active"]
        link.expires_at = datetime.fromisoformat(data["expires_at"]) if data["expires_at"] else None
        link.max_clicks = data["max_clicks"]
        link.click_count = data["click_count"]
        return link

    # Cache miss — hit Postgres and populate
    link = db.query(Link).filter(Link.code == code).first()
    if link:
        r.setex(
            cache_key,
            LINK_CACHE_TTL,
            json.dumps(
                {
                    "id": str(link.id),
                    "code": link.code,
                    "long_url": link.long_url,
                    "is_active": link.is_active,
                    "expires_at": link.expires_at.isoformat() if link.expires_at else None,
                    "max_clicks": link.max_clicks,
                    "click_count": link.click_count,
                }
            ),
        )
    return link


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="URL Shortener API", lifespan=lifespan)
app.include_router(api_router)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    err = normalize_http_exception(exc)
    headers = getattr(exc, "headers", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": err.code, "message": err.message}},
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": STATUS_TO_ERROR_CODE[422],
                "message": "Invalid request body or parameters.",
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": {"code": STATUS_TO_ERROR_CODE[500], "message": "Internal server error."}},
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Redirect helpers
# ---------------------------------------------------------------------------


def _raise_if_unusable(link: Link, now: datetime) -> None:
    if not link.is_active:
        raise HTTPException(status_code=403, detail="Link is disabled")

    if link.expires_at is not None and now >= link.expires_at:
        raise HTTPException(status_code=410, detail="Link is expired")

    if link.max_clicks is not None and link.click_count >= link.max_clicks:
        raise HTTPException(status_code=410, detail="Max clicks exceeded")


# ---------------------------------------------------------------------------
# Redirect endpoints
# ---------------------------------------------------------------------------


@app.head("/{code}")
def redirect_head(code: str, db: Session = Depends(get_db)):
    r = get_redis_client()
    link = _get_link(code, db, r)
    if link is None:
        raise HTTPException(status_code=404, detail="Not Found")

    now = datetime.now(timezone.utc)
    _raise_if_unusable(link, now)

    # HEAD should not increment analytics
    return RedirectResponse(url=link.long_url, status_code=307)


@app.get("/{code}")
def redirect(code: str, db: Session = Depends(get_db), _: None = Depends(redirect_rate_limiter)):
    r = get_redis_client()
    link = _get_link(code, db, r)

    if link is None:
        raise HTTPException(status_code=404, detail="Not Found")

    now = datetime.now(timezone.utc)

    # Add unflushed Redis buffer to in-memory count so max_clicks is accurate
    buffered = int(r.get(f"{CLICK_KEY_PREFIX}{link.code}") or 0)
    link.click_count = link.click_count + buffered

    _raise_if_unusable(link, now)

    # Buffer click in Redis — flushed to Postgres every FLUSH_INTERVAL_SECONDS
    r.incr(f"{CLICK_KEY_PREFIX}{link.code}")
    r.set(f"{LAST_ACCESSED_KEY_PREFIX}{link.code}", now.isoformat(), ex=300)

    return RedirectResponse(url=link.long_url, status_code=307)
