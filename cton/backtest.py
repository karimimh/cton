from __future__ import annotations
from dataclasses import dataclass
from typing import List, Sequence, Dict, Any
from .indicators import rsi
from .divergence import find_divergences, DivergenceSignal


@dataclass
class Trade:
    symbol: str
    timeframe: str
    direction: str  # 'long' or 'short'
    entry_index: int
    entry_price: float
    stop_price: float
    target_price: float
    exit_index: int | None = None
    exit_price: float | None = None
    result: str | None = None  # 'target','stop','open'

    def pnl_pct(self) -> float | None:
        if self.exit_price is None:
            return None
        if self.direction == 'long':
            return (self.exit_price - self.entry_price) / self.entry_price * 100
        else:
            return (self.entry_price - self.exit_price) / self.entry_price * 100


def simulate_trades(symbol: str, timeframe: str, klines: Sequence[Sequence[Any]], rsi_period: int = 14, swing_k: int = 2,
                     stop_pct: float = 5.0, target_pct: float = 10.0) -> List[Trade]:
    """Simulate divergence-based trades over provided klines.

    Rules:
    - Bullish divergence: place buy limit just below (e.g. 0.1% below) close of divergence candle.
      We'll assume immediate fill at that price on next candle open if price trades there (simplified).
      Stop = 5% below entry, Target = 10% above entry.
    - Bearish divergence: mirror logic (sell/short) with stop 5% above, target 10% below.
    Simplifications:
    - Assume liquidity & fill.
    - No overlapping positions: skip new signal if position open.
    """
    closes = [float(k[4]) for k in klines]
    rsi_vals = rsi(closes, period=rsi_period)
    divergences: List[DivergenceSignal] = find_divergences(symbol, timeframe, closes, rsi_vals, k=swing_k)
    trades: List[Trade] = []
    open_trade: Trade | None = None
    # Index mapping: divergence.candle_index refers to swing candle; we enter next candle
    for div in divergences:
        if open_trade is not None:
            # Process existing open trade forward until this divergence candle index to see if it closed earlier
            open_trade = _advance_trade_until_index(open_trade, klines, target_first=True, up_to_index=div.candle_index)
            if open_trade.result is not None:
                trades.append(open_trade)
                open_trade = None
        if open_trade is not None:
            # Still open, skip opening new trade
            continue
        entry_candle_index = div.candle_index + 1
        if entry_candle_index >= len(closes):
            break
        prev_close = closes[div.candle_index]
        if div.kind == 'bullish':
            entry_price = prev_close * 0.999  # 0.1% below close
            stop_price = entry_price * (1 - stop_pct/100)
            target_price = entry_price * (1 + target_pct/100)
            direction = 'long'
        else:
            entry_price = prev_close * 1.001  # 0.1% above close for short entry limit
            stop_price = entry_price * (1 + stop_pct/100)
            target_price = entry_price * (1 - target_pct/100)
            direction = 'short'
        open_trade = Trade(symbol, timeframe, direction, entry_candle_index, entry_price, stop_price, target_price)
        # Attempt to resolve trade immediately if next candles already trigger exit
        open_trade = _advance_trade_until_index(open_trade, klines, target_first=True, up_to_index=None)
        if open_trade.result is not None:
            trades.append(open_trade)
            open_trade = None
    # Finalize any remaining open trade until end
    if open_trade is not None:
        open_trade = _advance_trade_until_index(open_trade, klines, target_first=True, up_to_index=None)
        trades.append(open_trade)
    return trades


def _advance_trade_until_index(trade: Trade, klines: Sequence[Sequence[Any]], target_first: bool, up_to_index: int | None) -> Trade:
    # Candle sequence: each kline: [open_time, open, high, low, close, volume, ...]
    for i in range(trade.entry_index, len(klines)):
        if up_to_index is not None and i > up_to_index:
            break
        k = klines[i]
        high = float(k[2])
        low = float(k[3])
        if trade.direction == 'long':
            hit_target = high >= trade.target_price
            hit_stop = low <= trade.stop_price
        else:
            hit_target = low <= trade.target_price
            hit_stop = high >= trade.stop_price
        if hit_target and hit_stop:
            # Ambiguous: assume target prioritized (configurable)
            if target_first:
                trade.exit_index = i
                trade.exit_price = trade.target_price
                trade.result = 'target'
            else:
                trade.exit_index = i
                trade.exit_price = trade.stop_price
                trade.result = 'stop'
            return trade
        elif hit_target:
            trade.exit_index = i
            trade.exit_price = trade.target_price
            trade.result = 'target'
            return trade
        elif hit_stop:
            trade.exit_index = i
            trade.exit_price = trade.stop_price
            trade.result = 'stop'
            return trade
    if up_to_index is None or trade.exit_index is None:
        # Stays open
        if trade.exit_index is None:
            trade.result = 'open'
    return trade


def summarize_trades(trades: Sequence[Trade]) -> Dict[str, Any]:
    closed = [t for t in trades if t.result in ('target','stop')]
    wins = [t for t in closed if t.result == 'target']
    losses = [t for t in closed if t.result == 'stop']
    open_trades = [t for t in trades if t.result == 'open']
    total_pct = 0.0
    for t in closed:
        pnl = t.pnl_pct()
        if pnl is not None:
            total_pct += pnl
    return {
        'total_trades': len(trades),
        'closed_trades': len(closed),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': (len(wins)/len(closed)*100) if closed else 0.0,
        'avg_pct_per_closed_trade': (total_pct/len(closed)) if closed else 0.0,
        'net_pct': total_pct,
        'open_trades': len(open_trades),
    }


def backtest_symbols(client, symbols: Sequence[str], timeframe: str, start_ms: int, end_ms: int, rsi_period: int = 14,
                     swing_k: int = 2, stop_pct: float = 5.0, target_pct: float = 10.0) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    for sym in symbols:
        try:
            kl = client.fetch_klines_range(sym, timeframe, start_ms, end_ms)
            if len(kl) < rsi_period + 10:
                continue
            trades = simulate_trades(sym, timeframe, kl, rsi_period=rsi_period, swing_k=swing_k,
                                     stop_pct=stop_pct, target_pct=target_pct)
            results[sym] = {
                'trades': trades,
                'summary': summarize_trades(trades)
            }
        except Exception as e:  # noqa: BLE001
            results[sym] = {'error': str(e)}
    return results
