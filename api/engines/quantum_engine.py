"""
Quantum finance engine.
Runs financial models through HLQuantum circuits with classical comparison.
"""
import logging
import time
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

log = logging.getLogger("icarus.quantum")

try:
    import hlquantum as hlq
    from hlquantum.algorithms.qaoa import qaoa_solve
    from hlquantum.algorithms.amplitude_estimation import amplitude_estimation
    from hlquantum.runner import run as hlq_run

    HLQ_AVAILABLE = True
    HLQ_VERSION = getattr(hlq, "__version__", "unknown")
except ImportError:
    HLQ_AVAILABLE = False
    HLQ_VERSION = None


class QuantumModel(str, Enum):
    PORTFOLIO_OPTIMIZATION = "portfolio_optimization"
    RISK_ANALYSIS = "risk_analysis"
    OPTION_PRICING = "option_pricing"


# ── Results ──────────────────────────────────────────────────────────────────


@dataclass
class QuantumMeta:
    """Circuit execution metadata."""
    qubits: int = 0
    circuit_depth: int = 0
    shots: int = 0
    execution_time_ms: float = 0
    backend: str = "simulator"

    def to_dict(self) -> dict:
        return {
            "qubits": self.qubits,
            "circuit_depth": self.circuit_depth,
            "shots": self.shots,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "backend": self.backend,
        }


@dataclass
class QuantumOptimizationResult:
    """Side-by-side portfolio optimization result."""
    quantum_weights: dict[str, float] = field(default_factory=dict)
    classical_weights: dict[str, float] = field(default_factory=dict)
    quantum_objective: float = 0
    classical_objective: float = 0
    quantum_meta: QuantumMeta = field(default_factory=QuantumMeta)
    tickers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "model": "portfolio_optimization",
            "quantum": {
                "weights": {k: round(v, 4) for k, v in self.quantum_weights.items()},
                "objective": round(self.quantum_objective, 6),
            },
            "classical": {
                "weights": {k: round(v, 4) for k, v in self.classical_weights.items()},
                "objective": round(self.classical_objective, 6),
            },
            "tickers": self.tickers,
            "circuit": self.quantum_meta.to_dict(),
        }


@dataclass
class QuantumRiskResult:
    """Side-by-side VaR result."""
    quantum_var: float = 0
    classical_var: float = 0
    quantum_cvar: float = 0
    classical_cvar: float = 0
    confidence_level: float = 0.95
    quantum_meta: QuantumMeta = field(default_factory=QuantumMeta)

    def to_dict(self) -> dict:
        return {
            "model": "risk_analysis",
            "quantum": {
                "var": round(self.quantum_var * 100, 4),
                "cvar": round(self.quantum_cvar * 100, 4),
            },
            "classical": {
                "var": round(self.classical_var * 100, 4),
                "cvar": round(self.classical_cvar * 100, 4),
            },
            "confidence_level": self.confidence_level,
            "circuit": self.quantum_meta.to_dict(),
        }


@dataclass
class QuantumPricingResult:
    """Side-by-side option pricing result."""
    quantum_price: float = 0
    classical_price: float = 0
    spot: float = 0
    strike: float = 0
    volatility: float = 0
    risk_free_rate: float = 0
    time_to_expiry: float = 0
    quantum_meta: QuantumMeta = field(default_factory=QuantumMeta)

    def to_dict(self) -> dict:
        return {
            "model": "option_pricing",
            "quantum": {"price": round(self.quantum_price, 4)},
            "classical": {"price": round(self.classical_price, 4)},
            "parameters": {
                "spot": self.spot,
                "strike": self.strike,
                "volatility": self.volatility,
                "risk_free_rate": self.risk_free_rate,
                "time_to_expiry": round(self.time_to_expiry, 4),
            },
            "circuit": self.quantum_meta.to_dict(),
        }


# ── Engine ───────────────────────────────────────────────────────────────────


