# URL Shortener API

Production-style backend service that shortens URLs, redirects reliably, enforces rate limits, supports link expiration, and tracks basic click analytics.

> Current state: Create + redirect endpoints are implemented, with Redis-based rate limiting utilities and basic tests.
> (Auth/API keys, full spec rate limiting on create, expiration, analytics endpoint, CI, and Dockerfile docs are planned next.)

## Tech Stack
- Python 3.12
- FastAPI
- PostgreSQL (Docker)
- Redis (Docker)
- SQLAlchemy + Alembic
- pytest

## Setup (Local Dev)

### 1) Prerequisites
- Python **3.12.x**
- Docker + Docker Compose

(Optional) If you use `pyenv`, this repo includes a `.python-version` file.

### 2) Start dependencies (Postgres + Redis)
```bash
docker compose up -d
docker compose ps
