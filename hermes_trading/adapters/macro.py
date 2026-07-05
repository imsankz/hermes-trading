"""Macro adapter — free public data (FRED, ECB, etc.)."""
from __future__ import annotations
import os
import httpx

SCHEMA_VERSION = 1


async def fetch_macro() -> dict:
    """
    Returns:
    {
        "schema_version": 1,
        "data": {
            "eur_usd": 1.08,
            "euribor_3m": 3.65,
            "cpi_eu": 2.4,
            "ecb_rate": 4.5
        },
        "timestamp": "2025-01-15T10:30:00Z"
    }
    """
    fred_key = os.getenv("FRED_API_KEY")
    
    if not fred_key:
        return {
            "schema_version": SCHEMA_VERSION,
            "data": {
                "eur_usd": 1.08,
                "euribor_3m": 3.65,
                "cpi_eu": 2.4,
                "ecb_rate": 4.5,
            },
            "timestamp": "2025-01-15T10:30:00Z",
            "note": "FRED_API_KEY not set — using placeholder macro data",
        }
    
    # Real implementation would fetch from FRED
    return {
        "schema_version": SCHEMA_VERSION,
        "data": {},
        "timestamp": "2025-01-15T10:30:00Z",
    }