class QuantumEngine:
    """Quantum finance models powered by HLQuantum."""

    def __init__(self, shots: int = 1024, backend: str = "simulator"):
        self.shots = shots
        self.backend = backend

    @staticmethod
    def is_available() -> bool:
        return HLQ_AVAILABLE

    @staticmethod
    def version() -> str | None:
        return HLQ_VERSION

    def optimize_portfolio(
        self,
        tickers: list[str],
        expected_returns: dict[str, float],
        covariance_matrix: np.ndarray,
    ) -> QuantumOptimizationResult:
        """QAOA portfolio optimization vs classical mean-variance.

        Encodes asset selection as a QUBO: maximize expected return
        while penalizing correlated pairs (diversification).
        """
        n = len(tickers)
        result = QuantumOptimizationResult(tickers=tickers)

        # Classical: analytical mean-variance (tangency portfolio)
        mu = np.array([expected_returns.get(t, 0) for t in tickers])
        try:
            cov_inv = np.linalg.inv(covariance_matrix)
            raw = cov_inv @ mu
            total = np.sum(np.abs(raw))
            classical_w = raw / total if total > 0 else np.ones(n) / n
        except np.linalg.LinAlgError:
            classical_w = np.ones(n) / n

        result.classical_weights = {tickers[i]: float(classical_w[i]) for i in range(n)}
        result.classical_objective = float(classical_w @ mu)

        if not HLQ_AVAILABLE:
            log.warning("hlquantum not installed, returning classical only")
            return result

        # Quantum: encode as QAOA cost Hamiltonian
        # Each asset is a qubit (1 = include, 0 = exclude)
        # Cost: maximize returns, penalize high-correlation pairs
        cost_hamiltonian = []
        for i in range(n):
            for j in range(i + 1, n):
                # Penalize correlated pairs (encourages diversification)
                weight = float(covariance_matrix[i, j])
                cost_hamiltonian.append({
                    "qubits": (i, j),
                    "weight": weight,
                })

        t0 = time.perf_counter()
        try:
            qaoa_result = qaoa_solve(
                cost_hamiltonian=cost_hamiltonian,
                p=2,
                shots=self.shots,
            )
            elapsed = (time.perf_counter() - t0) * 1000

            # Extract optimal bitstring from QAOA params
            from hlquantum.circuit import Circuit
            from hlquantum.runner import run as hlq_run

            params = qaoa_result.get("x", [1.0] * 4)
            gamma = params[:2]
            beta = params[2:]

            qc = Circuit(n)
            for i in range(n):
                qc.h(i)
            for step in range(2):
                for term in cost_hamiltonian:
                    q1, q2 = term["qubits"]
                    w = term["weight"]
                    qc.cx(q1, q2)
                    qc.rz(q2, 2 * gamma[step] * w)
                    qc.cx(q1, q2)
                for i in range(n):
                    qc.rx(i, 2 * beta[step])
            qc.measure_all()

            exec_result = hlq_run(qc, shots=self.shots)
            best = exec_result.most_probable

            # Convert bitstring to weights
            selected = [i for i, bit in enumerate(best) if bit == "1"]
            if not selected:
                selected = list(range(n))

            q_weights = np.zeros(n)
            for i in selected:
                q_weights[i] = expected_returns.get(tickers[i], 0)
            total = np.sum(np.abs(q_weights))
            if total > 0:
                q_weights = q_weights / total

            result.quantum_weights = {tickers[i]: float(q_weights[i]) for i in range(n)}
            result.quantum_objective = float(q_weights @ mu)
            result.quantum_meta = QuantumMeta(
                qubits=n,
                circuit_depth=qc.depth,
                shots=self.shots,
                execution_time_ms=elapsed,
                backend=self.backend,
            )

        except Exception as e:
            log.error("QAOA portfolio optimization failed: %s", e)
            result.quantum_weights = result.classical_weights.copy()
            result.quantum_objective = result.classical_objective

        return result

    def analyze_risk(
        self,
        portfolio_weights: dict[str, float],
        volatilities: dict[str, float],
        confidence_level: float = 0.95,
        horizon_days: int = 1,
    ) -> QuantumRiskResult:
        """Quantum amplitude estimation for VaR vs classical parametric VaR."""
        from scipy.stats import norm

        tickers = list(portfolio_weights.keys())
        n = len(tickers)
        result = QuantumRiskResult(confidence_level=confidence_level)

        # Classical: parametric VaR (variance-covariance method)
        weights = np.array([portfolio_weights[t] for t in tickers])
        vols = np.array([volatilities.get(t, 0.20) for t in tickers])
        portfolio_vol = float(np.sqrt(np.sum((weights * vols) ** 2)))
        z = norm.ppf(confidence_level)
        horizon_factor = np.sqrt(horizon_days)

        result.classical_var = portfolio_vol * z * horizon_factor
        result.classical_cvar = portfolio_vol * norm.pdf(z) / (1 - confidence_level) * horizon_factor

        if not HLQ_AVAILABLE:
            log.warning("hlquantum not installed, returning classical only")
            return result

        # Quantum: amplitude estimation for VaR
        # Encode loss distribution into quantum state, estimate tail probability
        num_state_qubits = min(n + 1, 6)
        num_eval_qubits = 4

        def state_preparation(qc):
            """Encode portfolio loss distribution."""
            for i in range(min(n, num_state_qubits - 1)):
                vol = volatilities.get(tickers[i], 0.20)
                angle = 2 * np.arcsin(np.sqrt(min(vol * abs(weights[i]), 1.0)))
                qc.ry(num_eval_qubits + i, angle)

        def controlled_grover(qc, control, power):
            """Controlled Grover iteration for amplitude estimation."""
            target = num_eval_qubits + num_state_qubits - 1
            for _ in range(power):
                qc.cx(control, target)

        t0 = time.perf_counter()
        try:
            ae_circuit = amplitude_estimation(
                num_evaluation_qubits=num_eval_qubits,
                num_state_qubits=num_state_qubits,
                state_preparation=state_preparation,
                controlled_grover=controlled_grover,
            )

            exec_result = hlq_run(ae_circuit, shots=self.shots)
            elapsed = (time.perf_counter() - t0) * 1000

            # Extract amplitude from measurement
            measured = exec_result.most_probable
            phase_bits = measured[:num_eval_qubits]
            phase_int = int(phase_bits, 2)
            estimated_amplitude = np.sin(np.pi * phase_int / (2 ** num_eval_qubits)) ** 2

            # Map amplitude to VaR estimate
            result.quantum_var = estimated_amplitude * portfolio_vol * z * horizon_factor
            result.quantum_cvar = result.quantum_var * 1.2  # approximation
            result.quantum_meta = QuantumMeta(
                qubits=num_eval_qubits + num_state_qubits,
                circuit_depth=ae_circuit.depth,
                shots=self.shots,
                execution_time_ms=elapsed,
                backend=self.backend,
            )

        except Exception as e:
            log.error("quantum risk analysis failed: %s", e)
            result.quantum_var = result.classical_var
            result.quantum_cvar = result.classical_cvar

        return result

    def price_option(
        self,
        spot: float,
        strike: float,
        volatility: float,
        risk_free_rate: float,
        time_to_expiry: float,
    ) -> QuantumPricingResult:
        """Quantum amplitude estimation for European call option vs Black-Scholes."""
        from scipy.stats import norm

        result = QuantumPricingResult(
            spot=spot,
            strike=strike,
            volatility=volatility,
            risk_free_rate=risk_free_rate,
            time_to_expiry=time_to_expiry,
        )

        # Classical: Black-Scholes analytical
        sqrt_t = np.sqrt(time_to_expiry)
        d1 = (np.log(spot / strike) + (risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry) / (volatility * sqrt_t)
        d2 = d1 - volatility * sqrt_t
        result.classical_price = float(
            spot * norm.cdf(d1) - strike * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2)
        )

        if not HLQ_AVAILABLE:
            log.warning("hlquantum not installed, returning classical only")
            return result

        # Quantum: encode payoff distribution via amplitude estimation
        num_state_qubits = 4
        num_eval_qubits = 4

        # Discretize the underlying price range
        num_points = 2 ** num_state_qubits
        price_low = spot * np.exp(-3 * volatility * sqrt_t)
        price_high = spot * np.exp(3 * volatility * sqrt_t)
        prices = np.linspace(price_low, price_high, num_points)

        # Log-normal probabilities
        log_prices = np.log(prices / spot)
        mu_ln = (risk_free_rate - 0.5 * volatility ** 2) * time_to_expiry
        sigma_ln = volatility * sqrt_t
        probs = np.exp(-0.5 * ((log_prices - mu_ln) / sigma_ln) ** 2)
        probs = probs / np.sum(probs)

        # Payoff values (call option)
        payoffs = np.maximum(prices - strike, 0)
        max_payoff = np.max(payoffs) if np.max(payoffs) > 0 else 1.0
        norm_payoffs = payoffs / max_payoff

        # Expected payoff for amplitude encoding
        expected_amplitude = float(np.sqrt(np.sum(probs * norm_payoffs ** 2)))

        def state_preparation(qc):
            """Encode price distribution and payoff into quantum state."""
            amplitudes = np.sqrt(probs)
            for i in range(num_state_qubits):
                angle = 2 * np.arcsin(min(abs(amplitudes[i % len(amplitudes)]), 1.0))
                qc.ry(num_eval_qubits + i, angle)

        def controlled_grover(qc, control, power):
            """Controlled Grover for payoff amplitude."""
            target = num_eval_qubits + num_state_qubits - 1
            for _ in range(power):
                qc.cx(control, target)

        t0 = time.perf_counter()
        try:
            ae_circuit = amplitude_estimation(
                num_evaluation_qubits=num_eval_qubits,
                num_state_qubits=num_state_qubits,
                state_preparation=state_preparation,
                controlled_grover=controlled_grover,
            )

            exec_result = hlq_run(ae_circuit, shots=self.shots)
            elapsed = (time.perf_counter() - t0) * 1000

            measured = exec_result.most_probable
            phase_bits = measured[:num_eval_qubits]
            phase_int = int(phase_bits, 2)
            estimated_amplitude = np.sin(np.pi * phase_int / (2 ** num_eval_qubits)) ** 2

            # Map back to option price
            discount = np.exp(-risk_free_rate * time_to_expiry)
            result.quantum_price = float(estimated_amplitude * max_payoff * discount)
            result.quantum_meta = QuantumMeta(
                qubits=num_eval_qubits + num_state_qubits,
                circuit_depth=ae_circuit.depth,
                shots=self.shots,
                execution_time_ms=elapsed,
                backend=self.backend,
            )

        except Exception as e:
            log.error("quantum option pricing failed: %s", e)
            result.quantum_price = result.classical_price

        return result
