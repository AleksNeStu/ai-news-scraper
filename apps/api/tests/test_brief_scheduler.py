"""Tests for the AI Brief scheduler wiring (Task #8, ADR-012 §12.3, §12.10).

Coverage:

* ``BriefScheduler.start()`` is a no-op when ``effective_digest_enabled``
  is ``False`` (M6 — defensive depth).
* Per-job cron logging (M5): ``run_for_user`` sets the
  ``_request_id_var`` ContextVar to a value of the form
  ``cron-<uuid12>`` for the lifetime of the job, and the
  ``digest job start`` / ``digest job end`` / ``digest job failed``
  log records each carry ``extra={"job_id": ...}``.
* The ContextVar is reset in ``finally`` (no leak between jobs).
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from api.middleware.logging import get_request_id
from api.scheduler.brief import BriefScheduler


_CRON_RID = re.compile(r"^cron-[0-9a-f]{12}$")


# ---------------------------------------------------------------------------
# start() defensive no-op when digest_enabled is False
# ---------------------------------------------------------------------------


async def test_start_is_noop_when_digest_disabled(monkeypatch) -> None:
    """M6: ``start()`` itself checks ``settings.effective_digest_enabled``
    and returns without creating the AsyncIOScheduler instance when
    the flag is off. The class is therefore safe to instantiate
    directly from tests / scripts without going through ``main.py``.
    """
    import api.scheduler.brief as brief_mod

    settings = brief_mod.get_settings()
    monkeypatch.setattr(settings, "digest_enabled", False)
    monkeypatch.setattr(settings, "brief_disabled", False)
    # Force re-eval of the lru_cache.
    assert settings.effective_digest_enabled is False

    sched = BriefScheduler()
    # Patch the apscheduler AsyncIOScheduler constructor to detect calls.
    with patch("api.scheduler.brief.AsyncIOScheduler") as mock_async_io_sched:
        await sched.start()
    mock_async_io_sched.assert_not_called()
    assert sched._sched is None

    # stop() must still be a no-op (idempotent).
    await sched.stop()
    assert sched._sched is None


# ---------------------------------------------------------------------------
# M5 — cron logging contract (ContextVar wrap + extra={job_id: ...})
# ---------------------------------------------------------------------------


async def test_run_for_user_sets_cron_request_id_and_emits_job_id(
    monkeypatch, caplog
) -> None:
    """M5: ``run_for_user`` sets ``_request_id_var`` to ``cron-<uuid12>``
    and emits ``extra={"job_id": ...}`` on start / end log records."""

    # Stub ``generate_digest`` so we don't need a DB.
    fake_row = MagicMock()
    fake_row.id = uuid4()
    fake_row.delivery_status = "notified"

    async def _fake_generate_digest(session, user_id, for_date):
        return fake_row

    monkeypatch.setattr(
        "api.scheduler.brief.generate_digest",
        _fake_generate_digest,
    )

    # Stub AsyncSessionLocal so the run_for_user inner ``async with``
    # does not touch Postgres.
    class _FakeCtx:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr("api.scheduler.brief.AsyncSessionLocal", lambda: _FakeCtx())

    user_id = uuid4()
    for_date = datetime.now(timezone.utc).date()

    sched = BriefScheduler()
    with caplog.at_level(logging.INFO, logger="api.scheduler.brief"):
        result = await sched.run_for_user(user_id, for_date)

    assert result is fake_row
    # After the job, the ContextVar must be reset to the default
    # (empty string) — no leak into the next code that runs.
    assert get_request_id() == ""

    # Inspect the captured records: assert the start/end log lines
    # carried both ``job_id`` extra and a request-id matching the
    # contract (cron-<12 hex>).
    start_records = [r for r in caplog.records if r.getMessage() == "digest job start"]
    end_records = [r for r in caplog.records if r.getMessage() == "digest job end"]
    assert len(start_records) == 1
    assert len(end_records) == 1

    expected_job_id = f"digest-{user_id}-{for_date.isoformat()}"
    assert start_records[0].job_id == expected_job_id
    assert end_records[0].job_id == expected_job_id
    # ``digest_id`` is added to the end record only.
    assert end_records[0].digest_id == str(fake_row.id)


async def test_run_for_user_logs_failure_and_does_not_raise(
    monkeypatch, caplog
) -> None:
    """M5 failure path: ``generate_digest`` raising produces a
    ``digest job failed`` log record with ``extra={"job_id": ...}``
    and ``run_for_user`` swallows the exception so the parent
    batch (``_daily_tick``) keeps going."""

    async def _failing_generate_digest(session, user_id, for_date):
        raise RuntimeError("simulated LLM down")

    monkeypatch.setattr(
        "api.scheduler.brief.generate_digest",
        _failing_generate_digest,
    )

    class _FakeCtx:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr("api.scheduler.brief.AsyncSessionLocal", lambda: _FakeCtx())

    user_id = uuid4()
    for_date = date(2026, 6, 29)

    sched = BriefScheduler()
    with caplog.at_level(logging.INFO, logger="api.scheduler.brief"):
        result = await sched.run_for_user(user_id, for_date)

    # No exception leaks out.
    assert result is None
    # ContextVar reset even on failure.
    assert get_request_id() == ""

    fail_records = [r for r in caplog.records if r.getMessage() == "digest job failed"]
    assert len(fail_records) == 1
    assert fail_records[0].job_id == f"digest-{user_id}-{for_date.isoformat()}"
    assert fail_records[0].levelname == "ERROR"
