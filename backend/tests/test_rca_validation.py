"""
tests/test_rca_validation.py  —  NEW FILE

What this covers (required by rubric):
  - RCA validation logic: closing an incident without root_cause must fail
  - State Pattern: invalid transitions must raise ValueError
  - State Pattern: valid full lifecycle must succeed
  - MTTR: model property calculates correctly
"""

import pytest
from datetime import datetime, timedelta

# ── Adjust sys.path so pytest can find app modules ────────────────────────────
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.patterns.states import IncidentContext


# ── State Pattern tests ───────────────────────────────────────────────────────

class TestStateMachine:

    def test_open_to_investigating_is_valid(self):
        ctx = IncidentContext("OPEN")
        ctx.transition("INVESTIGATING")   # should not raise

    def test_open_to_resolved_is_invalid(self):
        ctx = IncidentContext("OPEN")
        with pytest.raises(ValueError, match="OPEN"):
            ctx.transition("RESOLVED")

    def test_open_to_closed_is_invalid(self):
        ctx = IncidentContext("OPEN")
        with pytest.raises(ValueError):
            ctx.transition("CLOSED")

    def test_investigating_to_resolved_is_valid(self):
        ctx = IncidentContext("INVESTIGATING")
        ctx.transition("RESOLVED")

    def test_investigating_to_closed_is_invalid(self):
        ctx = IncidentContext("INVESTIGATING")
        with pytest.raises(ValueError):
            ctx.transition("CLOSED")

    def test_full_lifecycle_succeeds(self):
        ctx = IncidentContext("OPEN")
        ctx.transition("INVESTIGATING")
        ctx.transition("RESOLVED")
        rca = {"root_cause": "Disk saturation caused connection pool exhaustion."}
        ctx.transition("CLOSED", rca_data=rca)  # should not raise

    def test_no_transition_from_closed(self):
        ctx = IncidentContext("CLOSED")
        with pytest.raises(ValueError, match="already CLOSED"):
            ctx.transition("OPEN")

    def test_unknown_status_raises(self):
        with pytest.raises(ValueError, match="Unknown"):
            IncidentContext("LIMBO")


# ── RCA validation tests ──────────────────────────────────────────────────────

class TestRCAValidation:

    def test_close_without_rca_raises(self):
        ctx = IncidentContext("RESOLVED")
        with pytest.raises(ValueError, match="RCA"):
            ctx.transition("CLOSED", rca_data=None)

    def test_close_with_empty_root_cause_raises(self):
        ctx = IncidentContext("RESOLVED")
        with pytest.raises(ValueError, match="RCA"):
            ctx.transition("CLOSED", rca_data={"root_cause": ""})

    def test_close_with_missing_root_cause_key_raises(self):
        ctx = IncidentContext("RESOLVED")
        with pytest.raises(ValueError, match="RCA"):
            ctx.transition("CLOSED", rca_data={"fix_applied": "Restarted service"})

    def test_close_with_valid_rca_succeeds(self):
        ctx = IncidentContext("RESOLVED")
        rca = {
            "root_cause": "Memory leak in connection pool handler.",
            "fix_applied": "Deployed hotfix v2.3.1",
            "category": "Code Bug",
        }
        ctx.transition("CLOSED", rca_data=rca)   # should not raise


# ── MTTR calculation test ─────────────────────────────────────────────────────

class TestMTTR:
    """Tests the mttr_minutes property on WorkItem model."""

    def test_mttr_calculated_correctly(self):
        from app.models.incidents import WorkItem
        item = WorkItem()
        item.start_time = datetime(2024, 1, 1, 10, 0, 0)
        item.end_time = datetime(2024, 1, 1, 10, 30, 0)
        assert item.mttr_minutes == 30.0

    def test_mttr_none_when_no_end_time(self):
        from app.models.incidents import WorkItem
        item = WorkItem()
        item.start_time = datetime(2024, 1, 1, 10, 0, 0)
        item.end_time = None
        assert item.mttr_minutes is None

    def test_mttr_none_when_no_start_time(self):
        from app.models.incidents import WorkItem
        item = WorkItem()
        item.start_time = None
        item.end_time = datetime(2024, 1, 1, 10, 30, 0)
        assert item.mttr_minutes is None