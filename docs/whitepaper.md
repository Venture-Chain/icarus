# Icarus: A Three-Gateway Architecture for Agent-Augmented Quantitative Trading

**Venture Chain Research**
**April 2026**

---

## Abstract

Quantitative trading systems traditionally fall into two camps: rule-based systems that encode human intuition as deterministic signals, and machine learning systems that extract statistical patterns from data. Both have well-documented failure modes. Rule-based systems are brittle under regime change. ML systems are opaque, overfit to training distributions, and lack the judgment to know when their predictions should not be trusted.

Icarus introduces a **three-gateway architecture** that layers rule-based signal generation, ML confidence filtering, and AI agent orchestration into a composable pipeline. Each gateway operates independently but compounds the others. The result is a system where rules generate candidates, ML filters for conviction, and agents provide the adaptive judgment that neither rules nor models can supply alone.

This paper describes the architecture, details each gateway's role, and explains why the agent layer solves problems that the first two gateways cannot address on their own.

---

## 1. The Problem: Brittle Rules, Opaque Models

### 1.1 Rule-Based Limitations

Technical trading rules (breakout detection, mean reversion, momentum scoring) encode observable market structure. They work reliably in the regimes they were designed for. When regimes shift, they do not degrade gracefully. A momentum strategy calibrated for a trending market will generate false signals in a range-bound one. The rules themselves have no mechanism to recognize this.

This is not a solvable problem within rule-based systems. Adding more rules to detect regime changes just creates a second rule-based system with the same brittleness one level up. The system needs something qualitatively different: the ability to reason about whether its own assumptions still hold.

### 1.2 ML Model Limitations

Supervised models (XGBoost, LightGBM, neural networks) learn statistical relationships from historical data. They generalize well within the distribution they were trained on. Outside that distribution, they fail silently, still producing confident predictions with no indication of uncertainty.

The core issue is that ML models are function approximators, not reasoning systems. A confidence score of 0.72 from an ensemble tells you nothing about whether the model's training distribution resembles today's market. The model cannot distinguish between "I have high confidence because this looks like patterns I've seen before" and "I have high confidence because I've never seen anything like this and I'm extrapolating."

This distinction matters enormously in markets, where the moments of highest model confidence are often the moments of greatest regime fragility.

### 1.3 The Missing Layer

Neither approach adapts well to the question: "Should I trust this signal right now?"

Rules cannot reason about context. Models cannot reason about themselves. What is missing is a layer that can evaluate the outputs of both, apply judgment about current market conditions, and make decisions that account for uncertainty. Not statistical uncertainty (which models handle), but epistemic uncertainty: the kind where you do not know what you do not know.

This is the role of the agent gateway.

---

## 2. Related Work

### 2.1 Existing Quantitative Frameworks

Open-source quantitative trading frameworks (Zipline, QuantConnect/Lean, Backtrader, VectorBT) provide backtesting engines, event-driven architectures, and broker integrations. These frameworks treat strategy logic as a monolithic block: data goes in, orders come out. There is no architectural separation between signal generation, confidence assessment, and contextual judgment. A strategy in Zipline handles all three concerns in a single `handle_data()` function.

This is adequate when the entire decision-making process can be expressed as code. It breaks down when some decisions require reasoning that cannot be predetermined.

### 2.2 ML-Augmented Trading Systems

Research platforms like FinRL and TradingGym integrate reinforcement learning into trading workflows. These systems replace rule-based logic with learned policies, treating trading as a sequential decision problem. The improvement over static rules is genuine, but the failure mode shifts rather than disappears: RL agents are notoriously sensitive to reward function design, suffer from non-stationarity in financial data, and provide even less interpretability than supervised models.

### 2.3 Where Icarus Differs

Icarus does not replace any layer with another. It composes three distinct approaches into a pipeline where each layer's output is evaluated by the next. The architecture assumes that no single approach is sufficient and that the value of composition comes from the ability to override: rules generate broadly, ML filters statistically, agents filter contextually.

