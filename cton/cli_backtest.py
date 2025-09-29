from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
from .binance_client import BinanceClient
from .backtest import portfolio_backtest


def parse_args():
    p = argparse.ArgumentParser(description="RSI Divergence Backtester")
    p.add_argument('--timeframe', default='4h')
    p.add_argument('--days', type=int, default=365, help='Number of days back from now to test')
    p.add_argument('--limit-symbols', type=int, default=50, help='Limit number of symbols (USDC quote) to test')
    p.add_argument('--rsi-period', type=int, default=14)
    p.add_argument('--swing-k', type=int, default=2)
    p.add_argument('--stop-pct', type=float, default=5.0)
    p.add_argument('--target-pct', type=float, default=10.0)
    p.add_argument('--initial-capital', type=float, default=1000.0)
    p.add_argument('--alloc-frac', type=float, default=0.25, help='Fraction of current capital per new trade (e.g. 0.25)')
    p.add_argument('--max-open', type=int, default=4)
    p.add_argument('--max-hold-candles', type=int, default=30, help='Max candles to hold a position before timeout exit')
    return p.parse_args()


def main():  # pragma: no cover
    args = parse_args()
    client = BinanceClient()
    print("Fetching exchangeInfo...")
    symbols = client.fetch_symbols_usdc(limit=args.limit_symbols)
    print(f"Fetched {len(symbols)} symbols with USDC quote.")
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)
    results = portfolio_backtest(
        client,
        symbols,
        args.timeframe,
        int(start.timestamp()*1000),
        int(end.timestamp()*1000),
        initial_capital=args.initial_capital,
        capital_fraction_per_trade=args.alloc_frac,
        max_open_trades=args.max_open,
        rsi_period=args.rsi_period,
        swing_k=args.swing_k,
        stop_pct=args.stop_pct,
        target_pct=args.target_pct,
        max_hold_candles=args.max_hold_candles,
    )
    print(f"Portfolio Backtest timeframe={args.timeframe} capital={args.initial_capital} alloc_frac={args.alloc_frac} max_open={args.max_open}")
    print(f"Symbols tested: {results['symbols_tested']} Divergence candidates: {results['candidates']} Executed trades: {results['executed']}")
    print("Trades (chronological):")
    header = f"{'Symbol':<12} {'Dir':<5} {'EntryTime':<13} {'ExitTime':<13} {'Entry':>10} {'Exit':>10} {'Result':<8} {'Hold':>5} {'Alloc$':>10} {'PnL$':>10} {'PnL%':>7}"
    print(header)
    print('-'*len(header))
    for t in results['trades']:
        pnl_val = t.pnl_value()
        pnl_pct = t.pnl_pct_on_alloc()
        print(f"{t.symbol:<12} {t.direction:<5} {t.entry_time:<13} {t.exit_time:<13} {t.entry_price:>10.5f} {t.exit_price:>10.5f} {t.result:<8} {t.holding_candles():>5} {t.capital_alloc:>10.2f} {pnl_val:>10.2f} {pnl_pct:>7.2f}")
    print("----")
    print(f"Final Capital: {results['final_capital']:.2f}  Return: {results['return_pct']:.2f}%")


if __name__ == '__main__':  # pragma: no cover
    main()
