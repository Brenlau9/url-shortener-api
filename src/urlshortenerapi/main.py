from fastapi import FastAPI
from urlshortenerapi.api.routes import router as api_router
from urlshortenerapi.db.session import engine
from urlshortenerapi.db.base import Base
from urlshortenerapi.db import models

Base.metadata.create_all(bind=engine)

app = FastAPI(title="URL Shortener API")
app.include_router(api_router)

@app.get("/health")
def health():
    return {"status": "ok"}
