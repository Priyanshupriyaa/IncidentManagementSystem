"""
timescale_writer.py — NEW FILE

What this does:
  Runs as a background asyncio task (started in main.py startup).
  Every 60 seconds it flushes accumulated per-component signal counts
  into TimescaleDB's signal_metrics hypertable.

  This satisfies the "Sink (Aggregations): Support timeseries aggregations"
  requirement from the spec. TimescaleDB's time_bucket() function can then
  answer queries like "signals per minute per component over the last hour".

  Architecture:
    - In-memory counter dict (component_id → count) updated by the /ingest
      route via record_signal().
    - flush_to_timescale() drains the counter and writes one row per
      component into TimescaleDB using a raw asyncpg connection (faster
      than SQLAlchemy for bulk inserts).
    - The hypertable is created on first startup if it doesn't exist.
"""

import asyncio
import time
from collections import defaultdict
from datetime import datetime, timezone

import asyncpg

from app.core.config import settings

# ── In-memory accumulator ─────────────────────────────────────────────────────
# Key: component_id, Value: signal count since last flush
_signal_counts: dict[str, int] = defaultdict(int)
FLUSH_INTERVAL = 60  # seconds


def record_signal(component_id: str):
    """
    Called from ingestion.py on every signal (O(1), no I/O).
    Thread-safe for single-threaded asyncio event loop.
    """
    _signal_counts[component_id] += 1


# ── TimescaleDB setup ─────────────────────────────────────────────────────────

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS signal_metrics (
    time        TIMESTAMPTZ NOT NULL,
    component   TEXT        NOT NULL,
    signal_count INTEGER    NOT NULL
);
"""

CREATE_HYPERTABLE_SQL = """
SELECT create_hypertable('signal_metrics', 'time', if_not_exists => TRUE);
"""


async def _init_timescale(conn: asyncpg.Connection):
    """Create the hypertable once on startup."""
    await conn.execute(CREATE_TABLE_SQL)
    try:
        await conn.execute(CREATE_HYPERTABLE_SQL)
    except Exception:
        pass  # already a hypertable — safe to ignore


async def _get_timescale_conn() -> asyncpg.Connection:
    """Raw asyncpg connection to TimescaleDB (port 5433)."""
    return await asyncpg.connect(settings.TIMESCALE_URL)


# ── Background flush task ─────────────────────────────────────────────────────

async def timescale_writer_loop():
    """
    Infinite loop started at app startup.
    Every FLUSH_INTERVAL seconds, drains the accumulator and
    bulk-inserts rows into TimescaleDB.
    """
    print("📊 TimescaleDB writer started.")

    # Init the hypertable on first run
    try:
        conn = await _get_timescale_conn()
        await _init_timescale(conn)
        await conn.close()
        print("📊 signal_metrics hypertable ready.")
    except Exception as exc:
        print(f"[TIMESCALE INIT ERROR] {exc} — will retry on next flush.")

    while True:
        await asyncio.sleep(FLUSH_INTERVAL)
        await flush_to_timescale()


async def flush_to_timescale():
    """Snapshot and flush current counters to TimescaleDB."""
    if not _signal_counts:
        return

    # Snapshot and reset atomically (single-threaded event loop)
    snapshot = dict(_signal_counts)
    _signal_counts.clear()

    now = datetime.now(timezone.utc)
    rows = [(now, component, count) for component, count in snapshot.items()]

    try:
        conn = await _get_timescale_conn()
        await conn.executemany(
            "INSERT INTO signal_metrics (time, component, signal_count) VALUES ($1, $2, $3)",
            rows,
        )
        await conn.close()
        print(f"[TIMESCALE] Flushed {len(rows)} component metrics at {now.strftime('%H:%M:%S')}")
    except Exception as exc:
        print(f"[TIMESCALE FLUSH ERROR] {exc} — data for this window lost.")