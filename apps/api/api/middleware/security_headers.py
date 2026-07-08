"""Security headers middleware.

Per the production deploy runbook (``.agent/adr/014-deploy-target.md``
§14.7 hardening) and the web security checklist, every response from
the API gets a baseline of browser-facing security headers:

* ``Strict-Transport-Security`` — only in production; tells browsers to
  refuse plain-HTTP for one year, including subdomains. Skipped in
  dev/staging so local ``http://localhost:8007`` keeps working without
  the dev browser complaining.
* ``X-Content-Type-Options: nosniff`` — disables MIME sniffing; blocks a
  class of XSS where a text file is interpreted as a script.
* ``X-Frame-Options: DENY`` — refuses to be embedded in an iframe, so
  the API cannot be wrapped by a malicious origin to harvest cookies
  / auth tokens via clickjacking.
* ``Referrer-Policy: strict-origin-when-cross-origin`` — sends full
  Referer to same-origin requests, origin-only cross-origin, nothing
  on protocol downgrade. Matches the GitHub-style default.
* ``Content-Security-Policy`` — locks down what the response can be
  used for. ``connect-src`` includes the configured ``NEXT_PUBLIC_API_URL``
  so browser callers from the web app can still fetch us; ``frame-ancestors
  'none'`` is a stronger form of X-Frame-Options that also covers CSP-aware
  browsers.

The middleware is registered AFTER ``CORSMiddleware`` so it sits
**innermost** in the Starlette stack — meaning the headers ride on
**every** response including OPTIONS preflights that CORS short-circuits
before they reach the inner app. (If we registered it outermost, the
preflight responses returned directly by CORS would not carry these
headers.)
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from api.config import get_settings

_settings = get_settings()


def _build_csp() -> str:
    """Compose the CSP ``connect-src`` from settings + a safe default.

    The web app's browser-side fetcher targets ``$NEXT_PUBLIC_API_URL``
    in production. We default to ``'self'`` so a misconfigured web
    build (no NEXT_PUBLIC_API_URL) still gets a working API at the same
    origin. The framework strips duplicate sources; we do not dedupe
    here because the directive order is irrelevant to the parser.
    """
    api_origin = (
        _settings.cors_allow_origins[0] if _settings.cors_allow_origins else "'self'"
    )
    return (
        "default-src 'self'; "
        "img-src 'self' https: data:; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        f"connect-src 'self' {api_origin}; "
        "frame-ancestors 'none'"
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach the security-headers baseline to every response."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._csp = _build_csp()
        self._is_prod = _settings.app_env == "production"

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        response.headers.setdefault("Content-Security-Policy", self._csp)
        if self._is_prod:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


__all__ = ["SecurityHeadersMiddleware"]