The agent layer is not a more sophisticated model. It is a qualitatively different kind of system: one that can reason about the outputs of models rather than just producing its own.

---

## 3. Architecture Overview

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

## 4. Gateway 1: Rule-Based Signal Generation

The first gateway encodes market microstructure into deterministic signals. Each strategy implementation produces a list of `Signal` objects with ticker, direction (long/short/hedge/close), confidence, sizing method, and metadata.

### 4.1 Signal Types

Icarus ships with three categories of rule-based strategies:

**Pattern Scanners** (intraday, 60-second interval):
Momentum breakouts above prior-day highs with volume confirmation, VWAP reclaim signals with ATR-based stop placement, and opening range breakout detection. These operate on the shortest timeframe and generate the highest volume of candidate signals.

**Rotation Strategies** (weekly rebalance):
Sector relative strength across a custom sector taxonomy, with equal-weight allocation to top-ranked sectors. Uses dual-period rate of change (fast and slow) with a long-term trend filter to avoid rotating into declining sectors.

**Hedging Overlays** (event-driven):
VIX regime-based hedging via inverse ETFs, with position sizing scaled by regime severity. These strategies activate only when volatility conditions warrant protection, not on a fixed schedule.

### 4.2 Smart Money Confluence

Rule-based signals are enriched by a confluence scoring engine that cross-references four institutional data sources: dark pool volume anomalies, congressional trading disclosures, SEC Form 4 insider filings, and short interest trends.

Each source contributes to a conviction score (0-100) based on signal strength and recency. When multiple sources align in the same direction, the score receives a bonus multiplier. Conflicting signals apply a penalty. The result is a single number that captures how much institutional activity supports or contradicts a given signal.

The confluence score is not a trading signal itself. It is metadata that enriches existing signals, giving both the ML layer and the agent layer additional context for evaluation.

### 4.3 Limitations Addressed by Gateway 2

Rule-based signals have no mechanism to evaluate their own reliability. A momentum breakout signal fires identically whether the broader regime supports momentum or not. The confidence field at this stage reflects signal strength within the strategy's own logic, not a probability of profitability. That calibration is the job of Gateway 2.

---

## 5. Gateway 2: ML Confidence Filtering

The second gateway applies machine learning models to filter and score signals from Gateway 1. The goal is not to generate new signals but to evaluate whether existing ones are likely to be profitable given current conditions.

### 5.1 Confidence Scoring

An XGBoost classifier trained on historical signal outcomes assigns a confidence score to each rule-based signal. The model considers signal features (direction, magnitude, time of day), market context (VIX level, SPY returns, sector momentum), volume profile (relative volume, dark pool activity), and sentiment scores from news and filings.

Signals below a configurable confidence threshold are filtered out. This is where the bulk of noise reduction happens: a majority of rule-based signals are rejected at this stage, leaving only those where statistical evidence supports the directional thesis.

### 5.2 Sentiment Analysis

Icarus runs FinBERT (a BERT model fine-tuned for financial text) on every incoming headline in a dedicated GPU-accelerated worker. Sentiment scores are stored in TimescaleDB for historical analysis, injected into strategy context, used as features in the confidence model, and available for agent-driven research workflows.

The value of continuous sentiment processing is not any individual score but the time series it produces. Sentiment momentum (the rate of change in aggregate sentiment for a ticker) is often a better signal than point-in-time sentiment.

### 5.3 Time-Series Forecasting

The TimesFM 2.5 foundation model provides zero-shot return forecasts without task-specific training. The model ingests raw OHLCV time series and produces multi-horizon predictions with prediction intervals.

This is complementary to tree-based confidence scoring. XGBoost captures cross-sectional patterns (which tickers, under which conditions, at which times). TimesFM captures temporal dynamics (what the price trajectory itself suggests about near-term direction). The two models fail in different ways, which makes their disagreement informative.

### 5.4 Regime Detection

ML models classify the current market regime (bull, bear, sideways, crisis) using realized volatility percentiles, VIX term structure, cross-asset correlations, and drawdown patterns.

