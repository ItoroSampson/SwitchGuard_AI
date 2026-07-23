import json
import logging

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:3b"

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


def generate_telegram_alert(telemetry_payload: dict) -> str:
    """Converts technical telemetry into a concise Telegram alert via local Mistral."""

    prompt = f"System Telemetry Data:\n{json.dumps(telemetry_payload, indent=2)}\n\nGenerate the Telegram message:"

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "system": SYSTEM_PROMPT,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 180},
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()

    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama connection error: {e}")

        cards = ", ".join(telemetry_payload.get("affected_cards", ["All Cards"]))
        return (
            f"🚨 **ALERT: {telemetry_payload.get('bank', 'Issuer')} Route Issue**\n\n"
            f"💳 **Affected Cards:** {cards}\n"
            f"⚠️ **Anomaly:** {telemetry_payload.get('anomaly_type')}\n"
            f"💡 **Action:** Switch default terminal route to an alternative bank switch immediately to prevent ghost debit disputes."
        )


if __name__ == "__main__":
    sample_incident = {
        "incident_id": "INC-8821",
        "bank": "First Bank",
        "anomaly_type": "GHOST_DEBIT_RISK",
        "affected_cards": ["Verve", "Mastercard"],
        "unaffected_cards": ["Visa"],
        "failure_rate": 0.42,
        "avg_latency_ms": 8450,
        "recommended_action": "Switch default terminal route to alternative bank channels immediately.",
    }

    print("--- Generating Alert via Ollama ---")
    alert_text = generate_telegram_alert(sample_incident)
    print(alert_text)
