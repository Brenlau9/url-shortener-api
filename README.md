# URL Shortener API

Backend URL shortener service built with FastAPI, PostgreSQL, and Redis.
Supports authenticated link management, public redirects, rate limiting,
expiration rules, analytics, and performance optimizations for
high-throughput redirect traffic.

## Tech Stack

-   FastAPI
-   PostgreSQL
-   Redis
-   SQLAlchemy 2.0
-   Alembic
-   Pytest
-   Docker / Docker Compose
-   k6

## Highlights

-   Versioned REST API (`/api/v1`)
-   API key authentication
-   Link ownership isolation
-   Cursor-based pagination
-   Redis-backed rate limiting
-   Redis link caching
-   Redis click-count buffering
-   Batched analytics flush to PostgreSQL
-   Alembic migrations
-   Dockerized local setup
-   GitHub Actions CI
-   k6 load testing

## Architecture

### Core Components

-   **FastAPI** serves management endpoints and redirect traffic
-   **PostgreSQL** stores API keys, links, and persisted analytics
-   **Redis** handles:
    -   link caching
    -   click-count buffering
    -   rate limiting
-   **Background flush task** batches buffered click counts into
    PostgreSQL

### Data Model

**api_keys** - `id` - `key_hash` - `name` - `created_at`

**links** - `id` - `owner_api_key_id` - `code` - `long_url` -
`created_at` - `expires_at` - `is_active` - `max_clicks` -
`click_count` - `last_accessed_at`

## Performance & Load Testing

The redirect endpoint was load tested with k6 using a
constant-arrival-rate workload to measure sustained throughput and
latency under concurrent traffic.

### Test Environment

-   FastAPI with 4 Uvicorn workers
-   PostgreSQL 16
-   Redis 7
-   Docker Compose on local macOS
-   2-minute sustained runs per target rate

### Optimization Summary

The initial redirect path performed a synchronous PostgreSQL update on
every request, causing the service to saturate at roughly **280 RPS**
with p95 latency above **1.8s**.

To remove this bottleneck, the redirect path was redesigned to:

-   buffer click counts in Redis using atomic `INCR`
-   cache link lookups in Redis
-   batch analytics writes back to PostgreSQL asynchronously
-   run with 4 Uvicorn worker processes

This removed database writes from the critical redirect path.

### Sustained Throughput Results

| Target RPS | p95 Latency | Result |
|-----------|-------------|--------|
| 1500 | 9.5ms | Stable |
| 2000 | 12.49ms | Stable |
| 2500 | 22.61ms | Stable |
| 3000 | 565ms | CPU saturation |

**Key Result:** sustained **2,500 RPS at p95 \< 25ms** with 0% HTTP
failures during steady-state testing.

## Authentication

Management endpoints require:

    X-API-Key: <your-api-key>

Public redirects do not require authentication.

## Rate Limiting

`POST /api/v1/links` is rate limited per API key.

-   Default: 60 creates per minute
-   Implemented with Redis
-   Enforced atomically
-   Returns headers:
    -   `X-RateLimit-Limit`
    -   `X-RateLimit-Remaining`
    -   `Retry-After`

## Quick Start with Docker

### Requirements

-   Docker
-   Docker Compose

### Start Services

    docker compose up -d --build

### Run Migrations

    docker compose exec api alembic upgrade head

### Open API Docs

    http://localhost:8000/docs

## Local Development

### Requirements

-   Python 3.12
-   PostgreSQL
-   Redis

### Setup

    python -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"

### Environment

    DATABASE_URL=postgresql+psycopg://urlshortener:urlshortener@localhost:5432/urlshortener
    REDIS_URL=redis://localhost:6379/0
    APP_ENV=dev

### Run Server

    python -m uvicorn urlshortenerapi.main:app --reload

## API Examples

### Health Check

    curl http://localhost:8000/health

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
### Analytics
```bash
curl http://localhost:8000/api/v1/links/brendan_123/analytics \
  -H "X-API-Key: YOUR_KEY"
```
## Testing

Run the test suite:

    pytest

Coverage target: **80%+**.

## Error Format

``` json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Link not found"
  }
}
```

Common error codes:

-   `UNAUTHORIZED`
-   `FORBIDDEN`
-   `NOT_FOUND`
-   `CONFLICT`
-   `GONE`
-   `RATE_LIMITED`

## Future Improvements

-   daily click aggregation
-   API key rotation and expiration
-   structured logging
-   metrics and observability
-   cloud deployment
