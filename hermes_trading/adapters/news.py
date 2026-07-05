"""News adapter — free public endpoints (no key = GNews/NewsAPI free tier)."""
from __future__ import annotations
import os
import httpx

SCHEMA_VERSION = 1


async def fetch_news(asset: str) -> dict:
    """
    Returns:
    {
        "schema_version": 1,
        "asset": "IWDA.DE",
        "articles": [
            {"title": "...", "sentiment": 0.2, "source": "...", "url": "..."}
        ],
        "aggregate_sentiment": 0.15
    }
    """
    api_key = os.getenv("NEWS_API_KEY")
    
    if not api_key:
        # Free fallback: simple mock for paper trading
        return {
            "schema_version": SCHEMA_VERSION,
            "asset": asset,
            "articles": [],
            "aggregate_sentiment": 0.0,
            "note": "NEWS_API_KEY not set — using neutral sentiment",
        }
    
    # Real implementation would call NewsAPI/GNews
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                "https://newsapi.org/v2/everything",
                params={"q": asset.replace(".DE", ""), "apiKey": api_key, "pageSize": 10},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            articles = data.get("articles", [])
            return {
                "schema_version": SCHEMA_VERSION,
                "asset": asset,
                "articles": articles,
                "aggregate_sentiment": 0.0,  # Would run NLP here
            }
        except Exception as e:
            return {
                "schema_version": SCHEMA_VERSION,
                "asset": asset,
                "articles": [],
                "aggregate_sentiment": 0.0,
                "error": str(e),
            }