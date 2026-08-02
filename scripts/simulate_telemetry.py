import asyncio
import json
import os
import time

import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


async def inject_fault_stream():
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    route_key = "route:GTBank:Moniepoint:Mastercard"
    print(f" Injecting burst failures into {route_key}...")

    now = time.time()

    for i in range(10):
        payload = json.dumps(
            {
                "timestamp": now + i,
                "latency_ms": 4500.0,
                "is_hard_error": True,
                "is_ghost_debit": True if i < 3 else False,
            }
        )
        await redis.zadd(route_key, {payload: now + i})

    print(" Fault injection complete. Evaluator should flag CRITICAL on next tick.")
    await redis.aclose()


if __name__ == "__main__":
    asyncio.run(inject_fault_stream())
