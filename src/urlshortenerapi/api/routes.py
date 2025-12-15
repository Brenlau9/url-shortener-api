from fastapi import APIRouter, status, HTTPException
from fastapi.responses import RedirectResponse
from urlshortenerapi.schemas.links import CreateLinkRequest, LinkResponse
from datetime import datetime, timezone

router = APIRouter(prefix="/api/v1")

@router.post("/links", 
          response_model=LinkResponse, 
          status_code=status.HTTP_201_CREATED
)
def create_link(req: CreateLinkRequest):
    return LinkResponse(
        code="abc123",
        long_url=req.url,
        created_at=datetime.now(timezone.utc),
        expires_at=None,
        is_active=True,
    )

@router.get("/{code}")
def redirect(code: str):
    if code != "abc123":
        raise HTTPException(status_code=404, detail="Not found")
    
    return RedirectResponse(
        url="https://example.com",
        status_code=307
    )