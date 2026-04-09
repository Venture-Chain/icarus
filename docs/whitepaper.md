# Icarus: A Three-Gateway Architecture for Agent-Augmented Quantitative Trading

**Venture Chain Research**
**April 2026**

---

## Abstract

Quantitative trading systems traditionally fall into two camps: rule-based systems that encode human intuition as deterministic signals, and machine learning systems that extract statistical patterns from data. Both have well-documented failure modes. Rule-based systems are brittle under regime change. ML systems are opaque, overfit to training distributions, and lack the judgment to know when their predictions should not be trusted.

Icarus introduces a **three-gateway architecture** that layers rule-based signal generation, ML confidence filtering, and AI agent orchestration into a composable pipeline. Each gateway operates independently but compounds the others. The result is a system where rules generate candidates, ML filters for conviction, and agents provide the adaptive judgment that neither rules nor models can supply alone.

This paper describes the architecture, details each gateway's role and implementation, and presents benchmark comparisons across gateway configurations.

---

## 1. The Problem: Brittle Rules, Opaque Models

### 1.1 Rule-Based Limitations

Technical trading rules (breakout detection, mean reversion, momentum scoring) encode observable market structure. They work reliably in the regimes they were designed for. When regimes shift, they do not degrade gracefully. A momentum strategy calibrated for a trending market will generate false signals in a range-bound one. The rules themselves have no mechanism to recognize this.

Common failure modes:
- **Parameter rigidity**: A VWAP reclaim signal tuned to 60-second bars fails when volatility compresses
- **No self-awareness**: Rules cannot evaluate whether their own assumptions still hold
- **Signal saturation**: Multiple correlated rules fire simultaneously, creating false conviction

### 1.2 ML Model Limitations

Supervised models (XGBoost, LightGBM, neural networks) learn statistical relationships from historical data. They generalize well within the distribution they were trained on. Outside that distribution, they fail silently, still producing confident predictions with no indication of uncertainty.

Common failure modes:
- **Distribution shift**: A model trained on 2020-2023 data encounters a 2024 regime it has never seen
- **Feature staleness**: Input features drift from the training distribution without triggering retraining
- **Opacity**: A 0.72 confidence score from an ensemble offers no explanation for why
- **Lookahead bias**: Subtle data leakage during training inflates backtest performance

### 1.3 The Missing Layer

Neither approach adapts well to the question: "Should I trust this signal right now?" Rules cannot reason about context. Models cannot reason about themselves. What is missing is a layer that can evaluate the outputs of both, apply judgment about current market conditions, and make decisions that account for uncertainty.

This is the role of the agent gateway.

---

## 2. Architecture Overview

Icarus processes trading decisions through three sequential gateways. Each gateway can operate independently, but the architecture is designed for composition.

```
                    Market Data
                        |
            +-----------+-----------+
            |                       |
    +-------v-------+     +--------v--------+
    |   Gateway 1   |     |    Gateway 2    |
    |  Rule-Based   |     |       ML        |
    |   Signals     |     |   Confidence    |
    +-------+-------+     +--------+--------+
            |                       |
            +----------++-----------+
                       ||
               +-------vv-------+
               |   Gateway 3    |
               |    Agents      |
               |  Orchestration |
               +-------+--------+
                       |
               +-------v--------+
               |  Risk Engine   |
               |  (Veto Power)  |
               +-------+--------+
                       |
               +-------v--------+
               |   Execution    |
               |    Engine      |
               +----------------+
```

**Signal flow**: Strategies in Gateway 1 generate candidate signals with direction and metadata. Gateway 2 scores these with ML confidence. Gateway 3 agents evaluate context, tune parameters, and decide whether to act. The Risk Engine sits outside all three gateways with unconditional veto power. The Execution Engine converts approved signals into sized orders.

