from datetime import datetime

from pydantic import BaseModel, Field


class TransactionIngest(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "TXN_1785255327_1"})
    terminal_id: str = Field(..., json_schema_extra={"example": "TERM_4401"})
    pos_provider: str = Field(..., json_schema_extra={"example": "Moniepoint"})
    issuing_bank: str = Field(..., json_schema_extra={"example": "GTBank"})
    card_type: str = Field(..., json_schema_extra={"example": "Verve"})
    amount: float = Field(..., gt=0, json_schema_extra={"example": 2500.00})
    response_code: str = Field(..., json_schema_extra={"example": "91"})
    off_status: str = Field(default="ONLINE", json_schema_extra={"example": "ONLINE"})
    ghost_debit: bool = Field(default=False)
    timestamp: datetime | None = Field(
        default=None,
        description="Transaction timestamp (UTC offset recommended)",
        json_schema_extra={"example": "2026-07-29T06:58:21Z"},
    )


class RouteHealth(BaseModel):
    sample_window: str = "5m"
    total_volume: int
    failure_rate_pct: float
    ghost_debit_count: int
    route_degraded: bool


class IngestionResponse(BaseModel):
    status: str
    id: str
    message: str
    route_health: RouteHealth
