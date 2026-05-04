"""
strategies.py  —  CHANGED

What changed & why:
  - Added P1Alert for completeness (ingestion.py now handles P0/P1/P2).
  - No structural changes — Strategy Pattern was already correct.
"""

from abc import ABC, abstractmethod


class AlertingStrategy(ABC):
    @abstractmethod
    def alert(self, component_id: str):
        pass


class P0RDBMSAlert(AlertingStrategy):
    """Critical — RDBMS / primary data store failure."""
    def alert(self, component_id: str):
        print(f"🔴 [P0 CRITICAL] RDBMS failure at {component_id} — page on-call immediately!")


class P1Alert(AlertingStrategy):
    """High — MCP Host / async queue failure."""
    def alert(self, component_id: str):
        print(f"🟠 [P1 HIGH] Service failure at {component_id} — notify engineering lead.")


class P2CacheAlert(AlertingStrategy):
    """Medium — Distributed cache latency spike."""
    def alert(self, component_id: str):
        print(f"🟡 [P2 MEDIUM] Cache degradation at {component_id} — monitor closely.")