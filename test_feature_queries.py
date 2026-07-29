import os
import urllib.parse

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "postgres")

safe_password = urllib.parse.quote_plus(DB_PASSWORD) if DB_PASSWORD else ""
DATABASE_URL = f"postgresql://{DB_USER}:{safe_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)


query = text("""
SELECT 
    issuing_bank AS bank_route,
    pos_provider AS pos_switch,
    card_type,
    COUNT(*) AS total_transactions,
    -- Failed transactions exclude customer soft errors (51, 55, 61, 75, 14, 01, 6841)
    COUNT(CASE 
        WHEN off_status = 'OFFLINE' OR response_code NOT IN ('00', '51', '55', '61', '75', '14', '01', '6841') 
        THEN 1 
    END) AS failed_transactions,
    
    ROUND(
        (COUNT(CASE 
            WHEN off_status = 'OFFLINE' OR response_code NOT IN ('00', '51', '55', '61', '75', '14', '01', '6841') 
            THEN 1 
        END)::NUMERIC / COUNT(*)) * 100, 2
    ) AS failure_rate_pct,
    
    -- Ghost Debit Risks trigger on flag OR Hard System Error Codes
    COUNT(CASE 
        WHEN ghost_debit IS TRUE 
          OR response_code IN ('91', '96', 'TO', '98', 'PY', '06', 'A3', 'N5') 
        THEN 1 
    END) AS ghost_debit_risks
FROM 
    historical_transactions
GROUP BY 
    issuing_bank,
    pos_provider, 
    card_type
ORDER BY 
    failure_rate_pct DESC;
""")


def run_feature_query():
    print(
        " Calculating commercial bank route stats from 'historical_transactions'...\n"
    )
    with engine.connect() as conn:
        results = conn.execute(query).fetchall()

        if not results:
            print(" No transactions found in historical_transactions.")
            return

        print(
            f"{'ISSUING BANK':<15} | {'POS SWITCH':<12} | {'CARD TYPE':<10} | {'TOTAL':<6} | {'FAILED':<6} | {'FAIL %':<8} | {'GHOST RISKS'}"
        )
        print("-" * 90)
        for row in results:
            print(
                f"{row.bank_route!s:<15} | {row.pos_switch!s:<12} | {row.card_type!s:<10} | {row.total_transactions:<6} | {row.failed_transactions:<6} | {row.failure_rate_pct:<8} | {row.ghost_debit_risks}"
            )


if __name__ == "__main__":
    run_feature_query()
