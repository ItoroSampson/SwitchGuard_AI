import os
import random
import urllib.parse
from typing import Any, Dict, List

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from switch_guard_engine import SwitchGuardEngine

load_dotenv()


def resolve_missing_banks(df: pd.DataFrame) -> pd.DataFrame:
    """Injects realistic distributions of Nigerian commercial banks in-memory."""
    if "issuing_bank" not in df.columns:
        df["issuing_bank"] = None

    nigerian_banks = [
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
    weights = [0.22, 0.18, 0.15, 0.12, 0.08, 0.08, 0.05, 0.04, 0.08]

    df["issuing_bank"] = df["issuing_bank"].fillna("")
    df["issuing_bank"] = df.apply(
        lambda row: (
            random.choices(nigerian_banks, weights=weights)[0]
            if str(row["issuing_bank"]).strip() == ""
            else row["issuing_bank"]
        ),
        axis=1,
    )
    return df


def get_recent_transactions(pos_provider: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Fetches latest transactions for a provider with dynamic latency injection for simulation."""
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "postgres")

    safe_password = urllib.parse.quote_plus(DB_PASSWORD) if DB_PASSWORD else ""
    DATABASE_URL = (
        f"postgresql://{DB_USER}:{safe_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    engine = create_engine(DATABASE_URL)

    query = text("""
        SELECT timestamp, pos_provider, terminal_id, card_type, amount, response_code, ghost_debit
        FROM historical_transactions
        WHERE LOWER(pos_provider) = LOWER(:provider)
        ORDER BY timestamp DESC
        LIMIT :limit
    """)

    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"provider": pos_provider, "limit": limit})

    df = resolve_missing_banks(df)

    if "latency_ms" not in df.columns:
        df["latency_ms"] = df["response_code"].apply(
            lambda code: (
                random.uniform(4500.0, 9500.0)
                if str(code).strip() in ["91", "TO", "98", "96", "PY", "06", "A3", "N5"]
                else random.uniform(200.0, 1200.0)
            )
        )

    return df.to_dict(orient="records")


if __name__ == "__main__":
    guard = SwitchGuardEngine(
        failure_rate_threshold=0.30,
        latency_threshold_ms=4000.0,
        half_life_seconds=120.0,
    )

    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "postgres")

    safe_password = urllib.parse.quote_plus(DB_PASSWORD) if DB_PASSWORD else ""
    DATABASE_URL = (
        f"postgresql://{DB_USER}:{safe_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    engine = create_engine(DATABASE_URL)

    try:
        with engine.connect() as conn:
            providers_df = pd.read_sql(
                text(
                    "SELECT DISTINCT UPPER(pos_provider) AS pos_provider FROM historical_transactions WHERE pos_provider IS NOT NULL"
                ),
                conn,
            )
            providers = sorted(
                list(set(providers_df["pos_provider"].str.title().tolist()))
            )
    except Exception as e:
        print(f" Could not fetch unique providers: {e}")
        providers = ["Opay", "Palmpay", "Moniepoint"]

    print(f" Discovered active payment switches to evaluate: {providers}\n")

    for provider in providers:
        records = get_recent_transactions(provider, limit=15)

        if not records:
            print(f" No recent transaction activity logged for {provider}. Skipping.")
            print("-" * 50)
            continue

        print(f" Evaluating last {len(records)} records for {provider}...")
        analysis = guard.analyze_route_window(records)
        metrics = analysis.get("metrics", {})

        should_alert = analysis.get("alert_recommended", False)
        recommended_action = analysis.get(
            "merchant_action_recommended", "STAY_ON_ROUTE"
        )

        print(f"================ {provider.upper()} ROUTE STATUS ================")
        if should_alert:
            print(f" ALERT MERCHANTS ({recommended_action}): {analysis['reason']}")
        else:
            print(f" ROUTE HEALTHY: {analysis['reason']}")

        print("-----------------------------------------------")
        print("Advanced Network Signals Evaluated:")
        print(
            f" - Time-Decayed Hard Failure Rate: {metrics.get('weighted_failure_rate', 0):.1%}"
        )
        print(
            f" - Average Response Latency:       {metrics.get('avg_latency_ms', 0):.0f} ms"
        )
        print(
            f" - Hard Technical Errors:          {metrics.get('hard_technical_errors', 0)}"
        )
        print(
            f" - Soft User Errors Ignored:       {metrics.get('soft_user_errors_ignored', 0)}"
        )
        print(
            f" - Max Consecutive Hard Strikes:   {metrics.get('max_consecutive_hard_strikes', 0)}"
        )
        print(
            f" - Local Terminal Issue Flag:     {metrics.get('isolated_terminal_issue', False)}"
        )

        if metrics.get("isolated_issuer_issue"):
            print(
                f" -  Issuer Bank Down Flag:       TRUE (Culprit: {metrics.get('faulty_issuer')})"
            )
        else:
            print(" -  Issuer Bank Down Flag:       False")

        print(
            f" -  Ghost Debit Risk Count:      {metrics.get('ghost_debit_risk_count', 0)}"
        )
        print(
            f" -  Route Recovered Status:      {metrics.get('route_recovered', False)}"
        )

        print("\n TRANSACTION EVALUATION LOG WINDOW:")
        window_df = pd.DataFrame(records)
        display_cols = [
            "timestamp",
            "terminal_id",
            "pos_provider",
            "issuing_bank",
            "amount",
            "response_code",
            "latency_ms",
            "ghost_debit",
        ]

        for col in display_cols:
            if col not in window_df.columns:
                window_df[col] = None

        window_df["latency_ms"] = window_df["latency_ms"].fillna(0).round(0).astype(int)
        print(window_df[display_cols].to_string(index=False))

        if should_alert:
            print("\n [MOCK DISPATCH] Triggering Telegram/SMS Merchant Alert:")
            print(
                f"   Message: ' ATTENTION ({provider}): {analysis['reason']} | Recommended Action: {recommended_action}.'"
            )

        print("=" * 70 + "\n")
