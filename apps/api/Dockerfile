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
# Poetry 2.x validates ``readme = "../../README.md"`` from
# apps/api/pyproject.toml during ``poetry install``; the file must
# exist at the path it resolves to (``/app/README.md``). The legacy
# repo-root ``pyproject.toml`` was the original reason the Dockerfile
# only copied the root-level files; once ``apps/api`` started
# referencing a repo-root readme, the COPY below became required.
COPY README.md /app/README.md
COPY apps/api /app/apps/api

WORKDIR /app/apps/api

RUN poetry config virtualenvs.create false \
    # ADR-016 §16.11: install the optional ``observability`` extra so
    # the api ships with sentry-sdk wired in. The extra is declared
    # in pyproject.toml (``[tool.poetry.extras] observability``) and
    # adds only sentry-sdk; the rest of the api's deps are unchanged.
    && poetry install --no-interaction --no-ansi --only main --extras observability

# ---- Non-root runtime user ------------------------------------------------
# Production hardening: drop root before CMD. Build steps above
# (apt-get, poetry install) need root; pivot to ``appuser`` here so the
# uvicorn worker runs unprivileged. /app is chowned to appuser so
# dev bind-mounts remain writable.
RUN groupadd -r appuser \
    && useradd -r -g appuser -d /app -s /sbin/nologin appuser \
    && chown -R appuser:appuser /app

# ---- Healthcheck ----------------------------------------------------------
# In-container probe mirroring the docker-compose probe. Stdlib only.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2).read()"

USER appuser

# Container port = 8000 (uvicorn / FastAPI default). Host port is
# allocated by the canonical port-registry file -- for ai-news-scraper
# that is 8007; compose maps ``8007:8000``. Do not change the
# container port without also updating ``apps/api/api/config.py``
# (``api_port``), ``docker-compose.yml`` (env, healthcheck, port
# mapping), and the build-time ``API_INTERNAL_URL`` arg consumed
# by ``apps/web/Dockerfile`` / ``docker-compose.yml``.
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
