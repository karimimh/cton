# TODO / Backlog

## MVP
- [ ] Implement config loader (`config.py`)
- [ ] Implement Binance client for symbols & klines (`binance_client.py`)
- [ ] Implement RSI indicator (`indicators.py`)
- [ ] Implement swing point detection (`divergence.py` or separate module)
- [ ] Implement divergence detection logic
- [ ] Implement strategy wrapper (`strategies/rsi_divergence.py`)
- [ ] Implement email notifier (`notifier/email_notifier.py`)
- [ ] Implement CLI runner (`runner.py`)
- [ ] Add environment example `.env.example`
- [ ] Add tests (RSI, swings, divergence)
- [ ] Wire everything together and manual dry run

## Post-MVP
- [ ] Retry/backoff logic & logging polish
- [ ] Parallelize data fetches (thread or asyncio)
- [ ] Add caching layer for candles
- [ ] Add CLI filter: specific symbols/timeframes
- [ ] Telegram notifier plugin
- [ ] Slack notifier plugin
- [ ] Dockerfile
- [ ] CI pipeline (lint + tests)
- [ ] Pre-commit hooks (black, ruff, mypy)
- [ ] Configurable RSI period & swing window via CLI
- [ ] Combine multiple divergence types (MACD, OBV)
- [ ] Persist last sent signals to avoid duplication
- [ ] Web dashboard (FastAPI) for recent signals

## Nice to Have
- [ ] Rate limit awareness (Binance headers)
- [ ] Historical backtest script
- [ ] Alert severity scoring
- [ ] HTML formatted email with mini charts
- [ ] Unit tests for notifier
- [ ] Integration test using recorded fixtures