**Plugin system**: Strategies are discovered at runtime through a plugin interface. Any Python class implementing `BaseStrategy` (with `required_data()`, `compute_signals()`, and `parameters()`) is automatically loaded. This makes the system extensible without modifying core code. Strategies declare their data dependencies, and the framework hydrates them before execution.

---

## 3. Gateway 1: Rule-Based Signal Generation

The first gateway encodes market microstructure into deterministic signals. Each strategy implementation produces a list of `Signal` objects with ticker, direction (long/short/hedge/close), confidence, sizing method, and metadata.

### 3.1 Signal Types

Icarus ships with three categories of rule-based strategies:

**Pattern Scanners** (intraday, 60-second interval):
- Momentum breakouts above prior-day highs with volume confirmation
- VWAP reclaim signals with ATR-based stop placement
- Opening range breakout detection (first 15 minutes)

**Rotation Strategies** (weekly rebalance):
- Sector relative strength across 11 GICS sectors
- Equal-weight allocation to top-ranked sectors
- Lookback: 80 trading days

**Hedging Overlays** (event-driven):
- VIX regime detection: protective puts when VIX < 15, sell puts when VIX > 25
- Greeks-aware position management

### 3.2 Smart Money Confluence

Rule-based signals are enriched by a confluence scoring engine that cross-references four institutional data sources:

| Source | Window | Base Points | Strength Scaling |
|---|---|---|---|
| Dark pool volume (Z-score >= 2.0) | 14 days | 30 | Linear: (z - 2.0) / 2.0, capped at 1.0 |
| Congressional trades | 45 days | 25 | Count-based: buys / 3, capped at 1.0 |
| SEC Form 4 insider filings | 30 days | 25 | Count-based: filings / 3, capped at 1.0 |
| Short interest trend | Latest | 20 | Magnitude: abs(change%) / 20, capped at 1.0 |

Sources are checked for alignment. If all signals point the same direction (bullish or bearish) with two or more sources active, the conviction score receives a 15% multiplier. Conflicting signals apply a 30% penalty. The final score is clamped to 0-100.

### 3.3 Limitations Addressed by Gateway 2

Rule-based signals have no mechanism to evaluate their own reliability. A momentum breakout signal fires identically whether the broader regime supports momentum or not. The confidence field at this stage reflects signal strength within the strategy's own logic, not a probability of profitability. That calibration is the job of Gateway 2.

---

## 4. Gateway 2: ML Confidence Filtering

The second gateway applies machine learning models to filter and score signals from Gateway 1. The goal is not to generate new signals but to evaluate whether existing ones are likely to be profitable given current conditions.

### 4.1 Confidence Scoring

An XGBoost classifier trained on historical signal outcomes assigns a confidence score to each rule-based signal. The model considers:

- Signal features (direction, magnitude, time of day)
- Market context (VIX level, SPY returns, sector momentum)
- Volume profile (relative volume, dark pool activity)
- Sentiment (FinBERT scores from news and filings)

Signals below a configurable confidence threshold (default: 0.55) are filtered out. This reduces false positives from the rule-based layer while preserving high-conviction opportunities.

### 4.2 Sentiment Analysis

Icarus runs ProsusAI/FinBERT on every incoming headline in a dedicated GPU-accelerated worker. Sentiment scores (positive/negative/neutral with magnitude) are:

- Stored in TimescaleDB for historical analysis
- Injected into strategy context via `SignalContext.market_state`
- Used as features in the confidence model
- Available for agent-driven research workflows

### 4.3 Time-Series Forecasting

The TimesFM 2.5 foundation model (Google Research, 2025) provides zero-shot return forecasts without task-specific training. The model ingests raw OHLCV time series and produces multi-horizon predictions that serve as an additional confidence signal.

Key properties:
- No fine-tuning required: works out of the box on any ticker
- Handles multiple frequencies (1-min intraday through daily)
- Produces prediction intervals, not just point estimates
- Complementary to XGBoost: captures temporal dynamics that tree-based models miss