Regime classification feeds into both the confidence model and agent decision-making. A signal that scores 0.70 in a trending market may warrant different sizing than the same 0.70 in a crisis regime. But the regime model itself is still a statistical classifier: it can tell you the most likely regime, not whether a regime transition is about to happen.

### 5.5 Limitations Addressed by Gateway 3

ML models are bounded by their training distribution. When market conditions diverge from historical patterns, confidence scores become unreliable without any internal warning mechanism. The models also cannot reason about higher-order questions: Is this signal redundant with another position? Does today's macro calendar change the risk profile? Should we be reducing exposure entirely?

These are judgment calls, not statistical ones. They require the agent gateway.

---

## 6. Gateway 3: Agent Orchestration

The third gateway introduces AI agents that operate on top of the rule-based and ML layers. Unlike the first two gateways, which are stateless computations run on every cycle, agents maintain context, reason about uncertainty, and make adaptive decisions.

This is the architectural novelty of Icarus. Agents are not a smarter model. They are a different kind of system that can evaluate models.

### 6.1 Why Agents, Not Better Models

The standard response to ML limitations is to build better ML. More data, more features, more sophisticated architectures. This approach has diminishing returns in trading because the fundamental problem is not model capacity but epistemic uncertainty: the model does not know what it does not know.

An agent can reason about this gap. It can look at a high-confidence ML signal and ask: "The model says 0.82 confidence on this breakout. But the VIX term structure just inverted for the first time in six months. The model was trained on data where this happened twice. Is a sample size of two sufficient to trust this score?"

No amount of model improvement produces this kind of reasoning. It requires a system that can evaluate the conditions under which the model's outputs are trustworthy, which is a meta-cognitive task that sits above the model layer.

### 6.2 Agent Architecture

Icarus integrates two specialized agents built on Claude (Anthropic):

**Quantitative Research Agent**: Evaluates factor hypotheses with statistical significance testing, tunes strategy parameters based on regime analysis, assesses cross-strategy correlation, and optimizes portfolio construction. Has full access to the Icarus API, market data, and research artifacts.

**ML Operations Agent**: Engineers features from raw market data, selects and trains model architectures (PyTorch, CUDA-accelerated), detects model staleness, maintains regime detection models, and computes confidence intervals on all metrics.

Both agents operate at the Opus capability tier, which provides the reasoning depth required for quantitative analysis. Weaker models produce analysis that reads plausibly but fails on edge cases, exactly the scenarios where agent judgment matters most.

### 6.3 Concrete Examples

The agent layer's value is clearest in specific scenarios where rules and ML both produce the wrong answer:

**Scenario: Correlated signal accumulation.** The day trading strategy generates long signals on three semiconductor stocks. The ML layer confirms all three with confidence above 0.65. Each signal is individually valid. But the portfolio already holds two semiconductor positions from yesterday's rotation. The agent recognizes that executing all three signals would concentrate 40% of the portfolio in a single sub-sector, violating the spirit of diversification even if each position individually passes the 10% concentration limit. It selects the highest-conviction signal and skips the other two.

**Scenario: Macro event override.** FOMC minutes are released at 2:00 PM. The pattern scanner fires a VWAP reclaim signal at 2:03 PM on a large-cap name. The ML model assigns 0.71 confidence. Both layers are operating correctly within their scope: the pattern is real, and historically this pattern has been profitable. But the agent knows that the first 30 minutes after FOMC releases have elevated reversal rates. It holds the signal for re-evaluation rather than executing immediately.

**Scenario: Regime transition detection.** Over two weeks, the VIX creeps from 14 to 22 while the confidence model's aggregate accuracy on recent signals drops from 58% to 49%. Neither the rules nor the ML layer flag this: VIX 22 is not a crisis level, and 49% accuracy is within normal variance for a short window. The research agent, reviewing weekly performance, identifies the pattern: the model is not wrong, but the regime is shifting and the model's training data has limited coverage of this transition zone. It recommends tightening the confidence threshold from 0.55 to 0.65 until accuracy stabilizes.

These examples share a common structure: the agent is not generating a better signal. It is preventing a bad decision that the other layers would have made.

