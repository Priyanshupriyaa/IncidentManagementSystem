"""
states.py  —  CHANGED

What changed & why:
  - Added IncidentContext class.  Previously the states were defined but
    there was no context object to wire them together and nothing in the
    API ever called them.  IncidentContext is now instantiated in
    incidents.py update_status, making the State Pattern live.
  - Added STATE_MAP helper so we can reconstruct the right state object
    from the string stored in Postgres.
  - Added InvestigatingState → RESOLVED guard (was missing before).
"""

from abc import ABC, abstractmethod


# ── Abstract base ─────────────────────────────────────────────────────────────

class IncidentState(ABC):
    @abstractmethod
    def handle_transition(self, context: "IncidentContext", next_state: str, rca_data: dict = None):
        pass


# ── Concrete states ───────────────────────────────────────────────────────────

class OpenState(IncidentState):
    def handle_transition(self, context, next_state, rca_data=None):
        if next_state == "INVESTIGATING":
            context.set_state(InvestigatingState())
        else:
            raise ValueError(f"Invalid transition: OPEN → {next_state}. Only INVESTIGATING allowed.")


class InvestigatingState(IncidentState):
    def handle_transition(self, context, next_state, rca_data=None):
        if next_state == "RESOLVED":
            context.set_state(ResolvedState())
        else:
            raise ValueError(f"Invalid transition: INVESTIGATING → {next_state}. Only RESOLVED allowed.")


class ResolvedState(IncidentState):
    def handle_transition(self, context, next_state, rca_data=None):
        if next_state == "CLOSED":
            if not rca_data or not rca_data.get("root_cause"):
                raise ValueError("Cannot close incident: RCA with 'root_cause' is mandatory.")
            context.set_state(ClosedState())
        else:
            raise ValueError(f"Invalid transition: RESOLVED → {next_state}. Only CLOSED allowed.")


class ClosedState(IncidentState):
    def handle_transition(self, context, next_state, rca_data=None):
        raise ValueError("Incident is already CLOSED. No further transitions allowed.")


# ── State map (string from DB → State object) ─────────────────────────────────
STATE_MAP = {
    "OPEN": OpenState,
    "INVESTIGATING": InvestigatingState,
    "RESOLVED": ResolvedState,
    "CLOSED": ClosedState,
}


# ── Context (the object that drives the machine) ──────────────────────────────

class IncidentContext:
    """
    Wraps the current state and delegates transition calls.
    Usage:
        ctx = IncidentContext("OPEN")       # reconstruct from DB string
        ctx.transition("INVESTIGATING")     # raises ValueError on bad transition
    """

    def __init__(self, current_status: str):
        state_class = STATE_MAP.get(current_status)
        if state_class is None:
            raise ValueError(f"Unknown incident status: {current_status}")
        self._state: IncidentState = state_class()

    def set_state(self, state: IncidentState):
        self._state = state

    def transition(self, next_state: str, rca_data: dict = None):
        """Delegates to the current state.  Raises ValueError on invalid move."""
        self._state.handle_transition(self, next_state, rca_data)