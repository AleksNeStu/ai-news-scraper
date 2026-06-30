# =====================================================
# AI News Scraper — API (FastAPI) Dockerfile
# =====================================================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_HOME=/opt/poetry \
    # Aligned with CI: ci.yml runs `pip install poetry` which always
    # picks up the latest. Pin to 2.x so the Docker build matches
    # what GitHub Actions installs (Poetry 1.8 silently tolerated
    # the duplicate asyncpg dep that Poetry 2.x rejects — see
    # commit 15eb638 for context).
    POETRY_VERSION=2.1.3

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="$POETRY_HOME/bin:$PATH"

WORKDIR /app

# Copy workspace-level files first for better layer caching
COPY pyproject.toml poetry.lock* /app/
COPY apps/api /app/apps/api

WORKDIR /app/apps/api

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main

EXPOSE 8082

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8082"]
