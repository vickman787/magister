from __future__ import annotations

import argparse
import sys

from magister import config as cfg
from magister.analyst import Analyst
from magister.audit import AuditLedger
from magister.market import MarketData
from magister.models import CycleReport, ExecutionReceipt, Proposal
from magister.orders import OrderDesk
from magister.risk import RiskEngine

CODEX_INSTRUCTIONS = (
    "\n=== NEXT STEP: execute via your AI client (Agent OS MCP) ===\n"
    "In Codex/ChatGPT connected to the Binance Agent OS MCP server:\n"
    '  "Read {orders_file}, then place the pending order for '
    '{symbol} at ~{quote:.2f} USDT. Restate it before sending."\n'
    "You approve in chat. Binance fills it. Then run:\n"
    "  uv run python -m magister.main record-fill --id {order_id} "
    "--base-qty <filled qty> --avg-price <fill price>"
)


def _instructions(order, orders_file: str) -> str:
    return CODEX_INSTRUCTIONS.format(
        orders_file=orders_file,
        symbol=order.symbol,
        quote=order.approved_notional_usdt,
        order_id=order.order_id,
    )


def cmd_run(args: argparse.Namespace) -> int:
    cfg.bootstrap()
    settings = cfg.load_settings()
    limits = cfg.load_risk_limits()
    ledger = AuditLedger()
    symbols = settings.get("symbols", ["BTCUSDT", "ETHUSDT"])

    try:
        snapshot = MarketData().snapshot(symbols)
    except Exception as exc:
        print(f"market data unavailable: {exc}", file=sys.stderr)
        return 2
    ledger.log("market_snapshot", {"snapshot": snapshot})

    try:
        proposals = Analyst(settings).analyze(snapshot)
    except Exception as exc:
        print(f"analyst failed: {exc}", file=sys.stderr)
        return 2

    risk = RiskEngine(limits, ledger)
    verdicts = [risk.vet(proposal) for proposal in proposals]
    report = CycleReport(proposals=proposals, verdicts=verdicts)
    ledger.log(
        "cycle",
        {
            "proposals": [p.model_dump(mode="json") for p in proposals],
            "verdicts": [v.model_dump(mode="json") for v in verdicts],
        },
    )

    desk = OrderDesk()
    orders = []
    for proposal, verdict in zip(proposals, verdicts):
        if not verdict.allowed or verdict.approved_notional_usdt <= 0:
            continue
        order = desk.dispatch(proposal, verdict)
        ledger.log("approved_order", order.model_dump(mode="json"))
        orders.append(order)

    print("=== CYCLE REPORT ===")
    print(report.model_dump_json(indent=2))
    print("\nApproved orders queued for the AI client:")
    for order in orders:
        print(_instructions(order, str(desk.orders_path)))
    if not orders:
        print("nothing approved this cycle")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    cfg.bootstrap()
    settings = cfg.load_settings()
    limits = cfg.load_risk_limits()
    ledger = AuditLedger()
    symbols = settings.get("symbols", ["BTCUSDT", "ETHUSDT"])
    symbol = args.symbol or symbols[0]
    risk = RiskEngine(limits, ledger)

    proposal = Proposal(
        symbol=symbol,
        side="BUY",
        quote_usdt=float(args.quote),
        thesis="manual demo trade",
    )
    verdict = risk.vet(proposal)
    print(
        f"RISK VERDICT: allowed={verdict.allowed} "
        f"notional=${verdict.approved_notional_usdt:.2f} reason={verdict.reason}"
    )
    if not verdict.allowed or verdict.approved_notional_usdt <= 0:
        return 1

    desk = OrderDesk()
    order = desk.dispatch(proposal, verdict)
    ledger.log("approved_order", order.model_dump(mode="json"))
    print(order.model_dump_json(indent=2))
    print(_instructions(order, str(desk.orders_path)))
    return 0


def cmd_pending(args: argparse.Namespace) -> int:
    cfg.bootstrap()
    desk = OrderDesk()
    orders = desk.pending()
    if not orders:
        print("no pending approved orders")
        return 0
    for order in orders:
        print(order.model_dump_json(indent=2))
    return 0


def cmd_record_fill(args: argparse.Namespace) -> int:
    cfg.bootstrap()
    ledger = AuditLedger()
    desk = OrderDesk()
    quote = args.quote
    if args.id:
        order = desk.fill(args.id, args.base_qty, args.avg_price, quote_usdt=quote)
        symbol, side = order.symbol, order.side
        if quote is None:
            quote = order.base_quantity * args.avg_price
    else:
        symbol = args.symbol
        side = args.side
        if not symbol:
            raise SystemExit("record-fill needs --id or --symbol")
        if quote is None:
            quote = args.base_qty * args.avg_price

    receipt = ExecutionReceipt(
        symbol=symbol,
        side=side,
        base_quantity=args.base_qty,
        quote_amount_usdt=round(quote, 2),
        average_price=args.avg_price,
        status="filled",
        raw={"filled_from": "ai_client_mcp"},
    )
    ledger.log("execution", receipt.model_dump(mode="json"))
    print(receipt.model_dump_json(indent=2))
    print("\nUpdated portfolio:")
    print(ledger.summary_daily())
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    cfg.bootstrap()
    ledger = AuditLedger()
    print(ledger.summary_daily())
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="magister", description="Magister - risk-governed portfolio agent")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="one analyst -> risk cycle; queue approved orders for the AI client").set_defaults(
        func=cmd_run
    )

    demo_parser = sub.add_parser("demo", help="queue a single safe demo order for the AI client")
    demo_parser.add_argument("--symbol", default=None)
    demo_parser.add_argument("--quote", default="10")
    demo_parser.set_defaults(func=cmd_demo)

    sub.add_parser("pending", help="list approved orders waiting for the AI client").set_defaults(
        func=cmd_pending
    )

    fill_parser = sub.add_parser("record-fill", help="record a fill reported by the AI client into the audit ledger")
    fill_parser.add_argument("--id", default=None, help="approved order id (preferred)")
    fill_parser.add_argument("--symbol", default=None)
    fill_parser.add_argument("--side", default="BUY")
    fill_parser.add_argument("--base-qty", required=True, type=float)
    fill_parser.add_argument("--avg-price", required=True, type=float)
    fill_parser.add_argument("--quote", default=None, type=float)
    fill_parser.set_defaults(func=cmd_record_fill)

    sub.add_parser("report", help="print daily summary and open positions from the ledger").set_defaults(
        func=cmd_report
    )

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
