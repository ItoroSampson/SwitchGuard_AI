import os
import urllib.parse

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")

safe_password = urllib.parse.quote_plus(DB_PASSWORD)
DATABASE_URL = f"postgresql://{DB_USER}:{safe_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    total_rows = conn.execute(
        text("SELECT COUNT(*) FROM historical_transactions")
    ).scalar()
    print(f"📊 Total rows inside 'historical_transactions': {total_rows}")

    breakdown_query = text("""
        SELECT pos_provider, COUNT(*) as record_count 
        FROM historical_transactions 
        GROUP BY pos_provider
    """)
    df = pd.read_sql(breakdown_query, conn)
    print("\n Provider Breakdown in Database:")
    print(df.to_string(index=False))
