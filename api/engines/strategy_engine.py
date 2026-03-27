"""
Strategy plugin loader and signal generation.
Loads strategies from configurable directory paths.
"""
import importlib
import os
from pathlib import Path


class StrategyEngine:
    def __init__(self, strategy_dirs: list[str] = None):
        self.strategy_dirs = strategy_dirs or ["strategies"]
        self.loaded_strategies = {}

    def load_strategies(self):
        """Discover and load strategy plugins from configured directories."""
        for directory in self.strategy_dirs:
            path = Path(directory)
            if not path.exists():
                continue
            for file in path.glob("*.py"):
                if file.name.startswith("_") or file.name == "base.py":
                    continue
                self._load_strategy_module(file)

    def _load_strategy_module(self, path: Path):
        """Load a single strategy module."""
        pass

    def get_strategy(self, name: str):
        """Get a loaded strategy by name."""
        return self.loaded_strategies.get(name)

    def list_strategies(self):
        """List all loaded strategies."""
        return list(self.loaded_strategies.keys())
