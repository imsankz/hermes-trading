"""Reflection cycle — deterministic fallback (pre-Hermes) and Hermes mode."""
from __future__ import annotations
import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any

from .score import score_trades

STATE_DIR = Path(__file__).parent.parent / "state"
STRATEGY_FILE = STATE_DIR / "strategy.yaml"
HISTORY_DIR = STATE_DIR / "history"


def load_strategy() -> dict:
    with STRATEGY_FILE.open() as f:
        return yaml.safe_load(f)


def save_strategy(strategy: dict) -> None:
    with STRATEGY_FILE.open("w") as f:
        yaml.safe_dump(strategy, f, sort_keys=False)


def archive_strategy(strategy: dict) -> None:
    """Save current version to history before bumping."""
    HISTORY_DIR.mkdir(exist_ok=True)
    version = strategy.get("version", "00")
    archive_path = HISTORY_DIR / f"v{version}.yaml"
    with archive_path.open("w") as f:
        yaml.safe_dump(strategy, f, sort_keys=False)


def bump_version(version: str) -> str:
    """Bump version like 01 -> 02, 09 -> 10."""
    try:
        num = int(version)
        return f"{num + 1:02d}"
    except ValueError:
        return "01"


def reflect_fallback(trades: list[dict], strategy: dict, goal: dict) -> tuple[dict, dict]:
    """
    Deterministic fallback reflection:
    - If realised return < target -> loosen entry.threshold by 2
    - If drawdown > max -> tighten stop_loss_pct by 0.2
    - Always changes exactly ONE variable.
    """
    new_strategy = dict(strategy)
    version = bump_version(strategy.get("version", "00"))
    new_strategy["version"] = version

    score = score_trades(trades, goal)
    realised_return = sum(t.get("pnl_pct", 0) for t in trades if t.get("status") == "closed") / 100
    target = goal.get("target_return_30d", 0.10)
    max_dd = goal.get("max_drawdown", 0.08)

    # Calculate max drawdown from trades
    cumulative = 0
    peak = 0
    max_drawdown = 0
    for t in trades:
        if t.get("status") == "closed":
            pnl = t.get("pnl_pct", 0) / 100
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_drawdown:
                max_drawdown = dd

    change = None
    if realised_return < target:
        # Loosen entry threshold (make it easier to enter)
        old_threshold = new_strategy["entry"]["threshold"]
        new_strategy["entry"]["threshold"] = max(10, old_threshold - 2)
        change = f"entry.threshold: {old_threshold} -> {new_strategy['entry']['threshold']} (loosened, return {realised_return:.1%} < target {target:.1%})"
    elif max_drawdown > max_dd:
        # Tighten stop loss
        old_sl = new_strategy["stop_loss_pct"]
        new_strategy["stop_loss_pct"] = round(old_sl + 0.2, 1)
        change = f"stop_loss_pct: {old_sl} -> {new_strategy['stop_loss_pct']} (tightened, drawdown {max_drawdown:.1%} > max {max_dd:.1%})"
    else:
        # Default: tighten stop loss slightly as conservative drift
        old_sl = new_strategy["stop_loss_pct"]
        new_strategy["stop_loss_pct"] = round(old_sl + 0.1, 1)
        change = f"stop_loss_pct: {old_sl} -> {new_strategy['stop_loss_pct']} (conservative drift)"

    hypothesis = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "mode": "fallback",
        "strategy_version": version,
        "change": change,
        "score_before": score,
        "trades_analyzed": len([t for t in trades if t.get("status") == "closed"]),
    }

    return new_strategy, hypothesis


def reflect_hermes(trades: list[dict], strategy: dict, goal: dict) -> tuple[dict, dict]:
    """
    Hermes reflection mode — calls `hermes` subprocess.
    Not implemented in scaffold; raises NotImplementedError.
    """
    raise NotImplementedError("Hermes reflection not yet implemented — use --fallback")


def maybe_reflect(trades: list[dict], strategy: dict, goal: dict, mode: str = "fallback") -> tuple[dict, dict] | None:
    """
    Returns (new_strategy, hypothesis) if reflection triggered, else None.
    Triggers every N closed trades (goal.reflection_every).
    """
    reflection_every = goal.get("reflection_every", 5)
    closed_trades = [t for t in trades if t.get("status") == "closed"]

    if len(closed_trades) == 0:
        return None
    if len(closed_trades) % reflection_every != 0:
        return None

    # Check if we already reflected on this batch (by version)
    last_reflected = strategy.get("last_reflected_trade", 0)
    if last_reflected >= len(closed_trades):
        return None

    if mode == "fallback":
        new_strategy, hypothesis = reflect_fallback(trades, strategy, goal)
    else:
        new_strategy, hypothesis = reflect_hermes(trades, strategy, goal)

    new_strategy["last_reflected_trade"] = len(closed_trades)
    archive_strategy(strategy)
    save_strategy(new_strategy)

    # Append hypothesis
    with (STATE_DIR / "hypotheses.jsonl").open("a") as f:
        f.write(json.dumps(hypothesis) + "\n")

    return new_strategy, hypothesis


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("--fallback", action="store_true", help="Run deterministic fallback reflection")
    parser.add_argument("--hermes", action="store_true", help="Run Hermes reflection (not implemented)")
    args = parser.parse_args()

    if not args.fallback and not args.hermes:
        parser.print_help()
        sys.exit(1)

    # Load state
    trades_file = STATE_DIR / "trades.jsonl"
    trades = []
    if trades_file.exists():
        with trades_file.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    trades.append(json.loads(line))

    strategy = load_strategy()
    goal_file = STATE_DIR / "goal.yaml"
    with goal_file.open() as f:
        goal = yaml.safe_load(f)

    mode = "fallback" if args.fallback else "hermes"
    result = maybe_reflect(trades, strategy, goal, mode=mode)

    if result:
        new_strategy, hypothesis = result
        print(f"Reflection applied: {hypothesis['change']}")
        print(f"New version: {new_strategy['version']}")
    else:
        print("No reflection triggered (not enough closed trades)")