from __future__ import annotations
import argparse
import time
from datetime import datetime, timezone
from .config import Config
from .binance_client import BinanceClient
from .strategies.rsi_divergence import run_strategy
from .notifier.email_notifier import format_email, send_email


def run_once(cfg: Config) -> int:
    client = BinanceClient(timeout=cfg.request_timeout)
    symbols = client.fetch_symbols_usdc(limit=cfg.symbol_limit)
    klines_by_symbol_and_tf: dict[str, dict[str, list[list]]] = {}

    for symbol in symbols:
        klines_by_symbol_and_tf[symbol] = {}
        for tf in cfg.timeframes:
            try:
                kl = client.fetch_klines(symbol, tf, limit=min(cfg.max_candles_fetch, cfg.min_rsi_lookback + 50))
                klines_by_symbol_and_tf[symbol][tf] = kl
            except Exception as e:  # noqa: BLE001
                # Basic logging; improve later
                print(f"Error fetching {symbol} {tf}: {e}")
    signals = run_strategy(symbols, klines_by_symbol_and_tf, cfg.rsi_period, cfg.swing_k)
    if signals:
        subject, body = format_email(signals)
        try:
            send_email(cfg.smtp_host, cfg.smtp_port, cfg.smtp_user, cfg.smtp_pass, cfg.starttls, cfg.email_from, cfg.email_to, subject, body)
            print(f"Sent email with {len(signals)} signals at {datetime.now(timezone.utc)}")
        except Exception as e:  # noqa: BLE001
            print(f"Failed to send email: {e}")
    else:
        print("No signals this run.")
    return len(signals)


def main():
    parser = argparse.ArgumentParser(description="CTON Runner")
    parser.add_argument('--once', action='store_true', help='Run a single scan then exit')
    parser.add_argument('--loop', action='store_true', help='Run continuously')
    parser.add_argument('--sleep-seconds', type=int, default=900, help='Sleep interval between scans in loop mode')
    args = parser.parse_args()

    cfg = Config.load()

    if args.once and args.loop:
        parser.error('Choose either --once or --loop')

    if args.once or not args.loop:
        run_once(cfg)
    else:
        while True:
            run_once(cfg)
            time.sleep(args.sleep_seconds)


if __name__ == '__main__':  # pragma: no cover
    main()
