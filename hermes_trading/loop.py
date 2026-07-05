"""24/7 reliability loop — pulls data, evaluates strategy, paper trades, logs."""
from __future__ import annotations
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .adapters.price import fetch_price
from .adapters.onchain import fetch_onchain
from .adapters.news import fetch_news
from .adapters.macro import fetch_macro
from .reflect import maybe_reflect
from .score import score_trades


STATE_DIR = Path(__file__).parent.parent / "state"
TRADES_FILE = STATE_DIR / "trades.jsonl"
HEARTBEAT_FILE = STATE_DIR / "heartbeat.json"
STRATEGY_FILE = STATE_DIR / "strategy.yaml"


def load_strategy() -> dict:
    with STRATEGY_FILE.open() as f:
        return yaml.safe_load(f)


def save_strategy(strategy: dict) -> None:
    with STRATEGY_FILE.open("w") as f:
        yaml.safe_dump(strategy, f, sort_keys=False)


def load_trades() -> list[dict]:
    if not TRADES_FILE.exists():
        return []
    trades = []
    with TRADES_FILE.open() as f:
        for line in f:
            line = line.strip()
            if line:
                trades.append(json.loads(line))
    return trades


def append_trade(trade: dict) -> None:
    with TRADES_FILE.open("a") as f:
        f.write(json.dumps(trade) + "\n")


def write_heartbeat(data: dict) -> None:
    HEARTBEAT_FILE.write_text(json.dumps(data, indent=2))


class CircuitBreaker(Exception):
    """Raised when too many consecutive failures."""


async def fetch_with_retry(fetch_fn, name: str, max_retries: int = 3) -> dict:
    """Call an async fetch with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return await fetch_fn()
        except Exception as e:
            wait = 2 ** attempt
            print(f"[loop] {name} attempt {attempt + 1} failed: {e}, retry in {wait}s", flush=True)
            await asyncio.sleep(wait)
    raise RuntimeError(f"{name} failed after {max_retries} attempts")


async def run_loop(assets: list[str], goal: dict) -> None:
    """Main trading loop — runs every 60 seconds, iterating all assets."""
    consecutive_failures = 0
    strategy = load_strategy()

    while True:
        cycle_start = time.time()
        timestamp = datetime.utcnow().isoformat() + "Z"
        total_signal = None

        for asset in assets:
            # 1. Fetch data from all adapters
            try:
                price_data = await fetch_with_retry(lambda a=asset: fetch_price(a), "price")
                onchain_data = await fetch_with_retry(lambda a=asset: fetch_onchain(a), "onchain")
                news_data = await fetch_with_retry(lambda a=asset: fetch_news(a), "news")
                macro_data = await fetch_with_retry(lambda: fetch_macro(), "macro")
                consecutive_failures = 0
            except Exception as e:
                consecutive_failures += 1
                print(f"[loop] {asset} adapters failed ({consecutive_failures}/5): {e}", flush=True)
                if consecutive_failures >= 5:
                    raise CircuitBreaker("5 consecutive adapter failures")
                continue

            # 2. Evaluate strategy against current market state
            signal = evaluate_strategy(strategy, price_data, onchain_data, news_data, macro_data)

            # 3. Execute paper trade if signal fires
            if signal:
                trade = {
                    "timestamp": timestamp,
                    "asset": asset,
                    "signal": signal,
                    "strategy_version": strategy.get("version", "00"),
                    "entry_price": price_data.get("last", 0),
                    "status": "open",
                }
                append_trade(trade)
                print(f"[loop] Paper trade opened: {signal['action']} {asset} @ {trade['entry_price']}", flush=True)

            # 4. Close matching open trades
            trades = load_trades()
            for t in trades:
                if t.get("status") == "open" and t.get("asset") == asset:
                    close_price = price_data.get("last", 0)
                    t["exit_price"] = close_price
                    t["status"] = "closed"
                    t["pnl_pct"] = ((close_price - t["entry_price"]) / t["entry_price"]) * 100
                    print(f"[loop] Paper trade closed: {asset} {t['pnl_pct']:.2f}%", flush=True)

        # 5. Portfolio-level: score all trades
        all_trades = load_trades()
        score = score_trades(all_trades, goal)
        print(f"[loop] Portfolio score: {score:.3f}", flush=True)

        # 6. Reflection cycle
        reflection_result = maybe_reflect(all_trades, strategy, goal)
        if reflection_result:
            new_strategy, hypothesis = reflection_result
            save_strategy(new_strategy)
            print(f"[loop] Reflection: {hypothesis['change']}", flush=True)

        # 7. Heartbeat
        write_heartbeat({
            "timestamp": timestamp,
            "assets": assets,
            "open_trades": sum(1 for t in all_trades if t.get("status") == "open"),
            "total_trades": len(all_trades),
            "score": score,
            "strategy_version": strategy.get("version", "00"),
        })

        # 8. Sleep to maintain 60s cycle
        elapsed = time.time() - cycle_start
        await asyncio.sleep(max(0, 60 - elapsed))


def evaluate_strategy(strategy: dict, price: dict, onchain: dict, news: dict, macro: dict) -> dict | None:
    """
    Evaluate entry conditions from strategy.yaml.
    Returns signal dict or None.
    """
    entry = strategy.get("entry", {})
    indicator = entry.get("indicator", "rsi")
    threshold = entry.get("threshold", 30)
    direction = entry.get("direction", "long")

    # Get RSI from price data (simplified - would use actual RSI calc)
    rsi = price.get("rsi", 50)

    if direction == "long" and indicator == "rsi" and rsi <= threshold:
        return {"action": "buy", "indicator": indicator, "value": rsi, "threshold": threshold}
    return None