import os
import urllib.parse

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.types import Boolean, DateTime, Numeric, String

load_dotenv()

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "********ITORO.2014")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")


safe_password = urllib.parse.quote_plus(DB_PASSWORD)

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)

init_engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")

with init_engine.connect() as conn:
    result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'"))
    if not result.scalar():
        print(f" Creating missing database: '{DB_NAME}'...")
        conn.execute(text(f"CREATE DATABASE {DB_NAME}"))


def clean_and_seed_data(csv_file_path: str):
    print(f" Reading historical seed data from {csv_file_path}...")
    if not os.path.exists(csv_file_path):
        print(
            f" Error: {csv_file_path} not found. Did you run the batch OCR script first?"
        )
        return

    df = pd.read_csv(csv_file_path)

    print(" Cleaning telemetry fields for database optimization...")

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    df["amount"] = (
        df["amount"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("w", "00", regex=False)
        .str.extract(r"(\d+)")
    )
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)

    df["ghost_debit"] = df["ghost_debit"].astype(str).str.lower().str.strip() == "true"

    df["terminal_id"] = df["terminal_id"].replace({pd.NA: None, "NaN": None, "": None})
    df["pos_provider"] = df["pos_provider"].str.strip().str.upper()
    df["card_type"] = df["card_type"].str.strip().str.capitalize()
    df["off_status"] = df["off_status"].str.strip().str.capitalize()
    df["response_code"] = df["response_code"].astype(str).str.strip()

    df = df.dropna(subset=["timestamp"])

    print(f" Connecting to PostgreSQL database: '{DB_NAME}'...")
    engine = create_engine(DATABASE_URL)

    schema_mapping = {
        "timestamp": DateTime,
        "pos_provider": String(50),
        "terminal_id": String(50),
        "card_type": String(20),
        "amount": Numeric(12, 2),
        "off_status": String(20),
        "response_code": String(10),
        "ghost_debit": Boolean,
    }

    print(" Seeding transactions table...")
    with engine.connect() as connection:
        df.to_sql(
            name="historical_transactions",
            con=connection,
            if_exists="replace",
            index=True,
            index_label="id",
            dtype=schema_mapping,
        )

        connection.execute(
            text("ALTER TABLE historical_transactions ADD PRIMARY KEY (id);")
        )
        connection.commit()

    print(f" Success! Migrated {len(df)} cleaned transaction records to PostgreSQL.")


if __name__ == "__main__":
    clean_and_seed_data("pos_seed_data.csv")
