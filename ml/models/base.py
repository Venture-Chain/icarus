"""
Base model interface for ML strategies.
All custom models implement this.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass
class ModelPrediction:
    direction: float     # positive = bullish, negative = bearish
    magnitude: float     # expected return magnitude
    confidence: float    # 0 to 1
    regime: str = ""     # bull, bear, sideways, crisis


class BaseMLModel(ABC):
    """Interface for ML models used in strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def model_type(self) -> str:
        ...

    @abstractmethod
    def train(self, features: np.ndarray, targets: np.ndarray):
        ...

    @abstractmethod
    def predict(self, features: np.ndarray) -> ModelPrediction:
        ...

    @abstractmethod
    def is_trained(self) -> bool:
        ...
