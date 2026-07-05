"""On-chain adapter — placeholder for crypto, returns empty for stocks/ETFs."""
from __future__ import annotations

SCHEMA_VERSION = 1


async def fetch_onchain(asset: str) -> dict:
    """
    Returns empty for non-crypto assets.
    For crypto, would fetch from Glassnode/CoinMetrics/etc.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "asset": asset,
        "data": {},
        "note": "On-chain data not applicable for stocks/ETFs",
    }