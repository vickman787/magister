from __future__ import annotations

import os

import requests


class MarketData:
    def __init__(self) -> None:
        self.base_url = os.getenv("BINANCE_SPOT_BASE_URL", "https://api.binance.com")
        self.session = requests.Session()

    def price(self, symbol: str) -> float:
        payload = self._get("/api/v3/ticker/price", {"symbol": symbol})
        return float(payload["price"])

    def return_pct(self, symbol: str, interval: str = "4h", limit: int = 30) -> float:
        klines = self._get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
        if not klines:
            raise RuntimeError(f"no klines returned for {symbol}")
        open_price = float(klines[0][1])
        close_price = float(klines[-1][4])
        return round((close_price / open_price - 1.0) * 100.0, 4)

    def snapshot(self, symbols: list[str]) -> list[dict]:
        rows = []
        for symbol in symbols:
            try:
                rows.append(
                    {
                        "symbol": symbol,
                        "price": self.price(symbol),
                        "return_4h_pct": self.return_pct(symbol),
                    }
                )
            except Exception as exc:
                rows.append({"symbol": symbol, "error": str(exc)})
        return rows

    def _get(self, path: str, params: dict | None = None) -> dict:
        response = self.session.get(self.base_url + path, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
