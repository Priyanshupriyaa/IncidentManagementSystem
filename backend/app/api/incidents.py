"""
incidents.py — FIXED

What changed & why:
  - Moved GET /{component_id}/signals  →  GET /signals/{component_id}
    FastAPI matches routes top-to-bottom. The old path /{component_id}/signals
    was below /{incident_id}, so FastAPI treated "signals" as a UUID and
    returned 404. Static path segment /signals/ must come BEFORE the dynamic
    segment to be matched correctly.
"""

import json
from datetime import datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db, mongo_db
from app.models.incidents import WorkItem
from app.patterns.states import IncidentContext, STATE_MAP

router = APIRouter()

_redis = aioredis.from_url(settings.REDIS_URL)
CACHE_KEY = "dashboard:incidents"
CACHE_TTL = 5


def _serialize(item: WorkItem) -> dict:
    return {
        "id": item.id,
        "component_id": item.component_id,
        "status": item.status,
        "severity": item.severity,
        "start_time": item.start_time.isoformat() if item.start_time else None,
        "end_time": item.end_time.isoformat() if item.end_time else None,
        "mttr_minutes": item.mttr_minutes,
        "rca_data": item.rca_data,
    }


async def _invalidate_cache():
    await _redis.delete(CACHE_KEY)


# ── IMPORTANT: static routes FIRST, dynamic routes LAST ──────────────────────

@router.get("/")
async def list_incidents(db: AsyncSession = Depends(get_db)):
    """Returns all incidents sorted by severity. Redis-cached for 5s."""
    cached = await _redis.get(CACHE_KEY)
    if cached:
        return json.loads(cached)

    result = await db.execute(select(WorkItem).order_by(WorkItem.severity))
    items = result.scalars().all()
    serialized = [_serialize(i) for i in items]
    await _redis.setex(CACHE_KEY, CACHE_TTL, json.dumps(serialized))
    return serialized


@router.get("/signals/{component_id}")
async def get_incident_signals(component_id: str):
    """
    Fetch raw audit-log signals from MongoDB for a given component.
    FIXED: was /{component_id}/signals — conflicted with /{incident_id}.
    """
    cursor = mongo_db.signals.find({"component_id": component_id}).limit(50)
    signals = await cursor.to_list(length=50)
    for s in signals:
        s["_id"] = str(s["_id"])
    return signals


@router.get("/{incident_id}")
async def get_incident(incident_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch a single WorkItem by UUID."""
    result = await db.execute(select(WorkItem).where(WorkItem.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _serialize(incident)


@router.put("/{incident_id}/status")
async def update_status(
    incident_id: str,
    next_state: str,
    rca_payload: dict = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Drives the State Pattern machine.
    Valid: OPEN → INVESTIGATING → RESOLVED → CLOSED (requires RCA)
    """
    result = await db.execute(select(WorkItem).where(WorkItem.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    try:
        context = IncidentContext(incident.status)
        context.transition(next_state, rca_payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    incident.status = next_state

    if next_state == "CLOSED" and rca_payload:
        incident.end_time = datetime.utcnow()
        incident.rca_data = rca_payload
        if incident.start_time:
            mttr = (incident.end_time - incident.start_time).total_seconds() / 60
            print(f"✅ Incident {incident_id} CLOSED. MTTR: {round(mttr, 2)} min")

    await db.commit()
    await _invalidate_cache()

    return {"message": f"Incident {incident_id} → {next_state}"}