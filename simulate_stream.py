import random
import time
from datetime import datetime, timezone

import requests

API_URL = "http://127.0.0.1:8000/api/v1/transactions/ingest"

BANKS = [
    "GTBank",
    "Zenith Bank",
    "Access Bank",
    "First Bank",
    "UBA",
    "Wema Bank",
    "Sterling Bank",
    "Stanbic Bank",
    "Polaris Bank",
]
SWITCHES = ["Moniepoint", "Opay", "Palmpay"]
CARD_TYPES = ["Verve", "Mastercard", "Visa"]

RESPONSE_CODES = [
    "00",
    "51",
    "55",
    "91",
    "96",
    "TO",
    "98",
    "PY",
    "06",
    "A3",
    "N5",
    "61",
    "75",
    "14",
    "01",
    "68",
    "41",
]


def generate_mock_transaction(txn_index: int) -> dict:
    issuing_bank = random.choice(BANKS)
    pos_provider = random.choice(SWITCHES)
    card_type = random.choice(CARD_TYPES)
    response_code = random.choice(RESPONSE_CODES)

    is_ghost = (
        True
        if response_code in ["91", "96", "TO", "PY", "98", "06", "A3", "N5"]
        and random.random() < 0.3
        else False
    )

    txn_id = f"TXN_{int(time.time())}_{txn_index}"

    return {
        "id": txn_id,
        "terminal_id": f"TERM_{random.randint(1000, 9999)}",
        "pos_provider": pos_provider,
        "issuing_bank": issuing_bank,
        "card_type": card_type,
        "amount": round(random.uniform(500.0, 50000.0), 2),
        "response_code": response_code,
        "off_status": (
            "OFFLINE"
            if response_code in ["TO", "96", "91", "PY", "98", "06", "A3", "N5"]
            and random.random() < 0.4
            else "ONLINE"
        ),
        "ghost_debit": is_ghost,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def start_simulation(interval_seconds: float = 0.5, count: int = 30):
    print(
        f" Starting live stream simulation ({count} transactions at {interval_seconds}s intervals)..."
    )
    print(f"Target Endpoint: {API_URL}\n" + "=" * 100)

    for i in range(1, count + 1):
        payload = generate_mock_transaction(i)
        try:
            res = requests.post(API_URL, json=payload)
            if res.status_code == 201:
                print(
                    f"[{i:02d}/{count}] ✅ Txn: {payload['id']} | "
                    f"Term: {payload['terminal_id']} | "
                    f"Route: {payload['issuing_bank']} ➔ {payload['pos_provider']} | "
                    f"Card: {payload['card_type']} | "
                    f"Amt: ₦{payload['amount']:,.2f} | "
                    f"Code: {payload['response_code']} | "
                    f"Status: {payload['off_status']} | "
                    f"Ghost: {payload['ghost_debit']}"
                )
            else:
                print(f"[{i:02d}/{count}]  Failed ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"[{i:02d}/{count}] Connection Error: {e}")
            break

        time.sleep(interval_seconds)


if __name__ == "__main__":
    start_simulation(interval_seconds=0.5, count=30)
