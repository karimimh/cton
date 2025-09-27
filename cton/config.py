from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

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
        )
