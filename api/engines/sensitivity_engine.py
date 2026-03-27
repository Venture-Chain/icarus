"""
Sensitivity analysis engine.
Adapted from Venture Chain financial modeling toolkit.
One-way, two-way, tornado, scenario, breakeven, Monte Carlo.
"""
from collections.abc import Callable

import numpy as np
import pandas as pd


class SensitivityEngine:
    def tornado(self, variables: dict, output_func: Callable) -> pd.DataFrame:
        """Tornado analysis: rank variables by impact on output."""
        base_output = output_func()
        rows = []

        for name, info in variables.items():
            info["update_func"](info["low"])
            low_out = output_func()
            info["update_func"](info["high"])
            high_out = output_func()
            info["update_func"](info["base"])

            impact = abs(high_out - low_out)
            rows.append({
                "variable": name,
                "low_output": low_out,
                "high_output": high_out,
                "impact": impact,
                "impact_pct": impact / base_output * 100 if base_output else 0,
            })

        df = pd.DataFrame(rows).sort_values("impact", ascending=False)
        return df

    def monte_carlo(
        self,
        distributions: dict,
        output_func: Callable,
        iterations: int = 5000,
    ) -> dict:
        """Monte Carlo simulation with configurable distributions."""
        results = []
        for _ in range(iterations):
            sample = {}
            for name, dist in distributions.items():
                sample[name] = dist()
            results.append(output_func(**sample))

        arr = np.array(results)
        return {
            "mean": float(np.mean(arr)),
            "median": float(np.median(arr)),
            "std": float(np.std(arr)),
            "var_95": float(np.percentile(arr, 5)),
            "var_99": float(np.percentile(arr, 1)),
            "p10": float(np.percentile(arr, 10)),
            "p90": float(np.percentile(arr, 90)),
            "results": results,
        }

    def breakeven(
        self,
        update_func: Callable,
        output_func: Callable,
        target: float,
        low: float,
        high: float,
        tolerance: float = 0.01,
    ) -> float:
        """Binary search for breakeven value."""
        while (high - low) > tolerance:
            mid = (low + high) / 2
            update_func(mid)
            output = output_func()
            if abs(output - target) < tolerance:
                return mid
            elif output < target:
                low = mid
            else:
                high = mid
        return (low + high) / 2