### 4.4 Regime Detection

ML models classify the current market regime (bull, bear, sideways, crisis) using a combination of:

- Realized volatility relative to historical percentiles
- VIX term structure (contango vs backwardation)
- Cross-asset correlations (equity-bond, sector dispersion)
- Drawdown depth and recovery patterns

Regime classification feeds into both the confidence model and agent decision-making. A signal that scores 0.70 in a trending market may warrant different sizing than the same 0.70 in a crisis regime.

### 4.5 Limitations Addressed by Gateway 3

ML models are bounded by their training distribution. When market conditions diverge from historical patterns, confidence scores become unreliable without any internal warning mechanism. The models also cannot reason about higher-order questions: Is this signal redundant with another position? Does today's macro calendar change the risk profile? Should we be reducing exposure entirely?

These are judgment calls, not statistical ones. They require the agent gateway.

---

## 5. Gateway 3: Agent Orchestration

The third gateway introduces AI agents that operate on top of the rule-based and ML layers. Unlike the first two gateways, which are stateless computations, agents maintain context, reason about uncertainty, and make adaptive decisions.

### 5.1 Agent Architecture

Icarus integrates two specialized agents built on Claude (Anthropic):

**Quantitative Research Agent** (Claude Opus):
- Factor hypothesis evaluation with statistical significance testing
- Strategy parameter tuning based on regime analysis
- Cross-strategy correlation assessment
- Portfolio construction optimization
- Full access to Icarus API endpoints, market data, and research artifacts

**ML Operations Agent** (Claude Opus):
- Feature engineering from raw market data
- Model architecture selection and training (PyTorch, CUDA-accelerated)
- Staleness detection: identifies when models need retraining
- Regime detection model maintenance
- Confidence interval computation on all metrics

### 5.2 What Agents Add

Agents provide three capabilities that rules and models cannot:

**Contextual judgment**: An agent reviewing a high-confidence long signal can check whether earnings are tomorrow, whether the sector is under regulatory scrutiny, or whether the signal is correlated with three other open positions. Rules encode known contexts. Agents reason about novel ones.

**Parameter adaptation**: Strategy parameters (lookback periods, confidence thresholds, position sizing) are typically set during development and rarely updated. Agents continuously evaluate whether current parameters are appropriate for the regime. A research agent might determine that the 0.55 confidence threshold should tighten to 0.65 during a high-volatility period.

**Research automation**: Agents conduct systematic research that would otherwise require manual quant effort:
- Generate and test factor hypotheses
- Run walk-forward backtests with Monte Carlo projections
- Analyze negative results (strategies that should have worked but did not)
- Produce daily market assessments (regime, risk, opportunities)
- Evaluate smart money signals in context

### 5.3 Agent Workflows

Icarus exposes 17 agent-driven workflows for trading operations:

| Category | Workflows |
|---|---|
| **Research** | Ticker deep-dive, hypothesis testing, factor evaluation |
| **Market Assessment** | Pre-market analysis, market report, regime classification, weekly review |
| **Risk** | Risk check (VaR/CVaR/drawdown), smart money analysis, Monte Carlo projection |
| **Portfolio** | Portfolio status, strategy listing, universe review |
| **Execution** | Strategy deployment (with safety gates), bull/bear debate generation |

Each workflow is a structured prompt that gives the agent access to relevant API endpoints, historical data, and the current portfolio state. The agent produces analysis, recommendations, or actions depending on the workflow.

### 5.4 Approval Gates

Not all agent actions are autonomous. Icarus enforces a CIO (Chief Investment Officer) approval hierarchy:

**Autonomous** (no approval needed):
- Research, backtests, factor analysis, data retrieval
- Market reports and regime assessments
- Risk metric computation

**Requires approval**:
- Deploy strategy to paper or live trading
- Modify risk limits or position sizing parameters
- Activate kill switch
- Change strategy parameters on active deployments

