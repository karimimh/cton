# CTON Architecture

## Overview
CTON periodically scans Binance spot market pairs ending with USDC across multiple higher timeframe intervals (1M,1w,1d,4h) to detect RSI divergences and notify via email.

## Components
- Symbol Discovery: Queries Binance `/api/v3/exchangeInfo` and filters symbols.
- Market Data Fetcher: Pulls OHLCV (klines) per symbol & interval using `/api/v3/klines`.
- Indicator Engine: Computes RSI (Wilder) and caches intermediate gains/losses for efficiency.
- Swing Point Detector: Identifies swing highs/lows using a lookback-left/right window (fractal approach).
- Divergence Detector: Matches most recent confirmed price swing vs prior swing and compares RSI swings.
- Strategy Module: Orchestrates detection across timeframes and aggregates signals.
- Notifier: Formats and sends email via SMTP.
- Runner: CLI entrypoint; handles loop scheduling, error logging, backoff.

## Data Flow
1. Load config (.env + CLI flags)
2. Fetch symbol list
3. For each timeframe:
   a. For each symbol: fetch latest N klines (ensuring at least MIN_RSI_LOOKBACK + safety margin)
   b. Compute RSI series
   c. Detect swings (price + RSI)
   d. Evaluate divergence (bullish/bearish)
4. Collect confirmed signals for most recent fully closed candle
5. If signals: send email
6. Sleep (loop mode) or exit (once)

## Divergence Logic (Detailed)
Given two swing points S_prev and S_last of the same type (lows for bullish, highs for bearish):
- Price condition (bullish): close_last < close_prev
- RSI condition (bullish): rsi_last > rsi_prev
- Bearish inverse.
Confirmation: We only consider S_last once its candle is closed AND at least one subsequent candle has formed (to mitigate repaint). For 1M/1w this means waiting until the next period boundary.

## Swing Detection
Use a window k (e.g., 2): A swing high at index i if High[i] > High[i - j] and High[i] >= High[i + j] for j in 1..k. Symmetric for lows.

## Configuration Knobs
- RSI_PERIOD (default 14)
- SWING_K (default 2)
- MIN_RSI_LOOKBACK (>= 120 recommended for stability)
- MAX_CANDLES_FETCH (cap per request, default 500)
- TIMEFRAMES = ["1M","1w","1d","4h"] (Binance intervals: 1M=1month, 1w=1week, 1d=1day, 4h=4hour)

## Error Handling & Resilience
- HTTP timeouts enforced.
- Retry with exponential backoff (simple capped) for transient 5xx / network errors.
- Symbols causing repeated errors are skipped for that cycle.
- Failures during one symbol/timeframe do not abort entire run.

## Performance Considerations
- Parallel fetch (future enhancement) using asyncio or thread pool; initial version serial (simpler).
- Cache symbol list for session; refresh daily.
- Potential rate limit handling (Binance weight counters) – future.

## Security
- No API key required (public endpoints only).
- SMTP credentials stored in .env (not committed); encourage app-specific passwords.

## Extensibility
Add new strategies in `cton/strategies/` implementing a `collect_signals(symbol, klines_per_tf)` interface. Combine multiple strategies into a unified signal dispatch.

## Testing Strategy
- Unit test RSI calculation vs known values.
- Unit test swing detection edge cases.
- Unit test divergence logic with synthetic data.

## Future Ideas
- Telegram / Slack notifier plugins.
- Position sizing helper (not trade execution) with ATR-based stop suggestion.
- Additional indicators (MACD divergence, OBV confirmation).
- Basic web dashboard for recent signals.
