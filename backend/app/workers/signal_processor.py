"""
signal_processor.py  —  CHANGED (was a stub that just slept every 10s)

What changed & why:
  - Added a module-level asyncio.Queue (signal_queue) — this is the backpressure
    buffer. The /ingest endpoint pushes onto this queue instead of spawning
    unbounded background tasks. If Postgres/MongoDB are slow, signals pile up
    in RAM (bounded by QUEUE_MAX_SIZE) instead of crashing the server.
  - process_signals_from_queue() is the single consumer: it drains the queue
    one item at a time, persisting to MongoDB + Postgres with tenacity retries.
  - push_to_queue() is the public API called from ingestion.py.
"""

import asyncio
import uuid
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import mongo_db, async_session
from app.models.incidents import WorkItem
from app.core.observability import metrics

# ── Backpressure buffer ───────────────────────────────────────────────────────
# 50 000-slot bound: at 10 000 signals/sec this gives ~5 s of headroom before
# we start rejecting at the HTTP layer (503) rather than crashing.
QUEUE_MAX_SIZE = 50_000
signal_queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)


async def push_to_queue(payload: dict) -> bool:
    """
    Non-blocking enqueue.  Returns False (backpressure signal) if the queue
    is full so the HTTP layer can return 503 instead of blocking forever.
    """
    try:
        signal_queue.put_nowait(payload)
        return True
    except asyncio.QueueFull:
        return False


# ── Retry-decorated DB writers ────────────────────────────────────────────────

@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=0.2, max=2),
    reraise=True,
)
async def _persist_to_mongo(payload: dict):
    """Write raw signal to MongoDB data-lake with up to 3 retries."""
    await mongo_db.signals.insert_one(payload)


@retry(
    retry=retry_if_exception_type(SQLAlchemyError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=0.2, max=2),
    reraise=True,
)
async def _persist_work_item(component_id: str, severity: str):
    """Create a WorkItem in Postgres (source of truth) with up to 3 retries."""
    async with async_session() as session:
        new_item = WorkItem(
            id=str(uuid.uuid4()),
            component_id=component_id,
            severity=severity,
            status="OPEN",
        )
        session.add(new_item)
        await session.commit()


# ── Consumer coroutine (runs as a background task) ────────────────────────────

async def process_signals_from_queue():
    """
    Infinite consumer loop.  Started once at app startup via asyncio.create_task().
    Drains signal_queue and persists each item to MongoDB + conditionally Postgres.
    """
    print("👷 Worker started: draining signal queue...")
    while True:
        item = await signal_queue.get()          # blocks until something arrives
        try:
            # 1. Always persist raw signal to MongoDB data-lake
            payload_copy = {k: v for k, v in item.items() if k != "_create_work_item"}
            await _persist_to_mongo(payload_copy)

            # 2. If debouncing logic flagged this as a new incident, create WorkItem
            if item.get("_create_work_item"):
                await _persist_work_item(item["component_id"], item["severity"])

            metrics.increment_processed()

        except Exception as exc:
            print(f"[WORKER ERROR] Failed to persist signal after retries: {exc}")
        finally:
            signal_queue.task_done()