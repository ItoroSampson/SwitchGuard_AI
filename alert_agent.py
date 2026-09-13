import logging
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()
from langfuse.decorators import langfuse_context, observe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

SYSTEM_PROMPT = """You are SwitchGuard AI, an expert payment routing assistant for POS merchants in Nigeria.
Your job is to convert technical payment route error logs into extremely clear, concise, and urgent plain-English alerts for merchants on Telegram.

Domain Knowledge:
- A "Ghost Debit" means a customer's account gets debited by their bank while the POS terminal displays a failed/declined receipt or times out even when the channel stability service says the banks' network is healthy.
- NEVER say "customers might be charged incorrectly" or "overcharged".
- Describe ghost debits clearly as: "customers may be debited on failed or timed-out transactions, leading to disputes."

Rules:
1. Start with an attention-grabbing emoji header (e.g., ⚠️, 🚨, 🔴).
2. Clearly state the issue and explicitly name affected CARD TYPES vs safe ones based on the telemetry data.
3. Keep technical details simple (explain latency and ghost debits accurately).
4. CRITICAL: In the Recommended Action, NEVER call out specific alternative bank names. Keep it generic (e.g., "Switch default terminal route to an alternative bank switch immediately").
5. Keep the response under 90 words. Direct, professional, and punchy.
"""


@observe(name="generate_telegram_alert")
def generate_telegram_alert(telemetry: dict) -> str:
    """
    Generates merchant-friendly alerts via local Ollama while tracing
    execution time, token counts, and fallbacks in Langfuse.
    """
    start_time = time.time()

    incident_id = telemetry.get("incident_id", "INC-UNKNOWN")
    bank = telemetry.get("bank", "Unknown Bank")
    pos_provider = telemetry.get("pos_provider", "Unknown Switch")
    route_id = f"{bank} ➔ {pos_provider}"

    langfuse_context.update_current_trace(
        name=f"Alert Gen: {route_id}",
        session_id=incident_id,
        tags=["switchguard-ai", "alert-agent", OLLAMA_MODEL],
        metadata={
            "route_id": route_id,
            "anomaly_type": telemetry.get("anomaly_type"),
            "failure_rate": telemetry.get("failure_rate"),
            "ghost_count": telemetry.get("ghost_count", 0),
        },
    )

    affected_cards = ", ".join(telemetry.get("affected_cards", ["All Cards"]))
    unaffected_cards = ", ".join(telemetry.get("unaffected_cards", ["None"]))

    prompt = f"""
[INCIDENT TELEMETRY DATA]
Incident ID: {incident_id}
Bank/Route: {route_id}
Anomaly Type: {telemetry.get("anomaly_type")}
Affected Card Types: {affected_cards}
Safe Card Types: {unaffected_cards}
Failure Rate: {telemetry.get("failure_rate", 0.0) * 100:.1f}%
Ghost Debits Detected: {telemetry.get("ghost_count", 0)}
5-Min Volume: {telemetry.get("volume_5m", 0)}
Average Latency: {telemetry.get("avg_latency_ms", 0)} ms

Generate the Telegram alert message following system rules.
"""

    payload = {
        "model": OLLAMA_MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 180},
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(OLLAMA_URL, json=payload)
            response.raise_for_status()
            res_json = response.json()

            raw_response = res_json.get("response", "").strip()
            eval_duration_sec = time.time() - start_time

            prompt_tokens = res_json.get("prompt_eval_count", 0)
            completion_tokens = res_json.get("eval_count", 0)

            langfuse_context.update_current_observation(
                input={"system_prompt": SYSTEM_PROMPT, "telemetry_prompt": prompt},
                output=raw_response,
                model=OLLAMA_MODEL,
                usage={
                    "input": prompt_tokens,
                    "output": completion_tokens,
                    "total": prompt_tokens + completion_tokens,
                },
                metadata={
                    "total_duration_sec": eval_duration_sec,
                    "ollama_eval_duration_ms": res_json.get("eval_duration", 0) / 1e6,
                },
            )

            return raw_response

    except Exception as e:
        logger.error(f"Ollama connection or execution error: {e}")

        fallback_msg = (
            f"🚨 **ALERT: {bank} Route Issue**\n\n"
            f"💳 **Affected Cards:** {affected_cards}\n"
            f"⚠️ **Anomaly:** {telemetry.get('anomaly_type', 'ROUTE_DEGRADATION')}\n"
            f"💡 **Action:** Switch default terminal route to an alternative bank switch immediately to prevent ghost debit disputes."
        )

        langfuse_context.update_current_observation(
            level="ERROR", status_message=str(e), output=fallback_msg
        )

        return fallback_msg


if __name__ == "__main__":
    sample_incident = {
        "incident_id": "INC-8821",
        "bank": "First Bank",
        "pos_provider": "Moniepoint",
        "anomaly_type": "GHOST_DEBIT_RISK",
        "affected_cards": ["Verve", "Mastercard"],
        "unaffected_cards": ["Visa"],
        "failure_rate": 0.42,
        "ghost_count": 3,
        "volume_5m": 120,
        "avg_latency_ms": 8450,
    }

    print("--- Testing  Alert Agent ---")
    print(generate_telegram_alert(sample_incident))
