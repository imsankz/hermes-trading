"""Entrypoint — parses asset from goal.yaml, starts the trading loop."""
from __future__ import annotations
import argparse
import asyncio
import sys
from pathlib import Path

import yaml

from .loop import run_loop


def load_goal(goal_path: Path) -> dict:
    with goal_path.open() as f:
        return yaml.safe_load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="Hermes Trading Worker")
    parser.add_argument("--asset", type=str, help="Override asset from goal.yaml")
    args = parser.parse_args()

    goal_path = Path(__file__).parent.parent / "state" / "goal.yaml"
    goal = load_goal(goal_path)
    assets = goal.get("assets", [goal.get("asset", "VWCE.DE")])

    print(f"[hermes-trading] Starting worker for {len(assets)} assets: {', '.join(assets)}", flush=True)
    try:
        asyncio.run(run_loop(assets, goal))
    except KeyboardInterrupt:
        print("\n[hermes-trading] Shutdown requested")
    return 0


if __name__ == "__main__":
    sys.exit(main())