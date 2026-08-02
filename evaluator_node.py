import asyncio
import json
import os
import time

import httpx
import redis.asyncio as aioredis
from alert_agent import generate_telegram_alert
from app.evaluator import AnomalyEvaluator

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
EVALUATION_INTERVAL = 15
WINDOW_SECONDS = 300

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


async def send_telegram_alert(message: str):
    """Dispatches message to Telegram chat if credentials are set."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ℹ Telegram credentials not set. Skipping push notification.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json=payload)
    except Exception as e:
        print(f" Failed to send Telegram alert: {e}")


async def run_anomaly_detection_loop():
    redis_client = aioredis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, decode_responses=True
    )
    evaluator = AnomalyEvaluator()
    print(" Anomaly Detection Node active (6-Feature XGBoost + Telegram Agent)...")

    try:
        while True:
            now = time.time()
            window_start = now - WINDOW_SECONDS

            route_keys = await redis_client.keys("route:*:*:*")
            active_route_keys = [
                k
                for k in route_keys
                if not k.endswith(":status") and not k.endswith(":alert_state")
            ]

            if active_route_keys:
                for route_key in active_route_keys:
                    parts = route_key.split(":")
                    if len(parts) != 4:
                        continue

                    issuing_bank, pos_provider, card_type = parts[1], parts[2], parts[3]
                    route_id = f"{issuing_bank} ➔ {pos_provider} ({card_type})"

                    async with redis_client.pipeline(transaction=True) as pipe:
                        pipe.zremrangebyscore(route_key, "-inf", window_start)
                        pipe.zrangebyscore(route_key, window_start, "+inf")
                        results = await pipe.execute()

                    window_members: list[str] = results[1]
                    total_vol = len(window_members)
                    if total_vol == 0:
                        continue

                    hard_errors = 0
                    ghost_count = 0
                    latencies = []
                    current_strike = 0
                    max_strike = 0

                    for item in window_members:
                        try:
                            if item.startswith("{"):
                                data = json.loads(item)
                                is_hard = data.get("is_hard_error", False)
                                is_ghost = data.get("is_ghost_debit", False)
                                lat = float(data.get("latency_ms", 0.0))
                            else:
                                item_parts = item.split(":")
                                is_hard = (
                                    item_parts[1] == "1"
                                    if len(item_parts) > 1
                                    else False
                                )
                                is_ghost = (
                                    item_parts[2] == "1"
                                    if len(item_parts) > 2
                                    else False
                                )
                                lat = 0.0

                            latencies.append(lat)

                            if is_ghost:
                                ghost_count += 1

                            if is_hard:
                                hard_errors += 1
                                current_strike += 1
                                max_strike = max(max_strike, current_strike)
                            else:
                                current_strike = 0
                        except Exception:
                            continue

                    fail_rate = (
                        round(hard_errors / total_vol, 4) if total_vol > 0 else 0.0
                    )
                    avg_latency = (
                        round(sum(latencies) / total_vol, 2) if total_vol > 0 else 0.0
                    )

                    features = {
                        "volume_5m": total_vol,
                        "time_decayed_fail_rate": fail_rate,
                        "avg_latency_ms": avg_latency,
                        "hard_technical_errors": hard_errors,
                        "max_consecutive_strikes": max_strike,
                        "ghost_debit_count": ghost_count,
                    }

                    current_status, score, reason = evaluator.evaluate_route_health(
                        features
                    )

                    status_key = f"{route_key}:status"
                    await redis_client.hset(
                        status_key,
                        mapping={
                            "status": current_status,
                            "anomaly_score": str(score),
                            "reason": reason,
                            "volume_5m": str(total_vol),
                            "fail_rate_pct": str(round(fail_rate * 100, 2)),
                            "ghost_count": str(ghost_count),
                            "max_strikes": str(max_strike),
                            "avg_latency_ms": str(avg_latency),
                            "last_evaluated": str(now),
                        },
                    )

                    alert_key = f"{route_key}:alert_state"
                    previous_alert_status = await redis_client.get(alert_key)

                    if (
                        current_status in ["DEGRADED", "CRITICAL"]
                        and previous_alert_status != current_status
                    ):
                        telemetry_payload = {
                            "incident_id": f"INC-{int(now)}",
                            "bank": issuing_bank,
                            "pos_provider": pos_provider,
                            "anomaly_type": "GHOST_DEBIT_RISK"
                            if ghost_count > 0
                            else "BURST_HARD_FAILURES",
                            "affected_cards": [card_type],
                            "unaffected_cards": [],
                            "failure_rate": fail_rate,
                            "ghost_count": ghost_count,
                            "volume_5m": total_vol,
                            "avg_latency_ms": avg_latency,
                            "max_consecutive_strikes": max_strike,
                        }

                        print(
                            f"\n Invoking alert_agent.py (Llama 3.2:3b) for {route_id}..."
                        )

                        alert_text = generate_telegram_alert(telemetry_payload)

                        print(
                            f"\n--- TELEGRAM ALERT DISPATCH ---\n{alert_text}\n-------------------------------\n"
                        )
                        await send_telegram_alert(alert_text)

                        await redis_client.set(alert_key, current_status, ex=900)

                    elif (
                        current_status == "HEALTHY"
                        and previous_alert_status is not None
                    ):
                        await redis_client.delete(alert_key)

                    status_icon = (
                        "🟢"
                        if current_status == "HEALTHY"
                        else ("🟡" if current_status == "DEGRADED" else "🔴")
                    )
                    print(
                        f"{status_icon} [{current_status:<8}] "
                        f"Route: {route_id:<38} | Vol: {total_vol:<3} | "
                        f"Fail: {fail_rate * 100:>5.1f}% | Strikes: {max_strike:<2} | Ghosts: {ghost_count:<2} | Lat: {avg_latency:>6.1f}ms"
                    )

            await asyncio.sleep(EVALUATION_INTERVAL)

    except asyncio.CancelledError:
        print("\nStopping Anomaly Detection Node...")
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(run_anomaly_detection_loop())
