# Magister

A risk-governed AI portfolio agent for the **Binance Agent OS Mini Hackathon (Track A)**.

The design answers agentic trading's hardest question: *how do you keep an LLM-powered trader inside
its guardrails?* The answer is **separation of duties** and a **human-in-the-loop execution channel
that is exactly how Binance's Agent OS is built to be used**:

```
Analyst (LLM, no trading tools)
   -> Risk (deterministic rules engine, no LLM, no tools)
      -> OrderDesk (approved orders, queued)
         -> AI client (Codex/ChatGPT) executes via the Agent OS MCP server
              with your "yes" in chat, then reports the fill back
         -> Audit ledger (append-only JSONL + daily report)
```

Magister never holds exchange keys. It decides what is safe to trade; your AI client -- connected to
Binance Agent OS over MCP with OAuth -- executes only the orders Magister approves, restating each
one and waiting for your confirmation.

## Architecture

```
                        +-----------------------------------+
                        |         Analyst (LLM agent)       |
                        |  reads market snapshot           |
                        |  proposes trades (JSON)          |
                        |  NO Binance access               |
                        +----------------+------------------+
                                         |
                                         | Proposal {symbol, side, quote, thesis}
                                         v
                        +----------------+------------------+
                        |  RiskEngine (deterministic rules) |
                        |  clamps / rejects / kill switch   |
                        +----------------+------------------+
                                         |
                                         | approved order
                                         v
                        +----------------+------------------+
                        |  OrderDesk (data/orders.jsonl)    |
                        +----------------+------------------+
                                         |
                                         | AI client executes via Agent OS MCP
                                         | restates order, human approves in chat
                                         v
                        +-----------------------------------+
                        |  AuditLedger (append-only JSONL)  |
                        |  report / positions / PnL         |
                        +-----------------------------------+
```

## Modules

See `docs/ARCHITECTURE.md` for the full diagram and data flow.

- `magister/analyst.py` - LLM proposes trades from a market snapshot. Has no Binance access.
- `magister/risk.py` - hard-coded rules: per-symbol caps, total exposure cap, max open positions,
  daily-loss limit, kill switch. Deterministic, testable, no LLM.
- `magister/orders.py` - OrderDesk: queues approved orders to `data/orders.jsonl` for the AI client
  and marks them filled when fills are reported back.
- `magister/audit.py` - append-only ledger. Every proposal, verdict, order, and fill is recorded and
  can be replayed into a daily report.
- `magister/market.py` - public market data (price, recent return) for the Analyst's snapshot.
- `magister/llm.py` - OpenAI-compatible client; swap in any provider by changing `LLM_BASE_URL`.
- `magister/main.py` - CLI orchestrator (`run`, `demo`, `pending`, `record-fill`, `report`).

## Requirements

- Python 3.11+ (managed here with `uv`)
- An LLM API key (OpenAI works out of the box; DeepSeek/others via `LLM_BASE_URL`)
- A Binance account, and an AI client (Codex CLI, ChatGPT, Claude, Cursor, VS Code) that can connect
  to the Agent OS MCP server via OAuth. No Binance API keys are stored anywhere.

## Quickstart

```powershell
uv sync                              # creates .venv and installs dependencies
Copy-Item .env.example .env          # then fill in OPENAI_API_KEY
uv run python -m magister.main demo  # queue one approved $10 order (no network needed)
uv run python -m magister.main pending
uv run python -m magister.main report
```

`run` needs live market data + the LLM:

```powershell
uv run python -m magister.main run   # analyst -> risk -> queues approved orders
```

## Enabling live execution through Agent OS (MCP)

1. Install Codex CLI (or use ChatGPT/Claude/VS Code) and connect it to Binance Agent OS:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"
codex mcp add binance-mcp-server --url https://agent.binance.com/mcp/agentic --oauth-client-id codex
```

> Older Codex CLI versions don't support `--oauth-client-id` — if it errors, run the
> command without that flag: `codex mcp add binance-mcp-server --url https://agent.binance.com/mcp/agentic`

2. Run the client and authenticate when Binance shows the "Agentic Account Access" consent screen.
   Binance auto-creates the **Agentic sub-account** on first authorization.
3. Fund it (it starts empty; agents can never pull from your main account):
   Profile -> Dashboard -> Sub-account -> Asset Management -> **Transfer**. ~$10-20 USDT is enough.
4. Queue an order with Magister: `uv run python -m magister.main demo --symbol BTCUSDT --quote 10`.
5. In the AI client, say: *"Read data/orders.jsonl and place the pending order. Restate it before
   sending."* It restates; you say yes; Binance fills it.
6. Report the fill back to the ledger with the numbers the client shows:

```powershell
uv run python -m magister.main record-fill --id <order_id> --base-qty 0.000153 --avg-price 65210.00
uv run python -m magister.main report
```

Emergency stop (disconnect all agents + cancel all positions/orders) lives at
Profile -> Dashboard -> Sub-account -> Account Management -> **Emergency stop**.

## Demo flows for the submission video

- **Guardrail demo:** queue `demo --quote 200` and watch Risk clamp it to `max_notional_per_symbol`;
  touch `data/kill_switch` and watch everything stop.
- **Real trade (human-in-the-loop):** Magister approves -> AI client restates the order through the
  Agent OS MCP server -> you approve in chat -> fill recorded -> `report` shows the live position.
- **Audit trail:** `report` shows today's buys/sells, realized PnL, current exposure, and open
  positions reconstructed purely from the log.

## Risk controls (config/risk_limits.yaml)

| Limit | Default | Meaning |
| --- | --- | --- |
| `max_notional_usdt` | 25 | max total exposure |
| `max_notional_per_symbol_usdt` | 15 | max per single trade |
| `max_open_positions` | 3 | simultaneous positions |
| `max_daily_loss_usdt` | 10 | realized-loss stop for the day |
| `kill_switch_file` | data/kill_switch | create this file -> Magister goes read-only |
| `allowed_symbols` | BTCUSDT, ETHUSDT | hard whitelist |

The kill switch is checked before every order. A second, platform-level kill switch (Emergency stop)
exists on Binance's side for the connected agents.

## Submission checklist (Track A)

- [x] Follow @Binance and repost the hackathon post
- [x] Record a <2 min video: problem -> architecture diagram -> guardrail demo -> real order through
      Agent OS MCP with human approval -> audit report
- [x] Make this repo public on GitHub with the README and diagram
- [x] Reply/quote the post with the video + repo link
- [x] Complete the survey linked in the post
- [x] Submit before the deadline
- [x] Skill PR to the official Binance Skills Hub: https://github.com/binance/binance-skills-hub/pull/335 (do not wait for the final day)
