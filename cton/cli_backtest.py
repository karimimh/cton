from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
from .binance_client import BinanceClient
from .backtest import backtest_symbols


def parse_args():
    p = argparse.ArgumentParser(description="RSI Divergence Backtester")
    p.add_argument('--timeframe', default='4h')
    p.add_argument('--days', type=int, default=365, help='Number of days back from now to test')
    p.add_argument('--limit-symbols', type=int, default=50, help='Limit number of symbols (USDC quote) to test')
    p.add_argument('--rsi-period', type=int, default=14)
    p.add_argument('--swing-k', type=int, default=2)
    p.add_argument('--stop-pct', type=float, default=5.0)
    p.add_argument('--target-pct', type=float, default=10.0)
    return p.parse_args()


def main():  # pragma: no cover
    args = parse_args()
    client = BinanceClient()
    symbols = client.fetch_symbols_usdc(limit=args.limit_symbols)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)
    results = backtest_symbols(client, symbols, args.timeframe, int(start.timestamp()*1000), int(end.timestamp()*1000),
                               rsi_period=args.rsi_period, swing_k=args.swing_k,
                               stop_pct=args.stop_pct, target_pct=args.target_pct)
    # Print summary
    print(f"Backtest timeframe={args.timeframe} period={args.rsi_period} swing_k={args.swing_k} stop={args.stop_pct}% target={args.target_pct}%")
    aggregate_net = 0.0
    aggregate_closed = 0
    aggregate_wins = 0
    aggregate_trades = 0
    for sym, data in results.items():
        if 'error' in data:
            print(f"{sym}: ERROR {data['error']}")
            continue
        summary = data['summary']
        aggregate_net += summary['net_pct']
        aggregate_closed += summary['closed_trades']
        aggregate_wins += summary['wins']
        aggregate_trades += summary['total_trades']
        print(f"{sym}: trades={summary['total_trades']} closed={summary['closed_trades']} win_rate={summary['win_rate']:.1f}% net_pct={summary['net_pct']:.2f}")
    if aggregate_closed:
        overall_wr = aggregate_wins / aggregate_closed * 100
    else:
        overall_wr = 0.0
    print("----")
    print(f"TOTAL symbols={len(results)} trades={aggregate_trades} closed={aggregate_closed} overall_win_rate={overall_wr:.1f}% aggregate_net_pct={aggregate_net:.2f}")


if __name__ == '__main__':  # pragma: no cover
    main()
