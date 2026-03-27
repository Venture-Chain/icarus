"""
ML training and inference engine.
PyTorch with CUDA support (RTX 4080).
Handles model lifecycle: train, evaluate, predict, track experiments.
"""
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

log = logging.getLogger("icarus.ml")


@dataclass
class TrainingConfig:
    model_name: str
    model_type: str = "lstm"  # lstm, transformer, xgboost, regime
    features: list[str] = field(default_factory=list)
    target: str = "returns_1d"
    lookback: int = 60
    epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 0.001
    train_split: float = 0.7
    val_split: float = 0.15
    # test_split = 1 - train - val


@dataclass
class TrainingResult:
    model_name: str
    model_type: str
    device: str
    train_loss: float = 0
    val_loss: float = 0
    test_metrics: dict = field(default_factory=dict)
    training_time_sec: float = 0
    epochs_completed: int = 0
    feature_importance: dict = field(default_factory=dict)
    saved_path: str = ""

    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "model_type": self.model_type,
            "device": self.device,
            "train_loss": round(self.train_loss, 6),
            "val_loss": round(self.val_loss, 6),
            "test_metrics": self.test_metrics,
            "training_time_sec": round(self.training_time_sec, 1),
            "epochs_completed": self.epochs_completed,
            "saved_path": self.saved_path,
        }


@dataclass
class PredictionResult:
    ticker: str
    predictions: list[float] = field(default_factory=list)
    confidence: float = 0
    model_name: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "predictions": [round(p, 6) for p in self.predictions],
            "confidence": round(self.confidence, 4),
            "model_name": self.model_name,
            "timestamp": self.timestamp,
        }


@dataclass
class Experiment:
    id: str
    model_name: str
    config: dict
    result: dict
    created_at: str


