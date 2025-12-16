from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import update

from urlshortenerapi.api.routes import router as api_router
from urlshortenerapi.db.session import engine, get_db
from urlshortenerapi.db.base import Base
from urlshortenerapi.db import models
from urlshortenerapi.db.models import Link

Base.metadata.create_all(bind=engine)

app = FastAPI(title="URL Shortener API")
app.include_router(api_router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.head("/{code}")
def redirect(code: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter(Link.code == code).first()

    if link is None:
        raise HTTPException(status_code=404, detail="Not Found")
    if not link.is_active:
        raise HTTPException(status_code=403, detail="Link is disabled")
    
    return RedirectResponse(url=link.long_url, status_code=307)

@app.get("/{code}")
def redirect(code: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter(Link.code == code).first()

    if link is None:
        raise HTTPException(status_code=404, detail="Not Found")
    if not link.is_active:
        raise HTTPException(status_code=403, detail="Link is disabled")

    # Increment click_count 
    db.execute(update(Link).where(Link.id==link.id).values(click_count=Link.click_count+1))
    db.commit()

    return RedirectResponse(url=link.long_url, status_code=307)
