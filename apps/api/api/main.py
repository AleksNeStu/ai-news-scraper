"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.middleware.logging import RequestIDMiddleware, configure_logging
from api.routers import articles, auth, feeds, health, scrape, search

logger = logging.getLogger(__name__)
_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Per ADR-009 §9.5: JSON logging setup runs at the top of lifespan
    # startup, before any router is mounted. Handlers attached by any
    # earlier ``logging.basicConfig`` are detached inside
    # ``configure_logging`` so we don't double-emit.
    configure_logging(_settings.log_level)
    logger.info("API starting up (env=%s)", _settings.app_env)
    yield
    logger.info("API shutting down")


app = FastAPI(
    title="AI News Search API",
    version="0.1.0",
    description="Backend for AI News Scraper — Next.js 16 + FastAPI monorepo.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — must be registered AFTER RequestIDMiddleware so Starlette wraps
# CORS outermost. CORS preflight (OPTIONS) requests short-circuit inside
# CORS, so the request ID has to be set by middleware that runs even
# on preflight. Per ADR-009 §Implementation notes.
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routers
app.include_router(auth.router)
app.include_router(articles.router)
app.include_router(scrape.router)
app.include_router(search.router)
app.include_router(feeds.router)
app.include_router(health.router)
