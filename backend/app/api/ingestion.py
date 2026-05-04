"""
ingestion.py — UPDATED

What changed vs previous version:
  - Added record_signal(signal.component_id) call so the TimescaleDB
    accumulator counts every signal passing through /ingest.
    This is the only change — one import + one line.
"""

import redis.asyncio as redis
from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.observability import metrics
from app.schemas.incident import SignalIn
from app.patterns.strategies import P0RDBMSAlert, P1Alert, P2CacheAlert
from app.workers.signal_processor import push_to_queue
from app.workers.timescale_writer import record_signal          # NEW

router = APIRouter()

limiter = Limiter(key_func=get_remote_address)
_redis = redis.from_url(settings.REDIS_URL)


@router.post("/ingest")
@limiter.limit(f"{settings.RATE_LIMIT_PER_SECOND}/second")
async def ingest_signal(request: Request, signal: SignalIn):
    """
    Hot path — sub-millisecond regardless of DB speed.
    1. Increment throughput counter.
    2. Record signal for TimescaleDB accumulator (in-memory, O(1)).
    3. Debounce via Redis.
    4. Push to asyncio.Queue.
    5. Return immediately.
    """
    metrics.increment_signal()
    record_signal(signal.component_id)                          # NEW

    debounce_key = f"debounce:{signal.component_id}"
    is_new_incident = await _redis.set(
        debounce_key, "active", nx=True, ex=settings.SIGNAL_WINDOW_SECONDS
    )

    if is_new_incident:
        _get_alert_strategy(signal.severity).alert(signal.component_id)

    payload = signal.dict()
    payload["_create_work_item"] = bool(is_new_incident)

    accepted = await push_to_queue(payload)
    if not accepted:
        raise HTTPException(
            status_code=503,
            detail="Queue full — system under extreme load. Retry shortly.",
        )

    return {"status": "accepted", "debounced": not bool(is_new_incident)}


def _get_alert_strategy(severity: str):
    if severity == "P0":
        return P0RDBMSAlert()
    if severity == "P1":
        return P1Alert()
    return P2CacheAlert()