# CTON (Crypto Trading Opportunity Notifier)

CTON scans Binance USDC trading pairs for technical setups and emails you when a strategy condition is met. The first implemented strategy detects RSI divergences (bullish or bearish) across multiple higher timeframes (Monthly, Weekly, Daily, 4H) so you can manually evaluate potential trades.

> Disclaimer: This tool is strictly for educational and notification purposes. It does NOT execute trades and is not financial advice.

## Goal
Provide timely email notifications when an RSI divergence occurs on any USDC pair across selected timeframes.

## Key Features (MVP)
- Discover all active Binance symbols whose quote (counter) asset is USDC.
- Fetch OHLCV candlesticks for 1M, 1w, 1d, 4h intervals.
- Compute RSI (period 14, Wilder smoothing).
- Detect bullish and bearish RSI divergences using recent swing points.
- Aggregate signals for the latest completed candle and send an email summary.
- Simple .env-based configuration (SMTP + runtime knobs).

## Planned Enhancements
See `TODO.md`.

## Stack
- Python 3.11+
- Standard library + `requests`, `python-dotenv`

## Project Structure
```
cton/
  cton/
    __init__.py
    config.py
    binance_client.py
    indicators.py
    divergence.py
    runner.py
    strategies/
      __init__.py
      rsi_divergence.py
    notifier/
      __init__.py
      email_notifier.py
  tests/
    test_indicators.py
  requirements.txt
  .env.example
  ARCHITECTURE.md
  TODO.md
```

## Configuration
Copy `.env.example` to `.env` and fill in values.

| Variable | Description |
|----------|-------------|
| SMTP_HOST | SMTP server hostname |
| SMTP_PORT | SMTP server port (e.g. 587) |
| SMTP_USER | SMTP auth username |
| SMTP_PASS | SMTP auth password / app password |
| EMAIL_FROM | From address |
| EMAIL_TO | Comma-separated list of recipients |
| STARTTLS | `true` to use STARTTLS, else `false` |
| MIN_RSI_LOOKBACK | Candles to look back for divergence swing points (default 120) |
| SYMBOL_LIMIT | Optional cap on number of symbols (debug) |
| REQUEST_TIMEOUT | Seconds HTTP timeout (default 10) |

## Running (One-Off Scan)
```
python -m cton.runner --once
```

## Running (Loop Mode)
Run continuously (default sleep 15 min between cycles):
```
python -m cton.runner --loop --sleep-seconds 900
```

## Email Output Example
Subject: `CTON 2025-09-27 12:00Z (6 signals)`

Body (sample):
```
Timeframes checked: 1M,1w,1d,4h
Bullish:
  BTCUSDC 1d bullish divergence (price lower low vs RSI higher low) confirmed at candle 2025-09-26
Bearish:
  ETHUSDC 4h bearish divergence (price higher high vs RSI lower high) confirmed at candle 2025-09-27 08:00
```

## Divergence Definition (Simplified)
- Bullish: Price forms a lower swing low while RSI forms a higher swing low.
- Bearish: Price forms a higher swing high while RSI forms a lower swing high.
We use recent swing points detected via a fractal window (configurable) and confirm only after candle close.

## Assumptions
- "Has USDC as the base asset" interpreted as pairs where USDC is the quote (e.g., BTCUSDC). Adjust by changing filtering logic if needed.

## Tests
```
pytest -q
```

## Contributing / Next Steps
Update `ARCHITECTURE.md` and `TODO.md` as strategy logic expands (e.g., add volume filters, trend filters, risk scoring).
