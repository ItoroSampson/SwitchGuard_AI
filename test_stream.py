import asyncio
import random
import time
from datetime import datetime, timezone

import httpx

TARGET_URL = "https://localhost:8443/api/v1/transactions/ingest"

BANKS = [
    "GTBank",
    "Access Bank",
    "Zenith Bank",
    "UBA",
    "Sterling Bank",
    "Stanbic Bank",
    "Wema Bank",
    "Polaris Bank",
    "First Bank",
]
PROVIDERS = ["Moniepoint", "Opay", "Palmpay"]
CARD_TYPES = ["Verve", "Mastercard", "Visa"]
ERROR_CODES = ["91", "96", "TO", "98", "PY", "06", "A3", "N5"]


async def simulate_transaction(client: httpx.AsyncClient, i: int):
    issuing_bank = random.choice(BANKS)
    pos_provider = random.choice(PROVIDERS)
    resp_code = random.choice(ERROR_CODES)
    is_ghost = random.choice([False, False, False, True])

    payload = {
        "id": f"TXN_{int(time.time())}_{i}",
        "terminal_id": f"TERM_{random.randint(1000, 9999)}",
        "pos_provider": pos_provider,
        "issuing_bank": issuing_bank,
        "card_type": random.choice(CARD_TYPES),
        "amount": round(random.uniform(500.0, 50000.0), 2),
        "response_code": resp_code,
        "off_status": "ONLINE" if random.random() > 0.3 else "OFFLINE",
        "ghost_debit": is_ghost,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    start_time = time.perf_counter()
    response = await client.post(TARGET_URL, json=payload)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    if response.status_code == 201:
        data = response.json()
        health = data["route_health"]
        print(
            f"[{i:02d}/30] ✅ HTTP {elapsed_ms:5.1f}ms | "
            f"Route: {issuing_bank:>11} ➔ {pos_provider:<10} | "
            f"Window 5m Vol: {health['total_volume']:<2} | "
            f"Fail Rate: {health['failure_rate_pct']:5.1f}% | "
            f"Degraded: {health['route_degraded']!s:<5}"
        )
    else:
        print(f"[{i:02d}/30]  FAILED {response.status_code}: {response.text}")


async def main():
    print("Starting Redis Rolling Window Stream Test...")
    print(f"Target: {TARGET_URL}\n" + "=" * 90)

    async with httpx.AsyncClient(verify=False) as client:
        for i in range(1, 31):
            await simulate_transaction(client, i)
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(main())
