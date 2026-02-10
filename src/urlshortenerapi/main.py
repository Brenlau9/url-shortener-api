from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from sqlalchemy import update

from urlshortenerapi.api.routes import router as api_router
from urlshortenerapi.api.deps import redirect_rate_limiter
from urlshortenerapi.db.session import get_db
from urlshortenerapi.db.models import Link
from urlshortenerapi.core.errors import normalize_http_exception, STATUS_TO_ERROR_CODE

app = FastAPI(title="URL Shortener API")
app.include_router(api_router)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    err = normalize_http_exception(exc)
    # Preserve headers like Retry-After (important for 429)
    headers = getattr(exc, "headers", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": err.code, "message": err.message}},
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Keep message simple (or concatenate field errors if you want)
    return JSONResponse(
        status_code=422,
        content={"error": {"code": STATUS_TO_ERROR_CODE[422], "message": "Invalid request body or parameters."}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Avoid leaking internals
    return JSONResponse(
        status_code=500,
        content={"error": {"code": STATUS_TO_ERROR_CODE[500], "message": "Internal server error."}},
    )

@app.get("/health")
def health():
    return {"status": "ok"}


def _raise_if_unusable(link: Link, now: datetime) -> None:
    if not link.is_active:
        raise HTTPException(status_code=403, detail="Link is disabled")

    if link.expires_at is not None and now >= link.expires_at:
        raise HTTPException(status_code=410, detail="Link is expired")

    # max_clicks: None means unlimited (per your create endpoint normalization)
    if link.max_clicks is not None and link.click_count >= link.max_clicks:
        raise HTTPException(status_code=410, detail="Max clicks exceeded")


@app.head("/{code}")
def redirect_head(code: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter(Link.code == code).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Not Found")

    now = datetime.now(timezone.utc)
    _raise_if_unusable(link, now)

    # HEAD should not increment analytics
    return RedirectResponse(url=link.long_url, status_code=307)


@app.get("/{code}")
def redirect(code: str, db: Session = Depends(get_db), _: None = Depends(redirect_rate_limiter)):
    link = db.query(Link).filter(Link.code == code).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Not Found")

    now = datetime.now(timezone.utc)
    _raise_if_unusable(link, now)

    # Increment click_count and set last_accessed_at atomically
    db.execute(
        update(Link)
        .where(Link.id == link.id)
        .values(
            click_count=Link.click_count + 1,
            last_accessed_at=now,
        )
    )
    db.commit()

    return RedirectResponse(url=link.long_url, status_code=307)
