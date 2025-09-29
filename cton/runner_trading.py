from __future__ import annotations
import argparse
import time
from datetime import datetime, timezone
from .config import Config
from .trading_bot import TradingBot


def run_loop(cfg: Config, sleep_seconds: int):  # pragma: no cover
    bot = TradingBot(cfg)
    print(f"Trading bot started paper_mode={bot.paper_mode} timeframe={cfg.trade_timeframe}")
    while True:
        try:
            bot.scan_and_trade()
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] {e}")
        print(f"Cycle complete {datetime.now(timezone.utc)} capital={bot.capital:.2f} open_positions={len(bot.open_positions)}")
        time.sleep(sleep_seconds)


def main():  # pragma: no cover
    parser = argparse.ArgumentParser(description="CTON Trading Bot")
    parser.add_argument('--sleep-seconds', type=int, default=900)
    args = parser.parse_args()
    cfg = Config.load()
    run_loop(cfg, args.sleep_seconds)


if __name__ == '__main__':  # pragma: no cover
    main()
