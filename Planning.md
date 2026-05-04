# PLANNING.md — Prompts, Spec, and Architecture Decisions
---

## 1. Initial Architecture Plan

The assignment was decomposed into these sub-problems before writing any code:

| Problem | Decision |
|---|---|
| High-throughput ingestion without DB bottleneck | `asyncio.Queue` as in-process buffer (backpressure) |
| One WorkItem per burst, not one per signal | Redis `SET NX EX` (debounce key per component) |
| Swappable alerting logic per severity | Strategy Pattern (ABC + P0/P1/P2 concrete classes) |
| State enforcement for incident lifecycle | State Pattern (IncidentContext + per-state handlers) |
| Raw signal audit log | MongoDB (schema-free, write-heavy) |
| Transactional work items + RCA | PostgreSQL (ACID, structured) |
| Real-time dashboard without hammering Postgres | Redis key (`dashboard:incidents`, 5s TTL) |
| Timeseries aggregations | TimescaleDB (Postgres extension, native time-bucketing) |

---

## 2. How Backpressure Was Handled

**The problem:** At 10,000 signals/second, if the Postgres or MongoDB write takes even 5ms, unbounded `BackgroundTask` spawning will queue up thousands of coroutines, exhaust memory, and crash the server.

**The solution — asyncio.Queue:**

```
HTTP /ingest  →  signal_queue.put_nowait()  →  returns 200 immediately
                        ↓
              process_signals_from_queue()   ← single consumer coroutine
                        ↓
              _persist_to_mongo()            ← tenacity retry (3 attempts)
                        ↓  (if new incident)
              _persist_work_item()           ← tenacity retry (3 attempts)
```

- **Queue bound:** 50,000 slots. At 10k signals/sec, this gives ~5 seconds of DB outage tolerance before the HTTP layer starts returning 503.
- **503 on full queue:** Instead of blocking the event loop, `put_nowait()` raises `QueueFull` which is caught and returned as HTTP 503, letting upstream callers retry.
- **Single consumer:** One `asyncio.create_task()` at startup drains the queue sequentially. No race conditions on the write path.

---

## 3. Design Pattern Justifications

### Strategy Pattern (alerting)
Different components need different alert escalation paths. Using an `AlertingStrategy` ABC lets us swap P0 (wake on-call) vs P2 (monitor) without touching the ingestion logic. New component types → new subclass, no existing code changes (Open/Closed Principle).

### State Pattern (incident lifecycle)
The `IncidentContext` wraps the current state object and delegates every transition. Invalid moves (e.g. `OPEN → CLOSED`) raise `ValueError` at the state layer — the API endpoint doesn't need to know the business rules. Adding a new state (e.g. `ESCALATED`) → new class + one line in `STATE_MAP`.

---

## 4. Data Separation Rationale

| Store | Data | Why |
|---|---|---|
| MongoDB | Raw signal payloads | Schema-free, write-optimised, can store arbitrary `metadata` fields |
| PostgreSQL | WorkItems, RCA records | ACID transactions required; JOIN with future team/user tables |
| Redis | Debounce keys, dashboard cache | Sub-millisecond reads; ephemeral (loss is acceptable) |
| TimescaleDB | Signal volume timeseries | Native `time_bucket()` aggregation; compresses historical data automatically |

---

## 5. Rate Limiting Strategy

`slowapi` wraps the `/ingest` endpoint with a token-bucket limiter keyed on client IP. The limit is configurable via `RATE_LIMIT_PER_SECOND` in `config.py` (default 10,000/s). Exceeded requests get HTTP 429 with a `Retry-After` header.

This is a first line of defence. In production, an API Gateway (Kong/AWS API GW) would enforce limits upstream before traffic hits the application.

---

## 6. Prompts Used During Development

**Prompt 1 (architecture):**
> "Design a resilient incident management backend in Python. It must handle 10,000 signals/sec, debounce duplicate component signals, store raw logs in MongoDB, transactional work items in Postgres, and use asyncio without crashing when the DB is slow."

**Prompt 2 (patterns):**
> "Implement the Strategy Pattern for alerting (P0/P1/P2) and the State Pattern for OPEN→INVESTIGATING→RESOLVED→CLOSED in Python. The state machine must enforce transitions and reject CLOSED without an RCA object."

**Prompt 3 (backpressure):**
> "Show me how to use asyncio.Queue as a backpressure buffer in a FastAPI app. The HTTP handler should be non-blocking. The consumer should use tenacity for retries."

**Prompt 4 (frontend):**
> "Build a React dashboard that polls /api/v1/incidents/ every 5s, shows severity-coloured cards for all statuses, has status-aware action buttons (different CTA per state), and a modal RCA form with datetime pickers, category dropdown, and textareas."