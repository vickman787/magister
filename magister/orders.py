from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from magister.config import data_dir
from magister.models import ApprovedOrder, Proposal, RiskVerdict


class OrderDesk:
    def __init__(self) -> None:
        self.orders_path: Path = data_dir() / "orders.jsonl"

    def dispatch(self, proposal: Proposal, verdict: RiskVerdict) -> ApprovedOrder:
        order = ApprovedOrder(
            order_id=str(uuid.uuid4())[:8],
            symbol=proposal.symbol,
            side=proposal.side,
            quote_usdt=proposal.quote_usdt,
            approved_notional_usdt=verdict.approved_notional_usdt,
            thesis=proposal.thesis,
            created=datetime.now(timezone.utc).isoformat(),
        )
        with open(self.orders_path, "a", encoding="utf-8") as handle:
            handle.write(order.model_dump_json() + "\n")
        return order

    def pending(self) -> list[ApprovedOrder]:
        return [order for order in self._read() if order.status == "pending"]

    def fill(
        self,
        order_id: str,
        base_quantity: float,
        average_price: float,
        quote_usdt: float | None = None,
    ) -> ApprovedOrder:
        orders = self._read()
        target = next((order for order in orders if order.order_id == order_id), None)
        if target is None:
            raise RuntimeError(f"no order with id {order_id}")
        if target.status != "pending":
            raise RuntimeError(f"order {order_id} already {target.status}")
        filled = ApprovedOrder(
            order_id=target.order_id,
            symbol=target.symbol,
            side=target.side,
            quote_usdt=target.quote_usdt,
            approved_notional_usdt=target.approved_notional_usdt,
            thesis=target.thesis,
            created=target.created,
            status="filled",
            reference_price=target.reference_price,
            base_quantity=base_quantity,
            quote_filled_usdt=quote_usdt,
        )
        kept = [order for order in orders if order.order_id != order_id]
        kept.append(filled)
        self._write_all(kept)
        return filled

    def _read(self) -> list[ApprovedOrder]:
        if not self.orders_path.exists():
            return []
        orders: list[ApprovedOrder] = []
        with open(self.orders_path, "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    orders.append(ApprovedOrder.model_validate_json(line))
                except Exception:
                    continue
        return orders

    def _write_all(self, orders: list[ApprovedOrder]) -> None:
        with open(self.orders_path, "w", encoding="utf-8") as handle:
            for order in orders:
                handle.write(order.model_dump_json() + "\n")
