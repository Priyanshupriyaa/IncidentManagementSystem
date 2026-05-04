"""
main.py — UPDATED

What changed vs previous version:
  - Imported and started timescale_writer_loop() as a background task at startup.
    That's the only change — one import + one create_task line.
"""

import asyncio
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import incidents, ingestion
from app.api.ingestion import limiter
from app.core.observability import metrics
from app.db.session import init_db
from app.workers.signal_processor import process_signals_from_queue
from app.workers.timescale_writer import timescale_writer_loop  # NEW

app = FastAPI(title="Mission-Critical IMS")

# ── Rate limiter ──────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(ingestion.router, prefix="/api/v1", tags=["Ingestion"])
app.include_router(incidents.router, prefix="/api/v1/incidents", tags=["Workflows"])


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    await init_db()
    asyncio.create_task(metrics.log_metrics_loop())
    asyncio.create_task(process_signals_from_queue())
    asyncio.create_task(timescale_writer_loop())                # NEW
    print("✅ IMS Engine, Rate Limiter, TimescaleDB Writer & Workers started.")


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    from app.workers.signal_processor import signal_queue
    return {
        "status": "alive",
        "timestamp": time.time(),
        "queue_depth": signal_queue.qsize(),
        "throughput_signals_per_sec": round(metrics.signal_count / 5, 2),
    }