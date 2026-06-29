"""APScheduler bridge for the AI Brief cron (Task #8, ADR-012 §12.3 + §12.10).

The brief fires daily at 08:00 in the user's local timezone. Because
APScheduler's ``BackgroundScheduler`` runs jobs in a *thread* but we
need to share the asyncio loop with the FastAPI request handlers, we
use ``AsyncIOScheduler`` instead. The scheduler is created inside
``lifespan`` startup (NOT at import time) so a ``pytest`` import does
not auto-start a background tick.

For the v1 scope this module ships a single per-user daily job plus a
hand-rolled ``run_for_user(user_id, for_date)`` entry point the
router can hit directly while we are still building out the end-to-end
delivery path.

M5 / ADR-012 §12.10 — cron logging contract: every callback sets the
shared ``_request_id_var`` ContextVar (defined in
``api.middleware.logging``) to a per-job value
``cron-<uuid12>`` for the duration of the job and emits
``extra={"job_id": ...}`` on the start / end / error log lines so
log-search-to-job is a one-step lookup. The ContextVar wrap is the
same one ``RequestIDMiddleware`` uses for HTTP requests, so the
JSON formatter picks the id up automatically.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time, timezone
from typing import Any
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from api.config import get_settings
from api.db.database import AsyncSessionLocal
from api.middleware.logging import _request_id_var
from api.models.user import User
from api.services.digest import generate_digest

logger = logging.getLogger(__name__)


# Stable, harmless pytz-free UTC default. ``zoneinfo`` is stdlib in 3.9+;
# falls back to UTC if a user has a malformed tz string.
_DEFAULT_TZ = timezone.utc


class BriefScheduler:
    """Thin wrapper around ``AsyncIOScheduler`` for the AI Brief.

    Lifecycle:

    * ``await scheduler.start()`` — called from the FastAPI lifespan
      startup hook. Must NOT run at import time (test safety).
      Refuses to start when ``settings.effective_digest_enabled`` is
      ``False`` (M6 — defensive depth: callers can also gate this in
      main.py, but the class itself checks so it is safe to use
      directly in tests / scripts).
    * ``await scheduler.stop()`` — called from the lifespan shutdown.
    * ``scheduler.run_for_user(user_id, for_date)`` — ad-hoc entry
      point for the router and the scheduler tick itself.
    """

    def __init__(self) -> None:
        # Job defaults — the AsyncIOScheduler runs the coroutine on the
        # currently-running event loop. We do NOT install ``default``
        # threadpool extras; this is purely async.
        self._sched: AsyncIOScheduler | None = None

    async def start(self) -> None:
        """Create the scheduler, register the daily tick, start the loop."""
        if self._sched is not None:
            return
        s = get_settings()
        # M6 — defensive: refuse to schedule when the brief subsystem is
        # disabled. ``main.py`` already gates this, but the class checks
        # too so it is safe to instantiate outside the lifespan.
        if not s.effective_digest_enabled:
            logger.warning(
                "BriefScheduler: digest disabled "
                "(settings.effective_digest_enabled=False); not started"
            )
            return
        sched = AsyncIOScheduler(timezone="UTC")
        # Master daily tick: 08:00 UTC. The tick body iterates users and
        # computes the per-user 08:00 from each user's stored tz. We keep
        # the master on UTC to avoid the DST gotcha documented in
        # ADR-012 §12.9 (the user-local hour is computed inside the job).
        # ``from_crontab("0 8 * * *")`` mirrors the spec notation
        # verbatim. ``misfire_grace_time=300`` (5 min) — the spec value;
        # anything longer would mean a worker restart fires back-to-back
        # catch-ups.
        sched.add_job(
            self._daily_tick,
            CronTrigger.from_crontab("0 8 * * *"),
            id="brief-daily-tick",
            replace_existing=True,
            misfire_grace_time=300,
        )
        sched.start()
        self._sched = sched
        logger.info("BriefScheduler started")

    async def stop(self) -> None:
        """Shut down the scheduler; idempotent."""
        if self._sched is None:
            return
        try:
            self._sched.shutdown(wait=False)
        except Exception as e:  # noqa: BLE001 — best-effort
            logger.warning("BriefScheduler.shutdown raised: %s", e)
        finally:
            self._sched = None

    async def _daily_tick(self) -> None:
        """Iterate users and run today's digest for each.

        Per ADR-012 §12.4: idempotent (``generate_digest`` is). Failures
        on one user don't take down the others.
        """
        today_utc = datetime.now(timezone.utc).date()
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(User.id))
            user_ids = [row[0] for row in res.all()]
        for uid in user_ids:
            await self.run_for_user(uid, today_utc)

    async def run_for_user(self, user_id: UUID, for_date: date) -> Any:
        """Run one (user, date) digest. Returns the persisted ``Digest``.

        M5 / ADR-012 §12.10: sets the request-id ContextVar to
        ``cron-<uuid12>`` for the lifetime of the job and emits
        ``extra={"job_id": ...}`` on start / end / error log lines.
        Per-user failures are caught and logged but NOT re-raised —
        partial progress beats aborting the whole batch.
        """
        job_id = f"digest-{user_id}-{for_date.isoformat()}"
        rid = f"cron-{uuid.uuid4().hex[:12]}"
        token = _request_id_var.set(rid)
        logger.info("digest job start", extra={"job_id": job_id})
        try:
            async with AsyncSessionLocal() as session:
                row = await generate_digest(session, user_id, for_date)
            logger.info(
                "digest job end",
                extra={
                    "job_id": job_id,
                    "digest_id": str(row.id),
                    "delivery_status": row.delivery_status,
                },
            )
            return row
        except Exception:  # noqa: BLE001 — per-user failure isolation
            logger.exception(
                "digest job failed",
                extra={"job_id": job_id},
            )
            # Re-raise intentionally avoided — see _daily_tick note.
            return None
        finally:
            _request_id_var.reset(token)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def user_local_eight_am(tz_name: str | None, for_date: date) -> datetime:
    """Return the datetime for 08:00 user-local on ``for_date``.

    Used only by the future per-user scheduling path (ADR-012 §12.3
    describes per-user cron evaluation). Safe to call with a junk tz
    name — falls back to UTC and emits a warning.
    """
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(tz_name) if tz_name else _DEFAULT_TZ
    except Exception as e:  # noqa: BLE001 — defensive
        logger.warning(
            "user_local_eight_am: invalid tz %r, defaulting to UTC: %s",
            tz_name,
            e,
        )
        tz = _DEFAULT_TZ
    return datetime.combine(for_date, time(hour=8), tzinfo=tz).astimezone(timezone.utc)
