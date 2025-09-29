from __future__ import annotations
from dataclasses import dataclass
from typing import List, Sequence, Dict, Any, Tuple
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


# ----------------- Portfolio Backtest (multi-symbol capital allocation) -----------------

@dataclass
class PortfolioTrade:
    symbol: str
    timeframe: str
    direction: str  # 'long' or 'short'
    entry_index: int
    exit_index: int
    entry_time: int
    exit_time: int
    entry_price: float
    exit_price: float
    result: str  # 'target','stop','timeout'
    quantity: float
    capital_alloc: float

    def holding_candles(self) -> int:
        return self.exit_index - self.entry_index

    def pnl_value(self) -> float:
        if self.direction == 'long':
            return (self.exit_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.exit_price) * self.quantity

    def pnl_pct_on_alloc(self) -> float:
        return self.pnl_value() / self.capital_alloc * 100 if self.capital_alloc else 0.0


def _simulate_single_portfolio_trade(symbol: str, timeframe: str, klines: Sequence[Sequence[Any]], divergence: DivergenceSignal,
                                     stop_pct: float, target_pct: float, max_hold_candles: int) -> Tuple[int, int, int, int, float, float, str]:
    """Return (entry_index, exit_index, entry_price, exit_price, result) for a single divergence-based trade.

    Entry assumed at next candle after divergence close with 0.1% improvement.
    Exit on stop/target first touch (target prioritized if both in same candle) or timeout after max_hold_candles.
    """
    entry_index = divergence.candle_index + 1
    if entry_index >= len(klines):
        raise ValueError("Entry index beyond klines length")
    prev_close = float(klines[divergence.candle_index][4])
    if divergence.kind == 'bullish':
        entry_price = prev_close * 0.999
        stop_price = entry_price * (1 - stop_pct / 100)
        target_price = entry_price * (1 + target_pct / 100)
        long = True
    else:
        entry_price = prev_close * 1.001
        stop_price = entry_price * (1 + stop_pct / 100)
        target_price = entry_price * (1 - target_pct / 100)
        long = False

    exit_index = len(klines) - 1
    exit_price = float(klines[exit_index][4])
    result = 'timeout'
    last_allowed = min(len(klines) - 1, entry_index + max_hold_candles)
    for i in range(entry_index, last_allowed + 1):
        k = klines[i]
        high = float(k[2])
        low = float(k[3])
        if long:
            hit_target = high >= target_price
            hit_stop = low <= stop_price
        else:
            hit_target = low <= target_price
            hit_stop = high >= stop_price
        if hit_target and hit_stop:
            # prioritize target
            exit_index = i
            exit_price = target_price
            result = 'target'
            break
        elif hit_target:
            exit_index = i
            exit_price = target_price
            result = 'target'
            break
        elif hit_stop:
            exit_index = i
            exit_price = stop_price
            result = 'stop'
            break
        # timeout condition after loop end if not broken
    if result == 'timeout':
        # exit at close price of last_allowed candle
        exit_index = last_allowed
        exit_price = float(klines[exit_index][4])
    entry_time = int(klines[entry_index][0])
    exit_time = int(klines[exit_index][0])
    return entry_index, exit_index, entry_time, exit_time, entry_price, exit_price, result


def portfolio_backtest(client, symbols: Sequence[str], timeframe: str, start_ms: int, end_ms: int,
                        initial_capital: float = 1000.0, capital_fraction_per_trade: float = 0.25,
                        max_open_trades: int = 4, rsi_period: int = 14, swing_k: int = 2,
                        stop_pct: float = 5.0, target_pct: float = 10.0, max_hold_candles: int = 30) -> Dict[str, Any]:
    """Run a portfolio-level backtest across all symbols chronologically.

    Returns dict with trades list and final capital.
    """
    # Collect divergences per symbol with associated trade simulation precomputed
    symbol_klines: Dict[str, List[List[Any]]] = {}
    candidate_trades: List[Dict[str, Any]] = []

    for sym in symbols:
        try:
            kl = client.fetch_klines_range(sym, timeframe, start_ms, end_ms)
            if len(kl) < rsi_period + 10:
                continue
            symbol_klines[sym] = kl
            closes = [float(k[4]) for k in kl]
            rsi_vals = rsi(closes, period=rsi_period)
            divergences = find_divergences(sym, timeframe, closes, rsi_vals, k=swing_k)
            for div in divergences:
                try:
                    (entry_idx, exit_idx, entry_time, exit_time, entry_price, exit_price, result) = _simulate_single_portfolio_trade(
                        sym, timeframe, kl, div, stop_pct, target_pct, max_hold_candles
                    )
                    candidate_trades.append({
                        'symbol': sym,
                        'timeframe': timeframe,
                        'direction': 'long' if div.kind == 'bullish' else 'short',
                        'entry_index': entry_idx,
                        'exit_index': exit_idx,
                        'entry_time': entry_time,
                        'exit_time': exit_time,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'result': result,
                    })
                except ValueError:
                    continue
        except Exception:  # noqa: BLE001
            continue

    # Sort by entry_time chronologically
    candidate_trades.sort(key=lambda d: d['entry_time'])

    current_capital = initial_capital
    open_positions: List[PortfolioTrade] = []
    executed_trades: List[PortfolioTrade] = []

    def close_due_trades(up_to_time: int):
        nonlocal current_capital, open_positions, executed_trades
        still_open: List[PortfolioTrade] = []
        for t in open_positions:
            if t.exit_time <= up_to_time:
                # Realize PnL
                current_capital += t.capital_alloc + t.pnl_value()
                executed_trades.append(t)
            else:
                still_open.append(t)
        open_positions = still_open

    for cand in candidate_trades:
        # First close trades that have exited by this entry time
        close_due_trades(cand['entry_time'])
        if len(open_positions) >= max_open_trades:
            continue  # cannot add new trade
        alloc = current_capital * capital_fraction_per_trade
        if alloc <= 0:
            continue
        quantity = alloc / cand['entry_price'] if cand['entry_price'] > 0 else 0
        pt = PortfolioTrade(
            symbol=cand['symbol'],
            timeframe=cand['timeframe'],
            direction=cand['direction'],
            entry_index=cand['entry_index'],
            exit_index=cand['exit_index'],
            entry_time=cand['entry_time'],
            exit_time=cand['exit_time'],
            entry_price=cand['entry_price'],
            exit_price=cand['exit_price'],
            result=cand['result'],
            quantity=quantity,
            capital_alloc=alloc,
        )
        current_capital -= alloc  # allocate capital
        open_positions.append(pt)

    # Close any remaining open trades at the very end (use max exit time among them)
    if open_positions:
        final_time = max(t.exit_time for t in open_positions)
        close_due_trades(final_time)

    final_capital = current_capital
    total_return_pct = (final_capital - initial_capital) / initial_capital * 100 if initial_capital else 0.0
    executed_trades.sort(key=lambda t: t.entry_time)
    return {
        'trades': executed_trades,
        'final_capital': final_capital,
        'start_capital': initial_capital,
        'return_pct': total_return_pct,
        'symbols_tested': len(symbol_klines),
        'candidates': len(candidate_trades),
        'executed': len(executed_trades),
    }


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
        print(f"Backtesting {sym}...")
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
