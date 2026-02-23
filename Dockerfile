# syntax=docker/dockerfile:1

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Copy packaging metadata AND source BEFORE editable install
COPY pyproject.toml ./
COPY src ./src

RUN python -m pip install --upgrade pip \
  && python -m pip install -e ".[dev]" \
  && python -m pip cache purge

# Copy remaining runtime files
COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000

ENV APP_ENV=dev

CMD ["python", "-m", "uvicorn", "urlshortenerapi.main:app", "--host", "0.0.0.0", "--port", "8000"]