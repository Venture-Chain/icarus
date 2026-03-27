"""
Sensitivity analysis engine.
One-way, two-way, tornado, scenario, breakeven, Monte Carlo.
Integrated with backtest and valuation engines.
"""
import logging
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

log = logging.getLogger("icarus.sensitivity")


@dataclass
class ScenarioResult:
    name: str
    probability: float
    output: float
    variables: dict


class SensitivityEngine:
    """Multi-method sensitivity analysis for strategies and valuations."""

    def one_way(
        self,
        variable_name: str,
        base_value: float,
        range_pct: float,
        steps: int,
        update_func: Callable,
        output_func: Callable,
    ) -> pd.DataFrame:
        """Test one variable across a range, measure output impact."""
        min_val = base_value * (1 - range_pct)
        max_val = base_value * (1 + range_pct)
        test_values = np.linspace(min_val, max_val, steps)
        base_output = output_func()

        rows = []
        for val in test_values:
            update_func(val)
            output = output_func()
            rows.append({
                "variable": variable_name,
                "value": float(val),
                "pct_change": (val - base_value) / base_value * 100,
                "output": float(output),
                "output_change": float(output - base_output),
                "output_change_pct": float((output - base_output) / base_output * 100) if base_output else 0,
            })

        update_func(base_value)
        return pd.DataFrame(rows)

    def two_way(
        self,
        var1_name: str,
        var1_values: list[float],
        var1_update: Callable,
        var2_name: str,
        var2_values: list[float],
        var2_update: Callable,
        output_func: Callable,
        var1_base: float | None = None,
        var2_base: float | None = None,
    ) -> pd.DataFrame:
        """Two-way data table: test all combinations of two variables."""
        results = np.zeros((len(var1_values), len(var2_values)))

        for i, v1 in enumerate(var1_values):
            for j, v2 in enumerate(var2_values):
                var1_update(v1)
                var2_update(v2)
                results[i, j] = output_func()

        # Reset to base
        if var1_base is not None:
            var1_update(var1_base)
        if var2_base is not None:
            var2_update(var2_base)

        df = pd.DataFrame(
            results,
            index=pd.Index(var1_values, name=var1_name),
            columns=pd.Index(var2_values, name=var2_name),
        )
        return df

    def tornado(self, variables: dict, output_func: Callable) -> pd.DataFrame:
        """
        Tornado analysis: rank variables by impact on output.

        variables format: {
            "name": {"base": x, "low": y, "high": z, "update_func": callable}
        }
        """
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
                "base_value": info["base"],
                "low_value": info["low"],
                "high_value": info["high"],
                "low_output": float(low_out),
                "high_output": float(high_out),
                "low_delta": float(low_out - base_output),
                "high_delta": float(high_out - base_output),
                "impact": float(impact),
                "impact_pct": float(impact / base_output * 100) if base_output else 0,
            })

        df = pd.DataFrame(rows).sort_values("impact", ascending=False)
        return df

    def scenario_analysis(
        self,
        scenarios: dict[str, dict[str, float]],
        update_funcs: dict[str, Callable],
        output_func: Callable,
        probabilities: dict[str, float] | None = None,
    ) -> dict:
        """
        Run named scenarios with probability weights.

        Returns results and probability-weighted expected value.
        """
        results = []
        for name, variables in scenarios.items():
            for var_name, value in variables.items():
                if var_name in update_funcs:
                    update_funcs[var_name](value)

            output = output_func()
            prob = 1 / len(scenarios)
            if probabilities and name in probabilities:
                prob = probabilities[name]

            results.append(ScenarioResult(
                name=name,
                probability=prob,
                output=float(output),
                variables=variables,
            ))

        expected_value = sum(r.output * r.probability for r in results)

        return {
            "scenarios": [
                {
                    "name": r.name,
                    "probability": round(r.probability * 100, 1),
                    "output": round(r.output, 2),
                    "variables": r.variables,
                }
                for r in results
            ],
            "expected_value": round(expected_value, 2),
            "best_case": round(max(r.output for r in results), 2),
            "worst_case": round(min(r.output for r in results), 2),
            "range": round(max(r.output for r in results) - min(r.output for r in results), 2),
        }

    def monte_carlo(
        self,
        distributions: dict[str, Callable],
        output_func: Callable,
        iterations: int = 5000,
    ) -> dict:
        """
        Monte Carlo simulation.

        distributions: {"var_name": callable_that_returns_sample}
        output_func: takes **kwargs of sampled values, returns output
        """
        results = []
        for _ in range(iterations):
            sample = {name: dist() for name, dist in distributions.items()}
            try:
                output = output_func(**sample)
                results.append(float(output))
            except Exception:
                continue

        if not results:
            return {"error": "no valid iterations"}

        arr = np.array(results)
        return {
            "iterations": len(results),
            "mean": round(float(np.mean(arr)), 2),
            "median": round(float(np.median(arr)), 2),
            "std": round(float(np.std(arr)), 2),
            "min": round(float(np.min(arr)), 2),
            "max": round(float(np.max(arr)), 2),
            "var_95": round(float(np.percentile(arr, 5)), 2),
            "var_99": round(float(np.percentile(arr, 1)), 2),
            "p5": round(float(np.percentile(arr, 5)), 2),
            "p10": round(float(np.percentile(arr, 10)), 2),
            "p25": round(float(np.percentile(arr, 25)), 2),
            "p75": round(float(np.percentile(arr, 75)), 2),
            "p90": round(float(np.percentile(arr, 90)), 2),
            "p95": round(float(np.percentile(arr, 95)), 2),
            "prob_positive": round(float(np.mean(arr > 0) * 100), 1),
        }

    def breakeven(
        self,
        update_func: Callable,
        output_func: Callable,
        target: float,
        low: float,
        high: float,
        tolerance: float = 0.01,
        max_iterations: int = 100,
    ) -> dict:
        """Binary search for breakeven value where output equals target."""
        for iteration in range(max_iterations):
            mid = (low + high) / 2
            update_func(mid)
            output = output_func()

            if abs(output - target) < tolerance:
                return {
                    "breakeven_value": round(mid, 6),
                    "output_at_breakeven": round(output, 2),
                    "iterations": iteration + 1,
                    "converged": True,
                }

            if output < target:
                low = mid
            else:
                high = mid

        mid = (low + high) / 2
        update_func(mid)
        return {
            "breakeven_value": round(mid, 6),
            "output_at_breakeven": round(output_func(), 2),
            "iterations": max_iterations,
            "converged": False,
        }

    def backtest_parameter_sensitivity(
        self,
        backtest_func: Callable,
        param_name: str,
        param_values: list,
        base_config: dict,
    ) -> pd.DataFrame:
        """
        Test how a backtest's Sharpe/drawdown changes with parameter values.
        backtest_func takes a config dict and returns BacktestResults.
        """
        rows = []
        for val in param_values:
            config = {**base_config, param_name: val}
            try:
                result = backtest_func(config)
                rows.append({
                    "param_value": val,
                    "sharpe": result.sharpe_ratio,
                    "total_return": result.total_return,
                    "max_drawdown": result.max_drawdown,
                    "win_rate": result.win_rate,
                    "total_trades": result.total_trades,
                    "cost_drag": result.cost_drag_pct,
                })
            except Exception as e:
                log.warning(f"backtest failed for {param_name}={val}: {e}")

        return pd.DataFrame(rows)
