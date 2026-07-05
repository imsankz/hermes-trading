"""Price adapter — fetches OHLCV + indicators via yfinance (free)."""
from __future__ import annotations
import asyncio
import pandas as pd
import yfinance as yf

SCHEMA_VERSION = 1


def _is_multi(hist):
    """yfinance 1.5.1 returns MultiIndex columns for single tickers."""
    return isinstance(hist.columns, pd.MultiIndex)


async def fetch_price(asset: str) -> dict:
    """
    Returns:
    {
        "schema_version": 1,
        "asset": "IWDA.DE",
        "last": 123.45,
        "open": 122.0,
        "high": 124.0,
        "low": 121.0,
        "volume": 1000000,
        "rsi": 45.2,
        "timestamp": "2025-01-15T10:30:00Z"
    }
    """
    loop = asyncio.get_event_loop()
    
    def _fetch_sync():
        ticker = yf.Ticker(asset)
        hist = ticker.history(period="1mo", interval="1d")
        if hist.empty:
            raise RuntimeError(f"No data for {asset}")
        last_row = hist.iloc[-1]
        # Simple RSI calculation (14-period)
        multi = _is_multi(hist)
        close = hist["Close"][asset] if multi else hist["Close"]
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return {
            "schema_version": SCHEMA_VERSION,
            "asset": asset,
            "last": float(last_row[("Close", asset)]) if multi else float(last_row["Close"]),
            "open": float(last_row[("Open", asset)]) if multi else float(last_row["Open"]),
            "high": float(last_row[("High", asset)]) if multi else float(last_row["High"]),
            "low": float(last_row[("Low", asset)]) if multi else float(last_row["Low"]),
            "volume": int(last_row[("Volume", asset)]) if multi else int(last_row["Volume"]),
            "rsi": float(rsi.iloc[-1]) if not rsi.empty else 50.0,
            "timestamp": last_row.name.isoformat() + "Z",
        }
    
    return await loop.run_in_executor(None, _fetch_sync)