from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

# 1. Incoming Signal Schema (Used in /ingest)
class SignalIn(BaseModel):
    component_id: str = Field(..., example="DATABASE_PROD_01")
    msg: str = Field(..., example="Connection timeout detected")
    severity: str = Field(..., pattern="^(P0|P1|P2)$") # Strict P0, P1, P2 only
    metadata: Optional[Dict[str, Any]] = None

# 2. RCA Payload Schema (Used for /status update to CLOSED)
class RCAPayload(BaseModel):
    start_time: datetime
    end_time: datetime
    root_cause: str = Field(..., min_length=10) # Enforces detail
    category: str = Field(..., example="Network/Hardware/Code")
    fix_applied: str

# 3. Response Schema (Optional: What the API sends back)
class WorkItemResponse(BaseModel):
    id: str
    component_id: str
    status: str
    severity: str
    mttr_minutes: Optional[float] = None

    class Config:
        from_attributes = True