import os
import random
import urllib.parse

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


def resolve_missing_banks(df: pd.DataFrame) -> pd.DataFrame:
    """
    Imputation & Resolution Utility: If the handwritten historical ledger left
    the issuing bank empty, this dynamically injects realistic distributions
    of Nigerian commercial banks to allow for deep financial risk audits.
    """
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


def detect_switchguard_anomalies() -> pd.DataFrame:
    """
    Queries historical ledger items and flags statistical anomalies
    such as high value transaction outliers and structural ghost debits.
    """
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "postgres")

    safe_password = urllib.parse.quote_plus(DB_PASSWORD)
    DATABASE_URL = (
        f"postgresql://{DB_USER}:{safe_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    engine = create_engine(DATABASE_URL)

    query = text("""
        SELECT timestamp, pos_provider, issuing_bank, terminal_id, card_type, amount, off_status, response_code, ghost_debit
        FROM historical_transactions
        ORDER BY timestamp DESC
    """)

    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    if df.empty:
        return df

    df = resolve_missing_banks(df)

    mean_amt = df["amount"].mean()
    std_amt = df["amount"].std()

    amt_threshold = mean_amt + (2 * std_amt) if std_amt > 0 else 50000

    anomalies = df[
        (df["ghost_debit"] == True)
        | (df["amount"] > amt_threshold)
        | (df["response_code"].isin(["91", "68"]))
    ].copy()

    return anomalies


if __name__ == "__main__":
    print(" Running SwitchGuard AI Batch Fraud Anomaly Detector...")
    flagged_df = detect_switchguard_anomalies()

    print("\n================ HISTORICAL AUDIT TARGETS IDENTIFIED ================")
    if flagged_df.empty:
        print(" Clean Audit Trail: No statistical network or fraud anomalies found.")
    else:
        print(f" Flagged {len(flagged_df)} transactional anomalies requiring review:\n")

        display_cols = [
            "timestamp",
            "pos_provider",
            "issuing_bank",
            "card_type",
            "amount",
            "response_code",
            "ghost_debit",
        ]

        print(flagged_df[display_cols].to_string(index=False))

    print("=====================================================================")
