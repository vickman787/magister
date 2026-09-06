from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from magister.config import data_dir


class AuditLedger:
    def __init__(self) -> None:
        self.log_path: Path = data_dir() / "ledger.jsonl"

    def log(self, kind: str, payload: dict) -> None:
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "kind": kind, "data": payload}
        with open(self.log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

    def events(self, kinds: set[str] | None = None) -> list[dict]:
        if not self.log_path.exists():
            return []
        result = []
        with open(self.log_path, "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                event = json.loads(line)
                if kinds is None or event.get("kind") in kinds:
                    result.append(event)
        return result

    def executions(self) -> list[dict]:
        return self.events({"execution"})

    def positions(self) -> dict[str, dict]:
        return self._state()[0]

    def open_symbols(self) -> list[str]:
        positions, _ = self._state()
        return [symbol for symbol, pos in positions.items() if pos["base_qty"] > 1e-9]

    def current_exposure_usdt(self) -> float:
        positions, _ = self._state()
        return round(sum(float(pos["cost_usdt"]) for pos in positions.values()), 2)

    def realized_pnl_usdt(self) -> float:
        _, pnl_events = self._state()
        return round(sum(pnl for _, pnl in pnl_events), 4)

    def realized_pnl_today_usdt(self) -> float:
        today = datetime.now(timezone.utc).date().isoformat()
        _, pnl_events = self._state()
        return round(sum(pnl for ts, pnl in pnl_events if ts[:10] == today), 4)

    def summary_daily(self) -> dict:
        today = datetime.now(timezone.utc).date().isoformat()
        executions = [e for e in self.executions() if e["ts"][:10] == today]
        buys = [e for e in executions if e["data"].get("side") == "BUY"]
        sells = [e for e in executions if e["data"].get("side") == "SELL"]
        return {
            "date": today,
            "buys_today": len(buys),
            "sells_today": len(sells),
            "realized_pnl_today_usdt": self.realized_pnl_today_usdt(),
            "realized_pnl_total_usdt": self.realized_pnl_usdt(),
            "current_exposure_usdt": self.current_exposure_usdt(),
            "positions": self.positions(),
        }

    def _state(self) -> tuple[dict[str, dict], list[tuple[str, float]]]:
        positions: dict[str, dict] = {}
        pnl_events: list[tuple[str, float]] = []
        for event in self.executions():
            data = event["data"]
            symbol = data.get("symbol")
            side = data.get("side")
            qty = float(data.get("base_quantity") or 0)
            quote = float(data.get("quote_amount_usdt") or 0)
            if not symbol:
                continue
            entry = positions.setdefault(symbol, {"base_qty": 0.0, "cost_usdt": 0.0})
            if side == "BUY":
                entry["base_qty"] += qty
                entry["cost_usdt"] += quote
            elif side == "SELL":
                avg_cost = entry["cost_usdt"] / entry["base_qty"] if entry["base_qty"] else 0.0
                cost_consumed = avg_cost * qty
                entry["base_qty"] = max(0.0, entry["base_qty"] - qty)
                entry["cost_usdt"] = max(0.0, entry["cost_usdt"] - cost_consumed)
                pnl_events.append((event["ts"], quote - cost_consumed))
        return positions, pnl_events
