import os
import urllib.parse
from datetime import datetime, timezone

import redis.asyncio as aioredis
import sentry_sdk
from app.schemas import IngestionResponse, RouteHealth, TransactionIngest
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()


SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=1.0,
        environment=os.getenv("ENVIRONMENT", "development"),
    )


DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = urllib.parse.quote_plus(os.getenv("DB_PASSWORD", ""))
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "switchguard_db")

ASYNC_DATABASE_URL = (
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
redis_client = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

app = FastAPI(title="SwitchGuard AI - Ingestion Engine", version="1.0.0")

HARD_ERROR_CODES = {"91", "96", "TO", "PY", "98", "06", "A3", "N5"}
FAILURE_THRESHOLD_PCT = 30.0
WINDOW_SECONDS = 300


@app.post(
    "/api/v1/transactions/ingest",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_transaction(payload: TransactionIngest):
    txn_time = payload.timestamp or datetime.now(timezone.utc)
    epoch_ts = txn_time.timestamp()
    window_start = epoch_ts - WINDOW_SECONDS

    insert_sql = text("""
        INSERT INTO historical_transactions (
            terminal_id, pos_provider, issuing_bank, 
            card_type, amount, response_code, off_status, ghost_debit, timestamp
        ) VALUES (
            :terminal_id, :pos_provider, :issuing_bank, 
            :card_type, :amount, :response_code, :off_status, :ghost_debit, :timestamp
        );
    """)

    try:
        async with AsyncSessionLocal() as session, session.begin():
            await session.execute(
                insert_sql,
                {
                    "terminal_id": payload.terminal_id,
                    "pos_provider": payload.pos_provider,
                    "issuing_bank": payload.issuing_bank,
                    "card_type": payload.card_type,
                    "amount": payload.amount,
                    "response_code": payload.response_code,
                    "off_status": payload.off_status,
                    "ghost_debit": payload.ghost_debit,
                    "timestamp": txn_time.isoformat()
                    if hasattr(txn_time, "isoformat")
                    else str(txn_time),
                },
            )

        route_key = f"route:{payload.issuing_bank}:{payload.pos_provider}"
        is_hard_error = "1" if payload.response_code in HARD_ERROR_CODES else "0"
        is_ghost = "1" if payload.ghost_debit else "0"

        member = f"{payload.id}:{is_hard_error}:{is_ghost}"

        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.zadd(route_key, {member: epoch_ts})

            pipe.zremrangebyscore(route_key, "-inf", window_start)

            pipe.zrangebyscore(route_key, window_start, "+inf")

            pipe.expire(route_key, 600)
            results = await pipe.execute()

        window_members: list[str] = results[2]

        total_vol = len(window_members) or 1
        hard_errors = 0
        ghost_count = 0

        for item in window_members:
            parts = item.split(":")
            if len(parts) == 3:
                if parts[1] == "1":
                    hard_errors += 1
                if parts[2] == "1":
                    ghost_count += 1

        failure_pct = round((hard_errors / total_vol) * 100.0, 2)
        is_degraded = failure_pct >= FAILURE_THRESHOLD_PCT

        return IngestionResponse(
            status="success",
            id=payload.id,
            message="Transaction logged and route metrics updated in Redis.",
            route_health=RouteHealth(
                sample_window="5m",
                total_volume=total_vol,
                failure_rate_pct=failure_pct,
                ghost_debit_count=ghost_count,
                route_degraded=is_degraded,
            ),
        )

    except Exception as e:
        sentry_sdk.capture_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest transaction: {e!s}",
        )
