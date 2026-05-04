import httpx
import asyncio
import uuid

async def simulate_outage():
    async with httpx.AsyncClient() as client:
        # Simulate an RDBMS outage (P0) 
        print("Simulating RDBMS Outage...")
        for _ in range(10):
            payload = {
                "signal_id": str(uuid.uuid4()),
                "component_id": "RDBMS_PRIMARY_01",
                "msg": "Connection Timeout",
                "severity": "P0"
            }
            await client.post("http://localhost:8000/ingest", json=payload)
        
        # Simulate a Cache failure (P2)
        print("Simulating Cache Latency Spike...")
        await client.post("http://localhost:8000/ingest", json={
            "signal_id": str(uuid.uuid4()),
            "component_id": "CACHE_CLUSTER_01",
            "msg": "Latency > 500ms",
            "severity": "P2"
        })

if __name__ == "__main__":
    asyncio.run(simulate_outage())