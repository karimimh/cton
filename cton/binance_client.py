from __future__ import annotations
import requests
from typing import Any

BASE_URL = "https://api.binance.com"

class BinanceClient:
    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{BASE_URL}{path}"
        r = requests.get(url, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def fetch_symbols_usdc(self, limit: int | None = None) -> list[str]:
        data = self._get("/api/v3/exchangeInfo")
        symbols = []
        for s in data["symbols"]:
            if s.get("status") != "TRADING":
                continue
            # We interpret requirement as pairs with USDC as quote (e.g. BTCUSDC)
            if s.get("quoteAsset") == "USDC":
                symbols.append(s["symbol"])
        if limit:
            symbols = symbols[:limit]
        return symbols

    def fetch_klines(self, symbol: str, interval: str, limit: int = 500) -> list[list[Any]]:
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        return self._get("/api/v3/klines", params=params)