class MLEngine:
    """ML model training, inference, and experiment tracking."""

    def __init__(self, models_dir: str = "ml/models", weights_dir: str = "ml/weights"):
        self.models_dir = Path(models_dir)
        self.weights_dir = Path(weights_dir)
        self.device = "cpu"
        self.experiments: list[Experiment] = []
        self._loaded_models: dict = {}
        self._detect_cuda()

        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.weights_dir.mkdir(parents=True, exist_ok=True)

    def _detect_cuda(self):
        try:
            import torch
            if torch.cuda.is_available():
                self.device = "cuda"
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_mem / 1e9
                log.info(f"CUDA available: {gpu_name} ({gpu_memory:.1f} GB)")
            else:
                log.info("CUDA not available, using CPU")
        except ImportError:
            log.warning("PyTorch not installed, ML engine limited")

    async def train(self, config: TrainingConfig, data: np.ndarray, targets: np.ndarray) -> TrainingResult:
        """
        Train a model.

        Args:
            config: Training configuration
            data: Feature matrix (samples x features)
            targets: Target values (samples,)
        """
        start_time = datetime.now()
        result = TrainingResult(
            model_name=config.model_name,
            model_type=config.model_type,
            device=self.device,
        )

        if config.model_type in ("lstm", "transformer"):
            result = await self._train_pytorch(config, data, targets, result)
        elif config.model_type == "xgboost":
            result = await self._train_xgboost(config, data, targets, result)
        elif config.model_type == "regime":
            result = await self._train_regime(config, data, targets, result)
        else:
            raise ValueError(f"unknown model type: {config.model_type}")

        result.training_time_sec = (datetime.now() - start_time).total_seconds()

        # Track experiment
        exp = Experiment(
            id=f"{config.model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            model_name=config.model_name,
            config=vars(config),
            result=result.to_dict(),
            created_at=datetime.now().isoformat(),
        )
        self.experiments.append(exp)

        return result

    async def _train_pytorch(
        self, config: TrainingConfig, data: np.ndarray, targets: np.ndarray, result: TrainingResult
    ) -> TrainingResult:
        """Train LSTM or Transformer model with PyTorch."""
        try:
            import torch
            import torch.nn as nn
            from torch.utils.data import DataLoader, TensorDataset
        except ImportError:
            result.test_metrics = {"error": "PyTorch not installed"}
            return result

        device = torch.device(self.device)

        # Time-series split (no shuffling, preserve order)
        n = len(data)
        train_end = int(n * config.train_split)
        val_end = int(n * (config.train_split + config.val_split))

        X_train = torch.FloatTensor(data[:train_end]).to(device)
        y_train = torch.FloatTensor(targets[:train_end]).to(device)
        X_val = torch.FloatTensor(data[train_end:val_end]).to(device)
        y_val = torch.FloatTensor(targets[train_end:val_end]).to(device)
        X_test = torch.FloatTensor(data[val_end:]).to(device)
        y_test = torch.FloatTensor(targets[val_end:]).to(device)

        # Reshape for sequence models: (batch, seq_len, features)
        n_features = data.shape[1] if len(data.shape) > 1 else 1
        if len(X_train.shape) == 2:
            X_train = X_train.unsqueeze(1)
            X_val = X_val.unsqueeze(1)
            X_test = X_test.unsqueeze(1)

        # Build model
        if config.model_type == "lstm":
            model = _LSTMModel(n_features, hidden_size=64, num_layers=2, output_size=1).to(device)
        else:
            model = _TransformerModel(n_features, d_model=64, nhead=4, num_layers=2).to(device)

        optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
        criterion = nn.MSELoss()

        # Training loop
        best_val_loss = float("inf")
        for epoch in range(config.epochs):
            model.train()
            optimizer.zero_grad()
            output = model(X_train).squeeze()
            loss = criterion(output, y_train)
            loss.backward()
            optimizer.step()

            # Validation
            model.eval()
            with torch.no_grad():
                val_output = model(X_val).squeeze()
                val_loss = criterion(val_output, y_val).item()

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                # Save best weights
                save_path = self.weights_dir / f"{config.model_name}.pt"
                torch.save(model.state_dict(), save_path)
                result.saved_path = str(save_path)

            result.epochs_completed = epoch + 1

        result.train_loss = loss.item()
        result.val_loss = best_val_loss

        # Test evaluation
        model.eval()
        with torch.no_grad():
            test_output = model(X_test).squeeze()
            test_loss = criterion(test_output, y_test).item()

            preds = test_output.cpu().numpy()
            actuals = y_test.cpu().numpy()

            # Direction accuracy
            if len(preds) > 1:
                pred_direction = np.sign(preds)
                actual_direction = np.sign(actuals)
                direction_accuracy = np.mean(pred_direction == actual_direction)
            else:
                direction_accuracy = 0

            result.test_metrics = {
                "test_loss": round(test_loss, 6),
                "direction_accuracy": round(float(direction_accuracy), 4),
                "mean_absolute_error": round(float(np.mean(np.abs(preds - actuals))), 6),
                "correlation": round(float(np.corrcoef(preds.flatten(), actuals.flatten())[0, 1]) if len(preds) > 2 else 0, 4),
            }

        self._loaded_models[config.model_name] = model
        return result

    async def _train_xgboost(
        self, config: TrainingConfig, data: np.ndarray, targets: np.ndarray, result: TrainingResult
    ) -> TrainingResult:
        """Train XGBoost model (CPU-based, fast for tabular data)."""
        try:
            from sklearn.ensemble import GradientBoostingRegressor
            from sklearn.metrics import mean_absolute_error
        except ImportError:
            result.test_metrics = {"error": "scikit-learn not installed"}
            return result

        n = len(data)
        train_end = int(n * config.train_split)
        val_end = int(n * (config.train_split + config.val_split))

        X_train, y_train = data[:train_end], targets[:train_end]
        X_test, y_test = data[val_end:], targets[val_end:]

        model = GradientBoostingRegressor(
            n_estimators=200,
            max_depth=5,
            learning_rate=config.learning_rate,
            random_state=42,
        )
        model.fit(X_train, y_train)

        preds = model.predict(X_test)
        mae = mean_absolute_error(y_test, preds)
        direction_acc = np.mean(np.sign(preds) == np.sign(y_test))

        result.test_metrics = {
            "mae": round(float(mae), 6),
            "direction_accuracy": round(float(direction_acc), 4),
        }

        # Feature importance
        if config.features:
            importances = model.feature_importances_
            result.feature_importance = {
                config.features[i]: round(float(importances[i]), 4)
                for i in range(min(len(config.features), len(importances)))
            }

        self._loaded_models[config.model_name] = model
        result.saved_path = str(self.weights_dir / f"{config.model_name}.pkl")
        return result

    async def _train_regime(
        self, config: TrainingConfig, data: np.ndarray, targets: np.ndarray, result: TrainingResult
    ) -> TrainingResult:
        """Train regime detection model using Hidden Markov-like approach."""
        from sklearn.cluster import KMeans

        n_regimes = 3  # bull, bear, sideways
        model = KMeans(n_clusters=n_regimes, random_state=42, n_init=10)
        model.fit(data)

        labels = model.labels_
        centroids = model.cluster_centers_

        # Map clusters to regime names by return level
        cluster_returns = {}
        for i in range(n_regimes):
            mask = labels == i
            if mask.any():
                cluster_returns[i] = float(np.mean(targets[mask]))

        sorted_clusters = sorted(cluster_returns.items(), key=lambda x: x[1])
        regime_map = {}
        regime_names = ["bear", "sideways", "bull"]
        for idx, (cluster_id, _) in enumerate(sorted_clusters):
            regime_map[cluster_id] = regime_names[min(idx, len(regime_names) - 1)]

        result.test_metrics = {
            "n_regimes": n_regimes,
            "regime_distribution": {
                regime_map.get(i, f"regime_{i}"): int(np.sum(labels == i))
                for i in range(n_regimes)
            },
            "cluster_returns": {
                regime_map.get(k, f"regime_{k}"): round(v * 100, 2)
                for k, v in cluster_returns.items()
            },
        }

        self._loaded_models[config.model_name] = {
            "model": model,
            "regime_map": regime_map,
        }
        return result

    async def predict(self, model_name: str, ticker: str, features: np.ndarray) -> PredictionResult:
        """Run inference with a loaded model."""
        result = PredictionResult(
            ticker=ticker,
            model_name=model_name,
            timestamp=datetime.now().isoformat(),
        )

        model = self._loaded_models.get(model_name)
        if model is None:
            return result

        try:
            import torch
            if isinstance(model, torch.nn.Module):
                model.eval()
                device = next(model.parameters()).device
                X = torch.FloatTensor(features).unsqueeze(0).unsqueeze(0).to(device)
                with torch.no_grad():
                    pred = model(X).squeeze().cpu().numpy()
                result.predictions = [float(pred)] if pred.ndim == 0 else pred.tolist()
                result.confidence = min(abs(float(pred)) * 5, 1.0)  # Scale to 0-1
            elif isinstance(model, dict) and "model" in model:
                # Regime model
                pred = model["model"].predict(features.reshape(1, -1))[0]
                regime = model["regime_map"].get(int(pred), "unknown")
                result.predictions = [float(pred)]
                result.confidence = 0.7
                result.model_name = f"{model_name}:{regime}"
            else:
                # sklearn model
                pred = model.predict(features.reshape(1, -1))
                result.predictions = pred.tolist()
                result.confidence = min(abs(float(pred[0])) * 5, 1.0)
        except Exception as e:
            log.error(f"prediction failed for {model_name}: {e}")

        return result

    def get_experiments(self) -> list[dict]:
        """List all training experiments."""
        return [
            {
                "id": exp.id,
                "model_name": exp.model_name,
                "config": exp.config,
                "result": exp.result,
                "created_at": exp.created_at,
            }
            for exp in self.experiments
        ]

    def is_stale(self, model_name: str, max_age_days: int = 30) -> bool:
        """Check if a model needs retraining."""
        for exp in reversed(self.experiments):
            if exp.model_name == model_name:
                created = datetime.fromisoformat(exp.created_at)
                age = (datetime.now() - created).days
                return age > max_age_days
        return True  # No experiment found


class _LSTMModel:
    """Placeholder for when torch is not available at import time."""
    pass


class _TransformerModel:
    """Placeholder for when torch is not available at import time."""
    pass


# Conditionally define PyTorch models
try:
    import torch
    import torch.nn as nn

    class _LSTMModel(nn.Module):
        def __init__(self, input_size: int, hidden_size: int = 64, num_layers: int = 2, output_size: int = 1):
            super().__init__()
            self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=0.2)
            self.fc = nn.Linear(hidden_size, output_size)

        def forward(self, x):
            lstm_out, _ = self.lstm(x)
            return self.fc(lstm_out[:, -1, :])

    class _TransformerModel(nn.Module):
        def __init__(self, input_size: int, d_model: int = 64, nhead: int = 4, num_layers: int = 2):
            super().__init__()
            self.input_proj = nn.Linear(input_size, d_model)
            encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, batch_first=True)
            self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
            self.fc = nn.Linear(d_model, 1)

        def forward(self, x):
            x = self.input_proj(x)
            x = self.transformer(x)
            return self.fc(x[:, -1, :])

except ImportError:
    pass
