# Architecture

## Diagram

```
                        +-----------------------------------+
                        |         Analyst (LLM agent)       |
                        |  reads market snapshot           |
                        |  proposes trades (JSON)          |
                        |  NO Binance access               |
                        +----------------+------------------+
                                         |
                                         | Proposal {symbol, side, quote_usdt, thesis}
                                         v
                        +----------------+------------------+
                        |  RiskEngine (deterministic code)  |
                        |  whitelist / caps / exposure /    |
                        |  daily loss / kill switch         |
                        |  clamps or rejects                |
                        +----------------+------------------+
                                         |
                                         | RiskVerdict {allowed, approved_notional_usdt}
                                         v
                        +----------------+------------------+
                        |  OrderDesk (approved orders)      |
                        |  data/orders.jsonl  (status)      |
                        +----------------+------------------+
                                         |
                                         | approved order, read by the AI client
                                         v
                        +----------------+------------------+
                        |  AI client (Codex/ChatGPT/...)    |
                        |  executes via Agent OS MCP server |
                        |  Binance OAuth; agentic sub-      |
                        |  account; human "yes" in chat;    |
                        |  no withdrawal scope              |
                        +----------------+------------------+
                                         |
                                         | fill reported back (qty + price)
                                         v
                        +----------------+------------------+
                        |  AuditLedger (append-only JSONL)  |
                        |  -> report / PnL / positions      |
                        +-----------------------------------+
```

Magister decides; it never holds exchange credentials and never sends an order itself. Execution is
delegated to the AI client over Binance Agent OS's MCP server -- the integration surface Binance
documents and the one the hackathon is built around. Binance's platform keeps a second set of rails
intact: OAuth consent, confirm-before-execute, no withdrawal scope, and an Emergency stop.

## Data flow for one cycle

1. `MarketData.snapshot(symbols)` - public prices + 4h returns (read-only).
2. `Analyst.analyze(snapshot)` - LLM returns up to N structured `Proposal`s.
3. `RiskEngine.vet(proposal)` for each - deterministic rules, returns `RiskVerdict`.
4. Approved orders are queued by `OrderDesk` to `data/orders.jsonl`; proposals/verdicts/orders are
   logged to the audit ledger before anything is sent anywhere.
5. The AI client reads the queue and, over the Agent OS MCP server, restates and places the order
   only after the human confirms in chat.
6. The fill (quantity + average price) is reported back with `record-fill`, appending an
   `execution` event to the ledger.
7. `report` reconstructs positions, exposure, and realized PnL from the log; nothing is stored in
   the LLM or the exchange's memory.

## Safety model

| Risk | Control |
| --- | --- |
| LLM goes rogue and over-trades | deterministic clamp + Binance's in-chat confirmation |
| Prompt injection pushes a bad symbol | hard `allowed_symbols` whitelist |
| Unbounded exposure | `max_notional_usdt` + `max_open_positions` |
| Runaway loss loop | `max_daily_loss_usdt` day stop |
| Anything unexpected | physical kill-switch file checked before every order |
| Agent funds drained to an external address | Agent OS has no withdrawal scope, by design |

## How Agent OS fits

- The execution channel is the Agent OS MCP server (`https://agent.binance.com/mcp/agentic`),
  connected from a supported AI client via Binance OAuth (client IDs such as `codex` / `grok` are
  documented for non-interactive registration).
- The Agentic sub-account is auto-created on first authorization and funded manually from the web UI
  (Profile -> Dashboard -> Sub-account -> Asset Management -> Transfer). It starts empty; the agent
  can only move funds between wallets *inside* the sub-account.
- `scripts/list_mcp_tools.py` probes the live server and dumps its tool schema to
  `tools_discovered.json` for reference.
- Future differentiators (not required for v1): x402 machine payments and Wallet Agentic Hub on-chain
  steps, kept behind the same RiskEngine so a paid data call or invoice settlement also passes the
  same gates.
