# syntax=docker/dockerfile:1

FROM python:3.12-slim AS runtime

# Prevents Python from writing .pyc files and buffers
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (optional but common for psycopg / builds; keep minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Install deps first for better Docker layer caching
COPY pyproject.toml ./
# If you have a lockfile, copy it too:
# COPY uv.lock ./
# COPY poetry.lock ./
# COPY requirements.txt ./

RUN python -m pip install --upgrade pip \
  && python -m pip install -e ".[dev]" \
  && python -m pip cache purge

# Copy app source
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000

# Default envs (compose can override)
ENV APP_ENV=dev

# Use python -m uvicorn per your repo standard
CMD ["python", "-m", "uvicorn", "urlshortenerapi.main:app", "--host", "0.0.0.0", "--port", "8000"]