### 6.4 Agent Workflows

Icarus exposes 17 agent-driven workflows covering research (ticker deep-dives, hypothesis testing, factor evaluation), market assessment (pre-market analysis, regime classification, weekly review), risk analysis (VaR/CVaR checks, smart money analysis, Monte Carlo projections), portfolio management (status, strategy listing, universe review), and execution (strategy deployment with safety gates, bull/bear debate generation).

Each workflow is a structured prompt that gives the agent access to relevant API endpoints, historical data, and the current portfolio state. The agent produces analysis, recommendations, or actions depending on the workflow.

### 6.5 Approval Gates

Not all agent actions are autonomous. Icarus enforces a CIO (Chief Investment Officer) approval hierarchy:

**Autonomous** (no approval needed): Research, backtests, factor analysis, data retrieval, market reports, regime assessments, risk metric computation.

**Requires approval**: Deploy strategy to paper or live trading, modify risk limits or position sizing parameters, activate kill switch, change strategy parameters on active deployments.

This separation is deliberate. The agent layer's greatest value is in research and evaluation, tasks where speed and breadth matter and the cost of a wrong conclusion is low (you just ignore it). Capital allocation decisions have irreversible consequences and benefit from human judgment. The approval gate ensures agents amplify human decision-making rather than replacing it.

### 6.6 The Composition Effect

The three gateways are most powerful in combination. Consider the full pipeline:

1. Rule-based strategies scan the universe and generate ~50 candidate signals
2. ML confidence filtering reduces this to ~12 high-conviction signals
3. An agent reviews the 12 signals against current regime, portfolio state, macro calendar, and cross-correlation, selecting ~4 for execution
4. The risk engine validates that these 4 signals do not breach any limits
5. The execution engine sizes and routes the orders

Each layer reduces noise while preserving signal. Crucially, the reduction at each stage is qualitatively different: rules filter by pattern, ML filters by probability, agents filter by context. This means the errors at each stage are uncorrelated, which is the same insight behind ensemble methods in ML but applied at the architectural level.

---

## 7. Risk Controls

Risk management in Icarus is not a gateway. It is a constraint layer with unconditional veto power that operates independently of all three gateways. No signal, regardless of confidence or agent approval, can bypass the risk engine.

This separation is intentional. The gateways are about making good decisions. The risk engine is about surviving bad ones. Mixing the two creates a system that negotiates with its own risk limits, which is how blowups happen.

### 7.1 Limit Structure

Limits are enforced on concentration (per-ticker and per-sector), leverage (gross and net exposure), drawdown (daily loss and peak-to-trough), and tail risk (VaR at the 95th percentile). Each limit has a hard threshold that cannot be exceeded and an alert threshold at 80% that triggers early warnings.

### 7.2 Multi-Layer Enforcement

Risk limits are enforced at four independent levels:

1. **Execution Engine**: Position sizing caps prevent oversized orders before they reach the broker
2. **Risk Engine**: Real-time VaR, CVaR, drawdown, and exposure computation. Every signal passes through validation before execution.
3. **Deployment Config**: Per-strategy daily loss limits, maximum concurrent positions, and no-overnight flags
4. **Runner**: End-of-day flatten for day trading deployments, startup flatten for positions held across restarts, and a manual kill switch

The redundancy is deliberate. Any single layer can fail (a bug, a race condition, a misconfiguration). Four independent layers make simultaneous failure extremely unlikely.

### 7.3 Kill Switch

The kill switch immediately flattens all positions across all deployments. It triggers automatically on max drawdown breach, per-deployment daily loss limit, data source failure, or broker disconnection. It can also be activated manually via the Control Room UI or an agent command.

Kill switch activation is logged and cannot be overridden by any gateway.

---

## 8. Portfolio Construction

Between signal approval and order execution, Icarus applies portfolio-level optimization to determine position sizing and allocation.

### 8.1 Optimization Methods

Six methods are available, selected per-deployment based on the strategy's characteristics:

