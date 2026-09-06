from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Proposal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    symbol: str
    side: str = Field(pattern="^(BUY|SELL)$")
    quote_usdt: float = Field(gt=0)
    reference_price: float | None = None
    conviction: float = Field(default=0.5, ge=0, le=1)
    thesis: str = ""
    horizon: str = ""


class RiskVerdict(BaseModel):
    symbol: str
    allowed: bool
    reason: str = ""
    approved_notional_usdt: float = 0.0


class ExecutionReceipt(BaseModel):
    symbol: str
    side: str
    base_quantity: float | None = None
    quote_amount_usdt: float | None = None
    average_price: float | None = None
    status: str = "dry_run"
    raw: dict[str, Any] = Field(default_factory=dict)
    ts: str = Field(default_factory=utc_now)


class ApprovedOrder(BaseModel):
    order_id: str
    symbol: str
    side: str
    quote_usdt: float = Field(gt=0)
    approved_notional_usdt: float = Field(gt=0)
    thesis: str = ""
    created: str = Field(default_factory=utc_now)
    status: str = "pending"
    reference_price: float | None = None
    base_quantity: float | None = None
    quote_filled_usdt: float | None = None


class CycleReport(BaseModel):
    ts: str = Field(default_factory=utc_now)
    proposals: list[Proposal] = Field(default_factory=list)
    verdicts: list[RiskVerdict] = Field(default_factory=list)
    receipts: list[ExecutionReceipt] = Field(default_factory=list)