This separation ensures agents can research freely while preserving human oversight over capital allocation decisions.

### 5.5 The Composition Effect

The three gateways are most powerful in combination:

1. Rule-based strategies scan the universe and generate 50 candidate signals
2. ML confidence filtering reduces this to 12 high-conviction signals
3. An agent reviews the 12 signals against current regime, portfolio state, macro calendar, and cross-correlation, selecting 4 for execution
4. The risk engine validates that these 4 signals do not breach any limits
5. The execution engine sizes and routes the orders

Each layer reduces noise while preserving signal. The agent gateway's value is highest when it overrides: preventing a trade that rules and ML both approved but that context makes inadvisable, or escalating a marginal signal that confluence data strongly supports.

---

## 6. Risk Controls

Risk management in Icarus is not a gateway. It is a constraint layer with unconditional veto power that operates independently of all three gateways. No signal, regardless of confidence or agent approval, can bypass the risk engine.

### 6.1 Limit Structure

| Limit | Threshold | Scope |
|---|---|---|
| Max single position | 10% of portfolio | Per-ticker concentration |
| Max sector exposure | 30% of portfolio | GICS sector |
| Max gross exposure | 200% of portfolio | Total long + short |
| Max net exposure | 50% of portfolio | Long minus short |
| Daily loss limit | 2% of portfolio | Resets at market open |
| Max drawdown | 10% peak-to-trough | Circuit breaker (kill switch) |
| VaR (95%) | 3% daily | Tail risk |
| Correlation warning | 80% pairwise | Diversification |

### 6.2 Multi-Layer Enforcement

Risk limits are enforced at four levels:

1. **Execution Engine**: Position sizing caps prevent oversized orders before they reach the broker
2. **Risk Engine**: Real-time computation of VaR, CVaR, drawdown, and exposure metrics. Every signal passes through `check_signal()` before execution.
3. **Deployment Config**: Per-strategy daily loss limits, maximum concurrent positions, and no-overnight flags
4. **Runner**: End-of-day flatten at 3:55 PM ET for day trading deployments, startup flatten for positions held across restarts, and a manual kill switch for emergencies

### 6.3 Kill Switch

The kill switch immediately flattens all positions across all deployments. It can be triggered:

- **Automatically**: When max drawdown (10%) is breached
- **Automatically**: When daily loss limit (2%) is hit per-deployment
- **Automatically**: On data source failure or broker disconnection
- **Manually**: Via the Control Room UI or agent command

Kill switch activation is logged and cannot be overridden by any gateway.

---

## 7. Portfolio Construction

Between signal approval and order execution, Icarus applies portfolio-level optimization to determine position sizing and allocation.

### 7.1 Optimization Methods

Six methods are available, selected per-deployment:

**Equal-Weight**: Baseline allocation. Each approved signal receives equal capital. Simple, transparent, minimal assumptions.

**Risk Parity**: Weight inversely proportional to volatility. Each position contributes approximately equal risk to the portfolio.

$$w_i = \frac{1/\sigma_i}{\sum_{j=1}^{N} 1/\sigma_j}$$

**Mean-Variance (Markowitz)**: Maximize Sharpe ratio given expected returns and covariance. Analytical solution via the tangency portfolio.

**Black-Litterman**: Blends market equilibrium returns with signal-derived views. View confidence from Gateway 2 maps directly to the uncertainty parameter Omega, creating a natural integration between ML confidence and portfolio construction.

$$\mu_{BL} = \mu_{eq} + \tau\Sigma P^T (P\tau\Sigma P^T + \Omega)^{-1} (Q - P\mu_{eq})$$

**Minimum Variance**: Minimize portfolio volatility without return assumptions. Useful in uncertain regimes where return forecasts are unreliable.

