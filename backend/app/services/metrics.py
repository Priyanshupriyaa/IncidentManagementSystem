import asyncio
import logging

async def log_throughput(app_state):
    while True:
        await asyncio.sleep(5)
        # Calculate signals per second
        count = app_state["signal_count"]
        print(f"[METRIC] Current Throughput: {count / 5} signals/sec")
        app_state["signal_count"] = 0 # Reset window