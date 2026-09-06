from __future__ import annotations

from magister.audit import AuditLedger
from magister.config import data_dir, resolve
from magister.models import Proposal, RiskVerdict


class RiskEngine:
    def __init__(self, limits: dict, ledger: AuditLedger) -> None:
        self.limits = limits
        self.ledger = ledger
        self.kill_file = resolve(str(limits.get("kill_switch_file", data_dir() / "kill_switch")))

    def vet(self, proposal: Proposal) -> RiskVerdict:
        if self.kill_file.exists():
            return RiskVerdict(
                symbol=proposal.symbol, allowed=False, reason="kill switch is active"
            )

        if proposal.side == "SELL":
            return RiskVerdict(
                symbol=proposal.symbol,
                allowed=False,
                reason="SELL proposals disabled for v1; close positions with 'demo --close'",
            )

        allowed_symbols = set(self.limits.get("allowed_symbols", []))
        if allowed_symbols and proposal.symbol not in allowed_symbols:
            return RiskVerdict(
                symbol=proposal.symbol, allowed=False, reason=f"{proposal.symbol} not in allowed_symbols"
            )

        max_per_symbol = float(self.limits.get("max_notional_per_symbol_usdt", 15))
        notional = min(proposal.quote_usdt, max_per_symbol)

        if proposal.symbol in self.ledger.open_symbols():
            return RiskVerdict(
                symbol=proposal.symbol,
                allowed=False,
                reason=f"{proposal.symbol} already open; one position per symbol in v1",
            )

        max_open = int(self.limits.get("max_open_positions", 3))
        if len(self.ledger.open_symbols()) >= max_open:
            return RiskVerdict(
                symbol=proposal.symbol, allowed=False, reason=f"max_open_positions={max_open} reached"
            )

        exposure = self.ledger.current_exposure_usdt()
        max_total = float(self.limits.get("max_notional_usdt", 25))
        if exposure + notional > max_total:
            notional = max(0.0, max_total - exposure)

        daily_loss = self.ledger.realized_pnl_today_usdt()
        max_daily_loss = float(self.limits.get("max_daily_loss_usdt", 10))
        if daily_loss < -max_daily_loss:
            return RiskVerdict(
                symbol=proposal.symbol,
                allowed=False,
                reason=f"daily realized loss {daily_loss:.2f} exceeds limit {-max_daily_loss:.2f}",
            )

        if notional <= 0:
            return RiskVerdict(
                symbol=proposal.symbol, allowed=False, reason="approved notional clamped to zero"
            )

        return RiskVerdict(
            symbol=proposal.symbol,
            allowed=True,
            reason="ok",
            approved_notional_usdt=round(notional, 2),
        )