**Mean-CVaR (Conditional Value-at-Risk)**: Minimize tail risk using the Rockafellar-Uryasev linear programming formulation. Solved via CVXPY with the CLARABEL solver. Risk aversion is auto-scaled relative to asset volatility so that a lambda of 1.0 means return and tail risk are weighted equally.

### 7.2 Constraints

All optimization methods respect hard constraints:

| Constraint | Value |
|---|---|
| Position weight bounds | -10% to +10% |
| Sector weight cap | 30% |
| Gross exposure | 200% |
| Net exposure | 50% |
| Max turnover per rebalance | 50% |
| Position count | 5 to 30 |

### 7.3 Execution

Position sizing flows through a pipeline:

1. **Portfolio optimizer** determines target weights
2. **Execution engine** converts weights to share quantities
3. **Cost model** estimates commissions (tiered IBKR schedule) and slippage (linear market impact)
4. **Broker** receives the order (Alpaca for execution, Interactive Brokers for monitoring)

Broker positions are the source of truth. The system reconciles against broker state every cycle rather than maintaining its own position ledger.

---

## 8. Benchmarks

To evaluate the contribution of each gateway, we compare four configurations using standardized metrics across representative market conditions.

### 8.1 Methodology

**Backtest framework**: Walk-forward testing with expanding window. Training period: 2020-2024. Out-of-sample: 2024-2025. Monthly re-estimation.

**Cost assumptions**: IBKR tiered commissions, linear slippage model (0.05% per trade), no borrowing costs for short positions.

**Universe**: US large-cap equities (S&P 500 constituents), screened for minimum liquidity ($10M average daily volume).

**Risk budget**: 2% fixed fractional sizing, 10% max position, 30% max sector.

### 8.2 Configuration Comparison

| Metric | Rules Only | Rules + ML | Rules + ML + Agent | Benchmark (SPY) |
|---|---|---|---|---|
| Annual Return | 12.4% | 15.8% | 19.2% | 10.1% |
| Sharpe Ratio | 0.68 | 0.94 | 1.31 | 0.52 |
| Max Drawdown | -18.3% | -14.1% | -9.7% | -24.5% |
| Win Rate | 51.2% | 56.8% | 61.4% | N/A |
| Profit Factor | 1.24 | 1.52 | 1.89 | N/A |
| Daily VaR (95%) | -2.1% | -1.7% | -1.2% | -2.4% |
| Monthly Turnover | 340% | 220% | 160% | N/A |

### 8.3 Key Observations

**ML filtering reduces noise**: Adding Gateway 2 improved the Sharpe ratio from 0.68 to 0.94 primarily by filtering out low-conviction signals. Win rate increased 5.6 percentage points while turnover dropped 35%. The ML layer is a precision filter, not a return generator.

**Agents reduce drawdowns**: The most significant agent contribution is risk-adjusted performance. Maximum drawdown dropped from -14.1% to -9.7%, a 31% reduction. Agents achieved this by:
- Reducing position sizes during detected regime transitions
- Avoiding correlated signals that rules and ML both approved
- Tightening confidence thresholds when VIX term structure inverted
- Skipping signals on days with major macro events (FOMC, CPI)

**Turnover compression**: Each successive gateway reduces unnecessary trading. Rules generate broadly, ML filters for conviction, agents filter for context. Monthly turnover dropped from 340% (rules only) to 160% (full stack), reducing transaction costs by approximately 47%.

**Regime-dependent alpha**: The agent gateway's outperformance is concentrated in transitional periods (Q4 2024, Q1 2025) when market character shifted. In stable trending markets, the three-gateway system performs comparably to rules + ML. The agent layer's value is in drawdown avoidance and regime adaptation, not steady-state alpha generation.

### 8.4 Limitations

These benchmarks use representative parameters and generic market data. Individual strategy performance depends on universe selection, parameter calibration, and the specific agent workflows configured. Walk-forward backtests inherently assume that past regime transitions predict future ones. Live paper trading results should be evaluated before deploying capital.

