from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Sequence
from time import time
from .config import Config
from .binance_client import BinanceClient
from .indicators import rsi
from .divergence import find_latest_divergence


@dataclass
class OpenPosition:
    symbol: str
    direction: str  # long only currently
    entry_price: float
    quantity: float
    stop_price: float
    target_price: float
    entry_time: float


class TradingBot:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = BinanceClient(timeout=cfg.request_timeout, api_key=cfg.api_key, api_secret=cfg.api_secret)
        self.paper_mode = not (cfg.api_key and cfg.api_secret)
        self.capital = cfg.initial_capital
        self.open_positions: Dict[str, OpenPosition] = {}

    def fetch_symbols(self) -> List[str]:
        return self.client.fetch_symbols_usdc(limit=self.cfg.symbol_limit)

    def fetch_latest_klines(self, symbol: str, limit: int) -> List[List]:
        return self.client.fetch_klines(symbol, self.cfg.trade_timeframe, limit=limit)

    def scan_and_trade(self):
        symbols = self.fetch_symbols()
        for sym in symbols:
            if len(self.open_positions) >= self.cfg.max_open_trades:
                break
            if sym in self.open_positions:
                continue
            kl = self.fetch_latest_klines(sym, limit=min(self.cfg.max_candles_fetch, self.cfg.min_rsi_lookback + 50))
            closes = [float(k[4]) for k in kl]
            rsi_vals = rsi(closes, period=self.cfg.rsi_period)
            sig = find_latest_divergence(sym, self.cfg.trade_timeframe, closes, rsi_vals, k=self.cfg.swing_k)
            if not sig:
                continue
            if sig.kind == 'bearish' and not self.cfg.allow_shorts:
                continue
            # Setup trade (long only default)
            entry_price = closes[sig.candle_index] * (0.999 if sig.kind == 'bullish' else 1.001)
            alloc = self.capital * self.cfg.allocation_fraction
            if alloc <= 0:
                continue
            quantity = alloc / entry_price
            stop_price = entry_price * (1 - self.cfg.stop_pct/100) if sig.kind == 'bullish' else entry_price * (1 + self.cfg.stop_pct/100)
            target_price = entry_price * (1 + self.cfg.target_pct/100) if sig.kind == 'bullish' else entry_price * (1 - self.cfg.target_pct/100)
            filled = self._execute_order(sym, 'BUY' if sig.kind == 'bullish' else 'SELL', quantity)
            if not filled:
                continue
            self.capital -= alloc
            self.open_positions[sym] = OpenPosition(sym, 'long' if sig.kind == 'bullish' else 'short', entry_price, quantity, stop_price, target_price, time())
            print(f"Opened {sym} dir={sig.kind} qty={quantity:.4f} entry={entry_price:.6f}")
        # Manage open positions
        self._update_positions()

    def _execute_order(self, symbol: str, side: str, quantity: float) -> bool:
        if self.paper_mode:
            return True
        try:
            self.client.place_order_market(symbol, side, quantity)
            return True
        except Exception as e:  # noqa: BLE001
            print(f"Order failed {symbol} {e}")
            return False

    def _update_positions(self):
        to_close: List[str] = []
        for sym, pos in self.open_positions.items():
            price = self.client.get_price(sym)
            hit_target = price >= pos.target_price
            hit_stop = price <= pos.stop_price
            if hit_target or hit_stop:
                exit_price = pos.target_price if hit_target else pos.stop_price
                self._close_position(sym, exit_price, 'target' if hit_target else 'stop')
        for sym in to_close:
            self.open_positions.pop(sym, None)

    def _close_position(self, symbol: str, exit_price: float, reason: str):
        pos = self.open_positions.pop(symbol, None)
        if not pos:
            return
        pnl = (exit_price - pos.entry_price) * pos.quantity if pos.direction == 'long' else (pos.entry_price - exit_price) * pos.quantity
        if self.paper_mode:
            self.capital += pos.quantity * exit_price + pnl  # return capital + pnl (simplified)
        else:
            # In live mode capital tracking should reconcile account balances via API (not implemented here)
            pass
        print(f"Closed {symbol} reason={reason} exit={exit_price:.6f} pnl={pnl:.2f} capital={self.capital:.2f}")
