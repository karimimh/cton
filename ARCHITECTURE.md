# CTON Architecture

CTON is a small, layered Python package. The layers are a Binance REST client, pure indicator and signal functions, and three entry points that share them: the scanner, the backtester, and the trading bot.

## Modules

| Module | Responsibility |
|--------|----------------|
| `config.py` | Loads `.env` with `python-dotenv` and builds a frozen `Config` dataclass. SMTP and email values are required. Everything else has a default. |
| `binance_client.py` | Thin `requests` wrapper over Binance spot REST v3. It covers symbol discovery (`/api/v3/exchangeInfo`, `status == TRADING`, `quoteAsset == USDC`), latest klines, paginated historical klines (`fetch_klines_range`: 1000 per page, 0.2 s pause between pages), ticker price, and HMAC-SHA256 signed `MARKET` orders. HTTP errors are re-raised with Binance's error body. |
| `indicators.py` | RSI with Wilder smoothing. The output is aligned with the input, and values before the first full period are `NaN`. |
| `divergence.py` | `detect_swings` (fractal swing highs and lows on closes), `find_latest_divergence` (the most recent bullish or bearish signal), and `find_divergences` (every signal, in time order). |
| `strategies/rsi_divergence.py` | Runs RSI and the latest-divergence check for every symbol × timeframe. |
| `notifier/email_notifier.py` | Formats the signal digest and sends mail through `smtplib` with optional STARTTLS. |
| `runner.py` | Scanner CLI (`--once`, `--loop`, `--sleep-seconds`). |
| `backtest.py` | Two engines: `simulate_trades` / `backtest_symbols` (one position at a time per symbol, no timeout) and `portfolio_backtest` (multi-symbol capital allocation). The CLI uses the portfolio engine. |
| `cli_backtest.py` | Backtest CLI. Uses public endpoints only and does not read `.env`. |
| `trading_bot.py` | `TradingBot`: scan, open, monitor and close cycle, plus email notifications. |
| `runner_trading.py` | Bot CLI loop (`--sleep-seconds`). |

## Signal logic

**Swing detection.** With window `k`, index `i` is a swing high when `close[i] > close[i-j]` and `close[i] >= close[i+j]` for every `j` in `1..k`. Swing lows mirror this. A swing can only be identified once `k` candles exist after it.

**Divergence.** Take two consecutive swings of the same kind, `prev` and `last`:

- Bullish: `last.price < prev.price` and `last.rsi > prev.rsi`
- Bearish: `last.price > prev.price` and `last.rsi < prev.rsi`

`find_latest_divergence` checks only the final pair of lows and the final pair of highs. If both qualify, it returns the one with the later swing index.

## Scanner flow (`runner.py`)

1. `Config.load()` reads `.env`.
2. Fetch the USDC symbol list, capped by `SYMBOL_LIMIT` if set.
3. For each symbol and each interval in `TIMEFRAMES`, fetch `min(MAX_CANDLES_FETCH, MIN_RSI_LOOKBACK + 50)` klines. A failed fetch is printed and skipped. It does not stop the run.
4. Run the latest-divergence check on each series.
5. If there are any signals, send one email digest.
6. Exit, or in loop mode sleep `--sleep-seconds` and repeat.

## Portfolio backtest (`portfolio_backtest`)

1. For each symbol, download the full history for the requested window and compute every divergence.
2. Simulate each divergence on its own:
   - Enter at the swing close ×0.999 (long) or ×1.001 (short), starting on the next candle.
   - Exit on the first candle whose high or low touches the target or the stop. If one candle touches both, the target wins.
   - Otherwise exit at the close of candle `entry + max_hold_candles`.
3. Sort all candidate trades by entry time. Walk through them, and before each entry release capital from trades that have already exited.
4. Allocate `alloc_frac × current free capital` to each new trade, and skip candidates while `max_open` positions are held.
5. Report the executed trades, the final capital and the return percentage.

Modelling assumptions: limit fills are assumed at the computed entry price, and there are no fees or slippage. Entry happens one candle after the swing, while confirming the swing needs `k` candles, so results contain look-ahead bias. Treat the output as exploratory.

## Trading bot (`TradingBot.scan_and_trade`)

1. Paper mode is on unless both `BINANCE_API_KEY` and `BINANCE_API_SECRET` are set.
2. For each USDC symbol not already held, and while open positions are below `MAX_OPEN_TRADES`:
   - Fetch `TRADE_TIMEFRAME` klines and find the latest divergence. Bearish signals are skipped unless `ALLOW_SHORTS=true`.
   - Compute the entry price (swing close ±0.1%), the stop and target (`STOP_PCT`, `TARGET_PCT`), and the size (`ALLOCATION_FRACTION × free capital`).
   - Paper mode records the fill at the computed entry price. Live mode sends a signed `MARKET` order, so the real fill is at market. Then send an OPEN email.
3. For each open position, poll the ticker price. If it is at or beyond the target or the stop, close the position at that level, realise the PnL and send a CLOSE email.
4. Emails include an open-positions table with unrealised PnL, plus realised PnL, free capital and approximate equity. An OPEN email whose state hash matches the previous email is not sent.

State is held in memory only. Exits are not sent to the exchange in live mode (see the README's known limitations).

## Error handling

- Every HTTP call has a timeout (`REQUEST_TIMEOUT`).
- Kline fetch failures are isolated per symbol and timeframe. The backtester skips symbols whose download fails.
- Email failures are logged and do not crash the scanner or the bot loop.
- The bot loop catches and prints exceptions from each cycle, then keeps running.

## Extending

- **New strategy.** Add a module under `cton/strategies/` that takes `{symbol: {timeframe: klines}}` and returns signal objects, following `run_strategy`, then call it from a runner.
- **New notifier.** Add a module under `cton/notifier/` with a send function, and call it next to `send_email`.
