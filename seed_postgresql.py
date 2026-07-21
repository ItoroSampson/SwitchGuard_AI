import os
import urllib.parse

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


def migrate_seed_data():
    csv_path = "pos_seed_data.csv"

    if not os.path.exists(csv_path):
        print(f" Error: Could not find '{csv_path}' in current directory.")
        return

    print(f" Reading {csv_path}...")
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

    if "pos_provider" in df.columns:
        df["pos_provider"] = df["pos_provider"].astype(str).str.strip().str.title()

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        df["timestamp"] = df["timestamp"].fillna("2026-07-09 12:00:00")

    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(
            df["amount"].astype(str).str.replace(r"[^0-9.]", "", regex=True),
            errors="coerce",
        ).fillna(500.0)

    if "issuing_bank" in df.columns:
        df = df.drop(columns=["issuing_bank"])

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

    print(" Re-seeding database with sanitized schema...")
    with engine.begin() as conn:
        df.to_sql(
            name="historical_transactions",
            con=conn,
            if_exists="replace",
            index=True,
            index_label="id",
        )

    print(" Migration complete!")

    with engine.connect() as conn:
        total = conn.execute(
            text("SELECT COUNT(*) FROM historical_transactions")
        ).scalar()
        print(f" Verified total rows in 'historical_transactions': {total}")


if __name__ == "__main__":
    migrate_seed_data()