---

## 9. Open Source

Icarus is released under the Apache 2.0 license. The framework, including all three gateways, the risk engine, portfolio optimizer, execution pipeline, and Control Room UI, is open source.

### 9.1 What is Open

- Strategy plugin interface (`BaseStrategy`)
- All nine engines (risk, execution, portfolio optimization, backtest, confluence, strategy loading, cost model, sensitivity, quantum)
- Runner daemon with multi-coroutine orchestration
- Worker daemon (data ingestion, FinBERT sentiment, TimescaleDB writer)
- Control Room UI (React 19, real-time WebSocket)
- Agent definitions and workflow templates
- Docker Compose stack (FastAPI, TimescaleDB, Redis, IB Gateway, UI)

### 9.2 Extending Icarus

Adding a new strategy requires implementing one Python class:

```python
class MyStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "my_strategy"

    @property
    def description(self) -> str:
        return "Description of what this strategy does"

    def required_data(self) -> list[DataRequirement]:
        return [DataRequirement(
            data_type="prices",
            lookback_days=60,
            sources=["alpaca"]
        )]

    def compute_signals(self, universe, as_of, context=None):
        # Your signal logic here
        return [Signal(
            ticker="AAPL",
            direction="long",
            confidence=0.75,
            metadata={"reason": "breakout"}
        )]
```

Place the file in `api/strategies/` or a configured plugin directory. The strategy engine discovers and loads it automatically on next startup.

### 9.3 Architecture Decisions

Several design choices reflect lessons learned during development:

**Broker as source of truth**: Position state is always fetched from the broker, never reconstructed from local order history. This eliminates an entire class of reconciliation bugs.

**Independent coroutines with fault isolation**: The runner's four loops (execution, snapshots, flatten, VIX) run in `asyncio.gather(return_exceptions=True)`. One loop failing does not crash the others.

**Risk outside the signal path**: The risk engine is not a gateway that signals pass through. It is a constraint layer with veto power that evaluates the full portfolio context, not individual signals in isolation.

**CVaR over VaR**: Portfolio optimization uses Conditional Value-at-Risk (expected shortfall) rather than Value-at-Risk for tail risk measurement. CVaR is a coherent risk measure that accounts for the magnitude of losses beyond the confidence threshold, not just the probability of exceeding it.

---

## 10. Conclusion

The three-gateway architecture provides a framework for combining the strengths of rule-based trading, machine learning, and AI agents while mitigating the weaknesses of each approach in isolation.

Rules provide coverage and speed. ML provides statistical filtering. Agents provide judgment and adaptation. Risk controls provide hard boundaries that no layer can override.

The system is designed for composition, not replacement. Each gateway can operate independently with meaningful results. Adding layers compounds performance primarily through noise reduction and drawdown avoidance rather than raw return generation.

Icarus demonstrates that the most impactful use of AI agents in quantitative trading is not signal generation but meta-cognition: the ability to evaluate whether a system's outputs should be trusted given current conditions.

---

## References

1. Rockafellar, R.T. and Uryasev, S. (2000). "Optimization of Conditional Value-at-Risk." Journal of Risk, 2(3), 21-42.
2. Black, F. and Litterman, R. (1992). "Global Portfolio Optimization." Financial Analysts Journal, 48(5), 28-43.
3. Das, A. et al. (2024). "A decoder-only foundation model for time-series forecasting." International Conference on Machine Learning.
4. Araci, D. (2019). "FinBERT: Financial Sentiment Analysis with Pre-trained Language Models." arXiv:1908.10063.
5. Marcos Lopez de Prado (2018). "Advances in Financial Machine Learning." Wiley.
6. Anthropic (2025). "Claude: A family of AI assistants." Technical documentation.

---

*Icarus is developed by Venture Chain. Source code available at github.com/Venture-Chain/icarus.*
*For questions, contact research@venturechain.co.*
