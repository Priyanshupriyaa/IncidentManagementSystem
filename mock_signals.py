import requests
import time
import json

BASE_URL = "http://localhost:8000/api/v1/ingest"

def send_signal(component, msg, severity):
    payload = {
        "component_id": component,
        "msg": msg,
        "severity": severity
    }
    try:
        response = requests.post(BASE_URL, json=payload)
        print(f"Sent: {component} | Status: {response.status_code} | Debounced: {response.json().get('debounced')}")
    except Exception as e:
        print(f"Error sending signal: {e}")

if __name__ == "__main__":
    print("🚀 Starting Mock Failure Simulation...")

    # Scenario 1: RDBMS Outage (P0 Burst) 
    # In 5 signals mein se sirf 1 Work Item banna chahiye due to 10s debouncing [cite: 13, 14]
    print("\n--- Simulating RDBMS Outage (P0) ---")
    for i in range(5):
        send_signal("DATABASE_PROD", "Connection Timeout: Pool Exhausted", "P0")
        time.sleep(0.5) # Fast burst

    # Scenario 2: Cache Failure (P2 Series) [cite: 23]
    print("\n--- Simulating Cache Cluster Failure (P2) ---")
    send_signal("REDIS_CACHE_01", "Key eviction rate high", "P2")

    # Scenario 3: MCP Host Failure (After 11 seconds) 
    # 10s ke window ke baad naya signal naya incident banayega [cite: 13]
    print("\nWaiting 11 seconds to bypass debouncing window...")
    time.sleep(11)
    print("--- Simulating MCP Host Failure (New Incident) ---")
    send_signal("MCP_HOST_PATNA", "Heartbeat Lost", "P1")

    print("\n✅ Simulation Complete. Check your Dashboard!")