**Equal-Weight**: Baseline. Each approved signal receives equal capital. Minimal assumptions, maximum transparency.

**Risk Parity**: Weight inversely proportional to volatility so each position contributes approximately equal risk.

**Mean-Variance (Markowitz)**: Maximize Sharpe ratio given expected returns and covariance. Analytical tangency portfolio solution.

**Black-Litterman**: Blends market equilibrium returns with signal-derived views. This is where the three-gateway architecture creates a natural integration: ML confidence from Gateway 2 maps directly to the view uncertainty parameter (Omega). High-confidence signals produce tight views that pull the portfolio toward them. Low-confidence signals produce wide views that defer to equilibrium.

**Minimum Variance**: Minimize portfolio volatility without return assumptions. Useful in uncertain regimes where return forecasts are unreliable, which is precisely when an agent might select this method over mean-variance.

**Mean-CVaR (Conditional Value-at-Risk)**: Minimize tail risk using the Rockafellar-Uryasev linear programming formulation. CVaR (expected shortfall) is a coherent risk measure that accounts for the magnitude of losses beyond the confidence threshold, not just the probability of exceeding it. Solved via CVXPY with the CLARABEL solver.

### 8.2 Execution Pipeline

Position sizing flows through four stages: the portfolio optimizer determines target weights, the execution engine converts weights to share quantities, the cost model estimates commissions and slippage, and the broker receives the order.

Broker positions are the source of truth. The system reconciles against broker state every cycle rather than maintaining its own position ledger. This eliminates an entire class of reconciliation bugs where local state drifts from reality due to partial fills, network failures, or manual intervention.

---

## 9. Open Source and Extensibility

Icarus is released under the Apache 2.0 license. The complete framework is open source: strategy plugin interface, all nine engines (risk, execution, portfolio optimization, backtest, confluence, strategy loading, cost model, sensitivity, quantum), the runner and worker daemons, the Control Room UI (React 19), agent definitions, and the full Docker Compose stack.

### 9.1 Extending Icarus

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
        return [Signal(
            ticker="AAPL",
            direction="long",
            confidence=0.75,
            metadata={"reason": "breakout"}
        )]
```

Place the file in `api/strategies/` or a configured plugin directory. The strategy engine discovers and loads it on next startup.

### 9.2 Key Architecture Decisions

**Broker as source of truth**: Position state is always fetched from the broker, never reconstructed from local order history.

**Independent coroutines with fault isolation**: The runner's four loops (execution, snapshots, flatten, VIX) run concurrently with independent error handling. One loop failing does not crash the others.

**Risk outside the signal path**: The risk engine evaluates the full portfolio context, not individual signals in isolation. It has veto power, not advisory power.

**CVaR over VaR**: Portfolio optimization uses Conditional Value-at-Risk rather than Value-at-Risk for tail risk measurement because CVaR is subadditive (diversification always reduces it) and captures loss magnitude, not just probability.

---

## 10. Conclusion

The three-gateway architecture provides a framework for combining the strengths of rule-based trading, machine learning, and AI agents while mitigating the weaknesses of each approach in isolation.

Rules provide coverage and speed. ML provides statistical filtering. Agents provide judgment and adaptation. Risk controls provide hard boundaries that no layer can override.

The system is designed for composition, not replacement. Each gateway can operate independently with meaningful results. Adding layers compounds performance primarily through noise reduction and drawdown avoidance rather than raw return generation. The errors at each layer are qualitatively different and therefore uncorrelated, which makes the combined system more robust than any individual layer regardless of how sophisticated that layer becomes.

Icarus demonstrates that the most impactful use of AI agents in quantitative trading is not signal generation but meta-cognition: the ability to evaluate whether a system's outputs should be trusted given current conditions. When markets are stable and regime is clear, rules and ML are sufficient. When conditions are ambiguous, transitional, or unprecedented, the agent layer's judgment becomes the margin between a controlled drawdown and an uncontrolled one.

---

*Icarus is developed by Venture Chain. Source code available at github.com/Venture-Chain/icarus.*
*For questions, contact research@venturechain.co.*
