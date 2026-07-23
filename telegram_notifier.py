import asyncio
import logging
import os
from datetime import datetime, timedelta

from alert_agent import generate_telegram_alert
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


RECENT_ALERTS = {}
ALERT_COOLDOWN_MINUTES = 15


def is_duplicate_alert(dedupe_key: str) -> bool:
    """Checks if an alert for the same route issue was sent within the cooldown window."""
    now = datetime.now()
    if dedupe_key in RECENT_ALERTS:
        last_sent = RECENT_ALERTS[dedupe_key]
        if now - last_sent < timedelta(minutes=ALERT_COOLDOWN_MINUTES):
            return True
    return False


def record_alert_sent(dedupe_key: str):
    """Records the timestamp of the sent alert."""
    RECENT_ALERTS[dedupe_key] = datetime.now()


async def send_incident_alert(telemetry_payload: dict, chat_id: str = TELEGRAM_CHAT_ID):
    """Generates an LLM alert via alert_agent.py and pushes it to Telegram with rate-limiting."""

    if not TELEGRAM_BOT_TOKEN or not chat_id:
        logger.error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in environment.")
        return

    bank = telemetry_payload.get("bank", "UNKNOWN")
    anomaly = telemetry_payload.get("anomaly_type", "UNKNOWN")
    dedupe_key = f"{bank}:{anomaly}"

    if is_duplicate_alert(dedupe_key):
        logger.info(
            f"⏸[Suppressed] Duplicate alert for '{dedupe_key}' within {ALERT_COOLDOWN_MINUTES}m cooldown window."
        )
        return None

    logger.info(
        f"Generating LLM alert for incident {telemetry_payload.get('incident_id')} ({dedupe_key})..."
    )
    alert_text = generate_telegram_alert(telemetry_payload)

    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    try:
        logger.info(f"Sending Telegram alert to Chat ID: {chat_id}...")
        message = await bot.send_message(
            chat_id=chat_id, text=alert_text, parse_mode=ParseMode.MARKDOWN
        )

        record_alert_sent(dedupe_key)
        logger.info(f"Alert successfully sent! Message ID: {message.message_id}")
        return message

    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")

        try:
            msg = await bot.send_message(chat_id=chat_id, text=alert_text)
            record_alert_sent(dedupe_key)
            return msg
        except Exception as fallback_err:
            logger.error(f"Fallback plain text sending failed: {fallback_err}")


async def main():
    test_incident = {
        "incident_id": "INC-9904",
        "bank": "First Bank",
        "anomaly_type": "GHOST_DEBIT_RISK",
        "affected_cards": ["Verve", "Mastercard"],
        "unaffected_cards": ["Visa"],
        "failure_rate": 0.42,
        "avg_latency_ms": 8450,
        "recommended_action": "Switch default terminal route to alternative bank channels immediately.",
    }

    print("--- First Attempt (Should Send) ---")
    await send_incident_alert(test_incident)

    print("\n--- Second Attempt (Should Suppress) ---")
    await send_incident_alert(test_incident)


if __name__ == "__main__":
    asyncio.run(main())
