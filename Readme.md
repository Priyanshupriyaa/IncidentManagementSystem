# Mission-Critical Incident Management System (IMS)

A resilient, high-throughput system for monitoring distributed infrastructure failures and managing incident workflows end-to-end.

---

## Architecture Diagram

```
                          ┌─────────────────────────────────────────────┐
                          │              React Dashboard (3000)         │
                          │  Live Feed · Incident Detail · RCA Form     │
                          └──────────────────┬──────────────────────────┘
                                             │ REST (axios, 5s poll)
                          ┌──────────────────▼──────────────────────────┐
                          │         FastAPI Backend (8000)              │
                          │                                             │
                          │  POST /api/v1/ingest  ──►  Rate Limiter     │
                          │         │                   (slowapi 429)   │
                          │         ▼                                   │
                          │  asyncio.Queue (50k slots) ◄── backpressure │
                          │         │                                   │
                          │         ▼                                   │
                          │  Worker Coroutine                           │
                          │  ├─ MongoDB  (raw signals / data lake)      │
                          │  └─ Postgres (WorkItems / RCA / source of truth)
                          │                                              │
                          │  GET /api/v1/incidents/                      │
                          │  ├─ Redis cache (5s TTL) ── hit ──► return   │
                          │  └─ Postgres ── miss ──► cache + return      │
                          │                                              │
                          │  PUT /api/v1/incidents/:id/status            │
                          │  └─ IncidentContext (State Pattern)          │
                          │     OPEN→INVESTIGATING→RESOLVED→CLOSED       │
                          └──────────────────────────────────────────────┘
                                    │            │           │
                             ┌──────▼──┐   ┌────▼────┐  ┌──▼──────┐
                             │ Postgres│   │ MongoDB │  │  Redis  │
                             │ :5432   │   │ :27017  │  │  :6379  │
                             └─────────┘   └─────────┘  └─────────┘
                                    │
                             ┌──────▼──────┐
                             │ TimescaleDB │  ← timeseries aggregations
                             │ :5433       │
                             └─────────────┘
```

### Design Patterns
| Pattern | Where | Purpose |
|---|---|---|
| **Strategy** | `app/patterns/strategies.py` | Swap P0/P1/P2 alert logic without changing ingestion code |
| **State** | `app/patterns/states.py` + `IncidentContext` | Enforce OPEN→INVESTIGATING→RESOLVED→CLOSED transitions |

---

## Tech Stack

| Layer | Technology | Role |
|---|---|---|
| API | FastAPI + uvicorn | Async HTTP, auto-docs |
| Rate limiting | slowapi | Token bucket per IP, 429 on breach |
| Backpressure | asyncio.Queue (50k) | In-process buffer, prevents DB-lag crashes |
| Source of Truth | PostgreSQL 15 | Transactional WorkItems + RCA |
| Data Lake | MongoDB 6.0 | Raw signal audit log (schema-free) |
| Hot-path Cache | Redis 7 | Debounce keys + dashboard state (5s TTL) |
| Timeseries | TimescaleDB | Signal volume aggregations |
| Retry logic | tenacity | 3-attempt exponential backoff on DB writes |
| Frontend | React 18 | Live dashboard, RCA form |

---

## Setup Instructions

### Prerequisites
- Docker ≥ 24
- Docker Compose ≥ 2.20

### 1. Clone and start
```bash
git clone <your-repo-url>
cd ims
docker compose up --build
```

Services start in this order (health checks enforce it):
1. postgres + timescaledb + mongodb + redis
2. backend (waits for postgres healthy)
3. frontend

### 2. Verify
```bash
# Backend health
curl http://localhost:8000/health

# Auto-generated API docs
open http://localhost:8000/docs

# Dashboard
open http://localhost:3000
```

### 3. Send mock signals
```bash
# From repo root
pip install requests
python mock_signals.py
```

This simulates:
- RDBMS P0 burst (5 signals → 1 WorkItem due to debouncing)
- Cache P2 failure
- MCP Host failure after the 10s debounce window (creates a new WorkItem)

### 4. Run tests
```bash
cd backend
pip install pytest
pytest tests/ -v
```

---

## How Backpressure Was Handled

**The problem:** At 10,000 signals/second, naive `BackgroundTask` spawning creates unbounded in-flight coroutines. If Postgres takes 5ms per write, 50,000 tasks queue up in seconds → OOM crash.

**The solution — bounded `asyncio.Queue`:**

```
HTTP /ingest (< 1ms)
    └── signal_queue.put_nowait()   ← non-blocking, returns 503 if full
                ↓
    process_signals_from_queue()    ← single background consumer
        ├── _persist_to_mongo()     ← tenacity 3-retry, exp backoff
        └── _persist_work_item()    ← tenacity 3-retry, exp backoff
```

- **Bound:** 50,000 slots → ~5 seconds of DB outage tolerance at 10k sig/s
- **503 on full queue:** Caller gets a retryable error instead of silently dropped data
- **No race conditions:** Single consumer, no mutex needed on write path

---

## Observability

The backend prints throughput metrics every 5 seconds:
```
[METRIC] 14:32:05 | Ingested: 9843.2 sig/s | Persisted: 9841.7 sig/s
```

The `/health` endpoint exposes:
```json
{
  "status": "alive",
  "timestamp": 1714912345.123,
  "queue_depth": 42,
  "throughput_signals_per_sec": 9843.2
}
```

---

## Project Structure

```
ims/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── ingestion.py      # POST /ingest — rate limiter + queue push
│   │   │   └── incidents.py      # CRUD + state transitions + Redis cache
│   │   ├── core/
│   │   │   ├── config.py         # Settings from env
│   │   │   └── observability.py  # Throughput metrics loop
│   │   ├── db/
│   │   │   └── session.py        # Postgres + MongoDB + Redis clients
│   │   ├── models/
│   │   │   └── incidents.py      # SQLAlchemy WorkItem model
│   │   ├── patterns/
│   │   │   ├── states.py         # State Pattern + IncidentContext
│   │   │   └── strategies.py     # Strategy Pattern (alerting)
│   │   ├── schemas/
│   │   │   └── incident.py       # Pydantic schemas
│   │   ├── services/
│   │   │   └── metrics.py        # (legacy, superseded by observability.py)
│   │   ├── workers/
│   │   │   └── signal_processor.py  # asyncio.Queue consumer + retry writes
│   │   └── main.py               # App factory, middleware, startup
│   ├── scripts/
│   │   └── mock_outage.py
│   ├── tests/
│   │   └── test_rca_validation.py
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.js                # Dashboard + RCA form
│       └── App.css
├── docker-compose.yml
├── mock_signals.py
├── PLANNING.md
└── README.md
```
