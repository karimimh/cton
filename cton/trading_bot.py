from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List
from time import time
from .config import Config
from .binance_client import BinanceClient
from .indicators import rsi
from .divergence import find_latest_divergence
from .notifier.email_notifier import send_email
import hashlib
import json


@dataclass
class OpenPosition:
    symbol: str
    direction: str  # 'long' or 'short'
    entry_price: float
    quantity: float
    stop_price: float
    target_price: float
    entry_time: float
    allocated: float  # capital allocated at entry (notional)


class TradingBot:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = BinanceClient(timeout=cfg.request_timeout, api_key=cfg.api_key, api_secret=cfg.api_secret)
        self.paper_mode = not (cfg.api_key and cfg.api_secret)
        self.capital = cfg.initial_capital
        self.open_positions = {}  # type: Dict[str, OpenPosition]
        self.realized_pnl = 0.0
        self._last_email_hash = None  # last sent email state hash

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
            quantity = alloc / entry_price if entry_price > 0 else 0
            stop_price = entry_price * (1 - self.cfg.stop_pct/100) if sig.kind == 'bullish' else entry_price * (1 + self.cfg.stop_pct/100)
            target_price = entry_price * (1 + self.cfg.target_pct/100) if sig.kind == 'bullish' else entry_price * (1 - self.cfg.target_pct/100)
            filled = self._execute_order(sym, 'BUY' if sig.kind == 'bullish' else 'SELL', quantity)
            if not filled:
                continue
            self.capital -= alloc
            direction = 'long' if sig.kind == 'bullish' else 'short'
            self.open_positions[sym] = OpenPosition(sym, direction, entry_price, quantity, stop_price, target_price, time(), alloc)
            print(f"Opened {sym} dir={direction} qty={quantity:.4f} entry={entry_price:.6f}")
            self._notify_trade('OPEN', sym, direction, entry_price, quantity, None, None, 'signal')
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
            # Return proceeds only; alloc already deducted
            self.capital += pos.quantity * exit_price
        # Track realized PnL separately
        self.realized_pnl += pnl
        print(f"Closed {symbol} reason={reason} exit={exit_price:.6f} pnl={pnl:.2f} capital={self.capital:.2f}")
        self._notify_trade('CLOSE', symbol, pos.direction, pos.entry_price, pos.quantity, exit_price, pnl, reason)

    # ---------------- Email Notification Helpers -----------------
    def _notify_trade(self, action: str, symbol: str, direction: str, entry_price: float, quantity: float,
                       exit_price: float | None, pnl: float | None, reason: str | None):
        try:
            subject, body = self._build_email(action, symbol, direction, entry_price, quantity, exit_price, pnl, reason)
            # Throttle: compute hash; if unchanged skip unless action is CLOSE (always important)
            state_repr = {
                'action': action,
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'quantity': quantity,
                'exit_price': exit_price,
                'pnl': pnl,
                'reason': reason,
                'open_positions': [
                    {'s': p.symbol, 'dir': p.direction, 'e': p.entry_price, 'q': p.quantity, 'st': p.stop_price, 'tg': p.target_price}
                    for p in sorted(self.open_positions.values(), key=lambda x: x.symbol)
                ],
                'realized': self.realized_pnl,
                'capital': self.capital,
            }
            digest = hashlib.sha256(json.dumps(state_repr, sort_keys=True).encode()).hexdigest()
            if action == 'OPEN' and self._last_email_hash == digest:
                return  # suppress duplicate opens with identical state
            self._last_email_hash = digest
            send_email(self.cfg.smtp_host, self.cfg.smtp_port, self.cfg.smtp_user, self.cfg.smtp_pass, self.cfg.starttls,
                       self.cfg.email_from, self.cfg.email_to, subject, body)
        except Exception as e:  # noqa: BLE001
            print(f"Email send failed: {e}")

    def _build_email(self, action: str, symbol: str, direction: str, entry_price: float, quantity: float,
                      exit_price: float | None, pnl: float | None, reason: str | None) -> tuple[str, str]:
        subject = f"CTON Trade {action} {symbol}"
        lines: List[str] = []
        lines.append(f"Action: {action}")
        lines.append(f"Symbol: {symbol}")
        lines.append(f"Direction: {direction}")
        lines.append(f"Entry: {entry_price:.6f} Qty: {quantity:.6f}")
        if exit_price is not None and pnl is not None:
            lines.append(f"Exit: {exit_price:.6f} PnL: {pnl:.2f} ({(pnl/(entry_price*quantity))*100 if entry_price*quantity>0 else 0:.2f}%) Reason: {reason}")
        lines.append("")
        lines.append("Open Positions:")
        if not self.open_positions:
            lines.append("  (none)")
        else:
            header = f"{'Symbol':<10} {'Dir':<5} {'Entry':>10} {'Current':>10} {'Qty':>10} {'UnrPnL$':>10} {'UnrPnL%':>9}"
            lines.append(header)
            total_unreal = 0.0
            for pos in self.open_positions.values():
                current_price = self.client.get_price(pos.symbol)
                if pos.direction == 'long':
                    unr = (current_price - pos.entry_price) * pos.quantity
                else:
                    unr = (pos.entry_price - current_price) * pos.quantity
                total_unreal += unr
                unr_pct = (unr / pos.allocated * 100) if pos.allocated else 0.0
                lines.append(f"{pos.symbol:<10} {pos.direction:<5} {pos.entry_price:>10.6f} {current_price:>10.6f} {pos.quantity:>10.4f} {unr:>10.2f} {unr_pct:>9.2f}")
            lines.append(f"Total Unrealized: {total_unreal:.2f}")
        equity_components = []
        for p in self.open_positions.values():
            current = self.client.get_price(p.symbol)
            if p.direction == 'long':
                equity_components.append((current - p.entry_price) * p.quantity)
            else:
                equity_components.append((p.entry_price - current) * p.quantity)
        equity = self.capital + sum(equity_components)
        lines.append("")
        lines.append(f"Realized PnL: {self.realized_pnl:.2f}")
        lines.append(f"Capital (free): {self.capital:.2f}")
        lines.append(f"Equity (approx): {equity:.2f}")
        body = "\n".join(lines)
        return subject, body
