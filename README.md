# URL Shortener API (FastAPI + Postgres + Redis)

A backend service that shortens URLs, redirects reliably, enforces per-API-key rate limits, supports link expiration and max clicks, and exposes analytics. Built with clean API design, migrations, Redis rate limiting, tests, coverage, and Docker.

---

## Features

- Create short links with optional custom alias
- 307 redirects via `GET /{code}`
- Expiration support (`expires_in_seconds`)
- Max clicks support (`max_clicks`)
- Disable links (owner-only)
- Owner-scoped link listing with cursor pagination
- Analytics endpoint (click count + last accessed)
- API key authentication via `X-API-Key`
- Per-API-key rate limiting (Redis token bucket)
- Standardized error responses
- Pytest + coverage (≥80%)
- Dockerized development environment

---

## Architecture Overview

### Stack

- **FastAPI** – API framework
- **PostgreSQL** – persistent storage
- **Redis** – rate limiting
- **SQLAlchemy 2.0** – ORM
- **Alembic** – migrations
- **Pytest + pytest-cov** – testing + coverage
- **Docker + Docker Compose** – local environment

### Data Model

**api_keys**
- id (uuid)
- key_hash
- name
- created_at

**links**
- id (uuid)
- owner_api_key_id (fk)
- code
- long_url
- created_at
- expires_at
- is_active
- max_clicks
- click_count
- last_accessed_at

---

## Authentication

All management endpoints require:

X-API-Key: `<your-api-key>`


Redirect (`GET /{code}`) is public.

---

## Rate Limiting

`POST /api/v1/links` is rate limited per API key.

- Default: 60 creates per minute
- Implemented using Redis token bucket
- Enforced atomically
- Returns headers:
    - X-RateLimit-Limit
    - X-RateLimit-Remaining
    - Retry-After

---

## Testing & Coverage

Run tests:

```bash
python -m pytest
```
Coverage is enforced at 80%+ via pytest-cov.

## 🐳 Docker Setup (Recommended)

### Requirements
- Docker
- Docker Compose

### 1. Build and start services
```bash
docker compose up -d --build
```
### 2. Run database migrations
```bash
docker compose exec api alembic upgrade head
```
### 3. Access API
Open:
```bash
http://localhost:8000/docs
```
## 💻 Local Setup (Without Docker)

### Requirements
Python 3.12
Postgres
Redis

### 1. Create virtual environment
```bash
python -m venv .venv
source .venv/bin/activate
```
### 2. Install dependencies
```bash
python -m pip install -e ".[dev]"
```
### 3. Create .env
```ini
DATABASE_URL=postgresql+psycopg://urlshortener:urlshortener@localhost:5432/urlshortener
REDIS_URL=redis://localhost:6379/0
APP_ENV=dev
```
### 4. Run migrations
```bash
alembic upgrade head
```
### 5. Start server
```bash
python -m uvicorn urlshortenerapi.main:app --reload
```
Open:
```bash
http://localhost:8000/docs
```
## API Usage Examples
### Health
```bash
curl http://localhost:8000/health
```
### Create Short Link
```bash
curl -X POST http://localhost:8000/api/v1/links \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{
    "url": "https://example.com",
    "custom_alias": "brendan_123",
    "expires_in_seconds": 3600,
    "max_clicks": 0
  }'
```
### Redirect
```bash
curl -I http://localhost:8000/brendan_123
```
### List Links
```bash
curl http://localhost:8000/api/v1/links \
  -H "X-API-Key: YOUR_KEY"
```
### Disable Link
```bash
curl -X PATCH http://localhost:8000/api/v1/links/brendan_123 \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{ "is_active": false }'
```
### Analytics
```bash
curl http://localhost:8000/api/v1/links/brendan_123/analytics \
  -H "X-API-Key: YOUR_KEY"
```
## Error Format

All API errors follow:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Link not found"
  }
}
```
Common codes:
- UNAUTHORIZED (401)
- FORBIDDEN (403)
- NOT_FOUND (404)
- CONFLICT (409)
- GONE (410)
- RATE_LIMITED (429)

## Project Status
- Full CRUD (minus hard delete)
- Rate limiting implemented
- Auth + ownership enforced
- Error standardization complete
- 90%+ test coverage
- Dockerized

## Future Improvements
- Daily click aggregation
- API key rotation & expiration
- Deployment to cloud (Render / Fly.io / AWS)
- Structured logging
- Metrics integration