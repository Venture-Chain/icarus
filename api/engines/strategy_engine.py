"""
Strategy plugin loader and signal generation.
Discovers strategies from configurable directories, manages lifecycle.
"""
import importlib
import importlib.util
import logging
from pathlib import Path

from config import settings
from strategies.base import BaseStrategy, Signal

log = logging.getLogger("icarus.strategy")


class StrategyEngine:
    """Load, manage, and run strategy plugins."""

    def __init__(self, strategy_dirs: list[str] | None = None):
        self.strategy_dirs = strategy_dirs or settings.strategy_dirs
        if settings.research_path:
            research_strategies = f"{settings.research_path}/strategies"
            if research_strategies not in self.strategy_dirs:
                self.strategy_dirs.append(research_strategies)
        self.loaded_strategies: dict[str, BaseStrategy] = {}

    def load_strategies(self):
        """Discover and load all strategy plugins."""
        for directory in self.strategy_dirs:
            path = Path(directory)
            if not path.exists():
                log.debug(f"strategy dir not found: {directory}")
                continue
            for file in path.glob("*.py"):
                if file.name.startswith("_") or file.name == "base.py":
                    continue
                try:
                    self._load_module(file)
                except Exception as e:
                    log.error(f"failed to load {file}: {e}")

        log.info(f"loaded {len(self.loaded_strategies)} strategies: {list(self.loaded_strategies.keys())}")

    def _load_module(self, path: Path):
        """Load a strategy module and register any BaseStrategy subclasses."""
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if not spec or not spec.loader:
            return
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseStrategy)
                and attr is not BaseStrategy
            ):
                try:
                    instance = attr()
                    self.loaded_strategies[instance.name] = instance
                    log.info(f"registered strategy: {instance.name}")
                except Exception as e:
                    log.error(f"failed to instantiate {attr_name}: {e}")

    def get_strategy(self, name: str) -> BaseStrategy | None:
        return self.loaded_strategies.get(name)

    def list_strategies(self) -> list[dict]:
        return [
            {
                "name": s.name,
                "description": s.description,
                "parameters": s.parameters(),
                "required_data": [
                    {"type": r.data_type, "lookback": r.lookback_days}
                    for r in s.required_data()
                ],
            }
            for s in self.loaded_strategies.values()
        ]

    def compute_signals(self, strategy_name: str, universe: list[str], as_of) -> list[Signal]:
        """Run a strategy and get signals."""
        strategy = self.get_strategy(strategy_name)
        if not strategy:
            raise ValueError(f"strategy not found: {strategy_name}")
        return strategy.compute_signals(universe, as_of)


