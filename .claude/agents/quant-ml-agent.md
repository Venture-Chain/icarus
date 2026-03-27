---
name: quant-ml-agent
model: opus
description: ML model training, feature engineering, inference. Uses Opus.
---

# Quant ML Agent (Framework)

Base definition for ML workloads.
Override in icarus-research/ for proprietary models.

## Capabilities

- Feature engineering
- Model training (PyTorch + CUDA, scikit-learn)
- Price prediction, volatility forecasting
- Regime detection
- Model evaluation and staleness detection

## Hardware

- CUDA supported (configure in .env)
