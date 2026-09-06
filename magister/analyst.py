from __future__ import annotations

import json

from magister.llm import LLM
from magister.models import Proposal


class Analyst:
    def __init__(self, settings: dict, llm: LLM | None = None) -> None:
        llm_cfg = settings.get("llm", {})
        self.llm = llm or LLM(llm_cfg)
        self.max_proposals = int(llm_cfg.get("max_proposals", 3))

    def analyze(self, snapshot: list[dict]) -> list[Proposal]:
        prompt = self._build_prompt(snapshot)
        data = self.llm.propose(prompt)
        proposals: list[Proposal] = []
        for item in data[: self.max_proposals]:
            try:
                proposals.append(Proposal(**item))
            except Exception:
                continue
        return proposals

    def _build_prompt(self, snapshot: list[dict]) -> str:
        schema = {
            "symbol": "BTCUSDT",
            "side": "BUY or SELL",
            "quote_usdt": 10.0,
            "reference_price": 0.0,
            "conviction": 0.0,
            "thesis": "one sentence reason",
            "horizon": "1d",
        }
        return (
            "Market snapshot:\n"
            + json.dumps(snapshot, indent=2)
            + "\n\nPropose up to 3 small spot trades from the snapshot symbols. "
            + "Cap each quote_usdt at 15. Prefer the two majors. "
            + "Return only a JSON array of objects shaped like:\n"
            + json.dumps(schema)
        )
