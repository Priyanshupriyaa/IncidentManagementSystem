"""
observability.py  —  CHANGED

What changed & why:
  - Added increment_processed() and processed_count so the metrics loop
    can report both ingested signals/sec AND successfully persisted signals/sec.
    This gives a clear view of queue lag under load.
"""

import asyncio
import time


class MetricsManager:
    def __init__(self):
        self.signal_count = 0        # signals received at HTTP layer
        self.processed_count = 0     # signals successfully persisted by worker
        self.start_time = time.time()

    def increment_signal(self):
        self.signal_count += 1

    def increment_processed(self):
        self.processed_count += 1

    async def log_metrics_loop(self):
        """Prints throughput every 5 seconds as required by the spec."""
        while True:
            await asyncio.sleep(5)
            ingested = self.signal_count
            persisted = self.processed_count
            print(
                f"[METRIC] {time.strftime('%H:%M:%S')} | "
                f"Ingested: {ingested / 5:.1f} sig/s | "
                f"Persisted: {persisted / 5:.1f} sig/s"
            )
            self.signal_count = 0
            self.processed_count = 0


metrics = MetricsManager()