"""
Strategy plugin loader and signal generation.
Discovers strategies from configurable directories, manages lifecycle.
"""
import importlib
import importlib.util
import logging
import sys
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
        # Check if this file is in any directory named "strategies" (could be /api/strategies or /app/strategies)
        parent_dir = path.parent.resolve()
        is_strategies_pkg = parent_dir.name == "strategies" and (parent_dir / "__init__.py").exists()

        if is_strategies_pkg:
            # Ensure the strategies package is importable from this directory
            api_dir = str(parent_dir.parent)
            if api_dir not in sys.path:
                sys.path.insert(0, api_dir)
            module_name = f"strategies.{path.stem}"
            module = importlib.import_module(module_name)
        else:
            # Research or external strategies: load by file path.
            # Pre-load sibling modules (like indicators.py) into the
            # strategies package namespace so "from strategies.X import ..."
            # resolves correctly for research strategy files.
            self._preload_research_siblings(parent_dir)

            module_name = f"research_strategies.{path.stem}"
            if module_name in sys.modules:
                module = sys.modules[module_name]
            else:
                spec = importlib.util.spec_from_file_location(module_name, path)
                if not spec or not spec.loader:
                    return
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
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

    def _preload_research_siblings(self, directory: Path):
        """Register helper modules from a research strategies directory
        into the strategies.* namespace so imports like
        'from strategies.indicators import ...' resolve correctly."""
        for sibling in directory.glob("*.py"):
            if sibling.name.startswith("_"):
                continue
            pkg_name = f"strategies.{sibling.stem}"
            if pkg_name in sys.modules:
                continue
            try:
                spec = importlib.util.spec_from_file_location(pkg_name, sibling)
                if not spec or not spec.loader:
                    continue
                mod = importlib.util.module_from_spec(spec)
                sys.modules[pkg_name] = mod
                spec.loader.exec_module(mod)
            except Exception:
                pass  # non-critical: only needed if a strategy imports it

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


