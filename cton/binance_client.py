from __future__ import annotations
import requests
from typing import Any, List
import time

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

    def fetch_klines_range(self, symbol: str, interval: str, start_ms: int, end_ms: int, limit: int = 1000, sleep: float = 0.2) -> List[list[Any]]:
        """Fetch klines for a symbol/interval covering [start_ms, end_ms] inclusive.

        Binance returns up to 1000 candles per call. We paginate by advancing startTime to the
        open time of the last returned kline + 1 ms until we exceed end_ms.
        """
        all_kl: List[list[Any]] = []
        current_start = start_ms
        while current_start <= end_ms:
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
                "startTime": current_start,
                "endTime": end_ms,
            }
            batch = self._get("/api/v3/klines", params=params)
            if not batch:
                break
            all_kl.extend(batch)
            last_open = batch[-1][0]
            # Prevent infinite loop if API returns same last candle repeatedly
            if last_open == current_start:
                break
            current_start = last_open + 1
            # Rate limit courtesy pause
            if sleep:
                time.sleep(sleep)
            # Safety: stop if we already passed end
            if last_open >= end_ms:
                break
        return all_kl
