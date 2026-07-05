"""Score trades against goal.yaml — returns [-1, +1]."""
from __future__ import annotations
import math
from typing import List


def score_trades(trades: List[dict], goal: dict) -> float:
    """
    Composite score in [-1, +1]:
    - Return component: realised return vs target_return_30d
    - Drawdown component: max drawdown vs max_drawdown
    - Sharpe component: realised Sharpe vs min_sharpe
    """
    if not trades:
        return 0.0

    closed = [t for t in trades if t.get("status") == "closed" and "pnl_pct" in t]
    if not closed:
        return 0.0

    # Returns
    returns = [t["pnl_pct"] / 100.0 for t in closed]
    avg_return = sum(returns) / len(returns)
    target = goal.get("target_return_30d", 0.10)
    return_score = min(avg_return / target, 1.0) if target > 0 else 0.0

    # Drawdown
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in returns:
        cumulative += r
        peak = max(peak, cumulative)
        dd = peak - cumulative
        max_dd = max(max_dd, dd)
    max_allowed_dd = goal.get("max_drawdown", 0.08)
    dd_score = 1.0 - min(max_dd / max_allowed_dd, 1.0) if max_allowed_dd > 0 else 0.0

    # Sharpe (simplified)
    if len(returns) > 1:
        mean_r = sum(returns) / len(returns)
        std_r = math.sqrt(sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1))
        sharpe = mean_r / std_r if std_r > 0 else 0.0
        min_sharpe = goal.get("min_sharpe", 1.2)
        sharpe_score = min(sharpe / min_sharpe, 1.0) if min_sharpe > 0 else 0.0
    else:
        sharpe_score = 0.0

    # Weighted composite
    composite = 0.5 * return_score + 0.3 * dd_score + 0.2 * sharpe_score

    # Floor at failure_below
    floor = goal.get("failure_below", -0.04)
    return max(composite, floor)