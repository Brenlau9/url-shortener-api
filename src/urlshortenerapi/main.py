from fastapi import FastAPI
from urlshortenerapi.api.routes import router as api_router

app = FastAPI(title="URL Shortener API")
app.include_router(api_router)

@app.get("/health")
def health():
    return {"status": "ok"}
