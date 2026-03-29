import { useState, useEffect } from 'react'

interface QuantumStatus {
  enabled: boolean
  hlquantum_installed: boolean
  hlquantum_version: string | null
  backend: string
  shots: number
  available_models: string[]
}

interface QuantumResult {
  model: string
  quantum: Record<string, number>
  classical: Record<string, number>
  circuit: {
    qubits: number
    circuit_depth: number
    shots: number
    execution_time_ms: number
    backend: string
  }
  tickers?: string[]
  parameters?: Record<string, number>
  confidence_level?: number
}

interface Props {
  apiUrl: string
}

type Model = 'portfolio' | 'risk' | 'pricing'

const MODEL_LABELS: Record<Model, string> = {
  portfolio: 'Portfolio Optimization',
  risk: 'Risk Analysis (VaR)',
  pricing: 'Option Pricing',
}

const MODEL_DESCRIPTIONS: Record<Model, string> = {
  portfolio: 'QAOA finds optimal asset allocation as a combinatorial problem. Classical comparison: mean-variance (Markowitz).',
  risk: 'Amplitude estimation for quantum Monte Carlo VaR/CVaR. Classical comparison: parametric variance-covariance.',
  pricing: 'Amplitude estimation encodes payoff distribution for European call pricing. Classical comparison: Black-Scholes.',
}

const MODEL_ENDPOINTS: Record<Model, string> = {
  portfolio: '/quantum/optimize',
  risk: '/quantum/risk',
  pricing: '/quantum/price',
}

function formatValue(v: unknown): string {
  if (typeof v === 'object' && v !== null) {
    return Object.entries(v as Record<string, number>)
      .map(([t, w]) => `${t}: ${typeof w === 'number' ? w.toFixed(4) : w}`)
      .join(', ')
  }
  if (typeof v === 'number') return v.toFixed(4)
  return String(v)
}

export default function QuantumLab({ apiUrl }: Props) {
  const [status, setStatus] = useState<QuantumStatus | null>(null)
  const [selectedModel, setSelectedModel] = useState<Model>('portfolio')
  const [result, setResult] = useState<QuantumResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${apiUrl}/quantum/status`)
      .then(r => r.json())
      .then(setStatus)
      .catch(() => setStatus(null))
  }, [apiUrl])

  const runModel = async () => {
    setRunning(true)
    setError(null)
    setResult(null)
    try {
      const resp = await fetch(`${apiUrl}${MODEL_ENDPOINTS[selectedModel]}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}))
        throw new Error(data.detail || `HTTP ${resp.status}`)
      }
      const data = await resp.json()
      setResult(data.result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setRunning(false)
    }
  }

  if (!status) return null

  const online = status.enabled && status.hlquantum_installed

  if (!online) {
    return (
      <div className="quantum-offline">
        <div className="quantum-offline-icon">[Q]</div>
        <div className="quantum-offline-title">Quantum Lab Offline</div>
        <div className="quantum-offline-sub">
          {!status.enabled ? 'Set QUANTUM_ENABLED=true to activate' : 'Run: pip install hlquantum'}
        </div>
      </div>
    )
  }

  return (
    <div className="quantum-page">
      <div className="quantum-sidebar">
        <div className="quantum-sidebar-header">
          <span className={`quantum-status-badge online`}>ONLINE</span>
          <div className="quantum-version">
            HLQuantum v{status.hlquantum_version}
          </div>
          <div className="quantum-version">
            {status.backend} / {status.shots} shots
          </div>
        </div>

        <div className="quantum-sidebar-models">
          <div className="quantum-sidebar-label">MODELS</div>
          {(Object.keys(MODEL_LABELS) as Model[]).map(m => (
            <button
              key={m}
              className={`quantum-model-btn ${selectedModel === m ? 'active' : ''}`}
              onClick={() => { setSelectedModel(m); setResult(null); setError(null) }}
            >
              {MODEL_LABELS[m]}
            </button>
          ))}
        </div>

        <button
          className="quantum-run-btn"
          onClick={runModel}
          disabled={running}
        >
          {running ? 'RUNNING...' : 'RUN MODEL'}
        </button>
      </div>

      <div className="quantum-main">
        <div className="quantum-main-header">
          <h2 className="quantum-main-title">{MODEL_LABELS[selectedModel]}</h2>
          <div className="quantum-main-desc">{MODEL_DESCRIPTIONS[selectedModel]}</div>
        </div>

        {error && (
          <div className="quantum-error">{error}</div>
        )}

        {!result && !error && (
          <div className="quantum-empty">
            <div className="quantum-empty-icon">[Q]</div>
            <div className="quantum-empty-text">Select a model and click Run</div>
          </div>
        )}

        {result && (
          <div className="quantum-results">
            <div className="quantum-comparison">
              <div className="quantum-col quantum-col-quantum">
                <div className="quantum-col-header quantum-accent">QUANTUM</div>
                {Object.entries(result.quantum).map(([k, v]) => (
                  <div key={k} className="quantum-metric">
                    <span className="quantum-metric-label">{k.replace(/_/g, ' ')}</span>
                    <span className="quantum-metric-value quantum-accent">
                      {formatValue(v)}
                    </span>
                  </div>
                ))}
              </div>
              <div className="quantum-col quantum-col-classical">
                <div className="quantum-col-header classical-accent">CLASSICAL</div>
                {Object.entries(result.classical).map(([k, v]) => (
                  <div key={k} className="quantum-metric">
                    <span className="quantum-metric-label">{k.replace(/_/g, ' ')}</span>
                    <span className="quantum-metric-value classical-accent">
                      {formatValue(v)}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="quantum-circuit-panel">
              <div className="quantum-circuit-title">CIRCUIT METADATA</div>
              <div className="quantum-circuit-grid">
                <div className="quantum-circuit-stat">
                  <div className="quantum-circuit-stat-value">{result.circuit.qubits}</div>
                  <div className="quantum-circuit-stat-label">Qubits</div>
                </div>
                <div className="quantum-circuit-stat">
                  <div className="quantum-circuit-stat-value">{result.circuit.circuit_depth}</div>
                  <div className="quantum-circuit-stat-label">Depth</div>
                </div>
                <div className="quantum-circuit-stat">
                  <div className="quantum-circuit-stat-value">{result.circuit.shots}</div>
                  <div className="quantum-circuit-stat-label">Shots</div>
                </div>
                <div className="quantum-circuit-stat">
                  <div className="quantum-circuit-stat-value">{result.circuit.execution_time_ms.toFixed(0)}ms</div>
                  <div className="quantum-circuit-stat-label">Execution</div>
                </div>
                <div className="quantum-circuit-stat">
                  <div className="quantum-circuit-stat-value">{result.circuit.backend}</div>
                  <div className="quantum-circuit-stat-label">Backend</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
