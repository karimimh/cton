from __future__ import annotations
import os
from dataclasses import dataclass
try:  # pragma: no cover - optional dependency guard
    from dotenv import load_dotenv  # type: ignore
except Exception:  # noqa: BLE001
    def load_dotenv():  # type: ignore
        return False

load_dotenv()

@dataclass(frozen=True)
class Config:
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    email_from: str
    email_to: list[str]
    starttls: bool

    rsi_period: int = 14
    swing_k: int = 2
    min_rsi_lookback: int = 120
    symbol_limit: int | None = None
    request_timeout: int = 10
    max_candles_fetch: int = 500
    timeframes: tuple[str, ...] = ("1M", "1w", "1d", "4h")
    # Trading (live/paper) parameters
    trade_timeframe: str = "4h"
    initial_capital: float = 1000.0  # only used for paper mode capital tracking
    allocation_fraction: float = 0.25
    max_open_trades: int = 4
    stop_pct: float = 5.0
    target_pct: float = 10.0
    max_hold_candles: int = 30
    allow_shorts: bool = False  # spot trading cannot short without margin
    api_key: str | None = None
    api_secret: str | None = None

    @staticmethod
    def load() -> "Config":
        def req(key: str) -> str:
            v = os.getenv(key)
            if not v:
                raise ValueError(f"Missing required env var {key}")
            return v
        email_to_raw = req("EMAIL_TO")
        return Config(
            smtp_host=req("SMTP_HOST"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=req("SMTP_USER"),
            smtp_pass=req("SMTP_PASS"),
            email_from=req("EMAIL_FROM"),
            email_to=[e.strip() for e in email_to_raw.split(",") if e.strip()],
            starttls=os.getenv("STARTTLS", "true").lower() == "true",
            rsi_period=int(os.getenv("RSI_PERIOD", "14")),
            swing_k=int(os.getenv("SWING_K", "2")),
            min_rsi_lookback=int(os.getenv("MIN_RSI_LOOKBACK", "120")),
            symbol_limit=(lambda v: int(v) if v and v.strip() else None)(os.getenv("SYMBOL_LIMIT")),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "10")),
            max_candles_fetch=int(os.getenv("MAX_CANDLES_FETCH", "500")),
            timeframes=tuple(os.getenv("TIMEFRAMES", "1M,1w,1d,4h").split(",")),
            trade_timeframe=os.getenv("TRADE_TIMEFRAME", "4h"),
            initial_capital=float(os.getenv("INITIAL_CAPITAL", "1000")),
            allocation_fraction=float(os.getenv("ALLOCATION_FRACTION", "0.25")),
            max_open_trades=int(os.getenv("MAX_OPEN_TRADES", "4")),
            stop_pct=float(os.getenv("STOP_PCT", "5")),
            target_pct=float(os.getenv("TARGET_PCT", "10")),
            max_hold_candles=int(os.getenv("MAX_HOLD_CANDLES", "30")),
            allow_shorts=os.getenv("ALLOW_SHORTS", "false").lower() == "true",
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_API_SECRET"),
        )
