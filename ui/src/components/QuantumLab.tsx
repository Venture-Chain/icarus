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

const MODEL_ENDPOINTS: Record<Model, string> = {
  portfolio: '/quantum/optimize',
  risk: '/quantum/risk',
  pricing: '/quantum/price',
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

  return (
    <>
      <div className="panel-header-row">
        <h2>Quantum Lab</h2>
        <span className={`quantum-status-badge ${online ? 'online' : 'offline'}`}>
          {online ? 'ONLINE' : 'OFFLINE'}
        </span>
      </div>

      {!online ? (
        <div className="empty-state" style={{ flex: 'none', padding: '20px 16px' }}>
          <div className="empty-state-icon">[Q]</div>
          <div className="empty-state-text">
            {!status.enabled ? 'Quantum module disabled' : 'HLQuantum not installed'}
          </div>
          <div className="empty-state-sub">
            {!status.enabled
              ? 'Set QUANTUM_ENABLED=true'
              : 'pip install hlquantum'}
          </div>
        </div>
      ) : (
        <div className="quantum-content">
          <div className="quantum-version">
            HLQuantum v{status.hlquantum_version} / {status.backend} / {status.shots} shots
          </div>

          <div className="quantum-models">
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
            {running ? 'RUNNING...' : 'RUN QUANTUM MODEL'}
          </button>

          {error && (
            <div className="quantum-error">{error}</div>
          )}

          {result && (
            <div className="quantum-results">
              <div className="quantum-comparison">
                <div className="quantum-col">
                  <div className="quantum-col-header quantum-accent">QUANTUM</div>
                  {Object.entries(result.quantum).map(([k, v]) => (
                    <div key={k} className="quantum-metric">
                      <span className="quantum-metric-label">{k.replace(/_/g, ' ')}</span>
                      <span className="quantum-metric-value quantum-accent">
                        {typeof v === 'object' && v !== null
                          ? Object.entries(v as Record<string, number>).map(([t, w]) => `${t}: ${w}`).join(', ')
                          : typeof v === 'number' ? v.toFixed(4) : String(v)}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="quantum-col">
                  <div className="quantum-col-header classical-accent">CLASSICAL</div>
                  {Object.entries(result.classical).map(([k, v]) => (
                    <div key={k} className="quantum-metric">
                      <span className="quantum-metric-label">{k.replace(/_/g, ' ')}</span>
                      <span className="quantum-metric-value classical-accent">
                        {typeof v === 'object' && v !== null
                          ? Object.entries(v as Record<string, number>).map(([t, w]) => `${t}: ${w}`).join(', ')
                          : typeof v === 'number' ? v.toFixed(4) : String(v)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="quantum-circuit-info">
                <span>{result.circuit.qubits}q</span>
                <span>depth {result.circuit.circuit_depth}</span>
                <span>{result.circuit.shots} shots</span>
                <span>{result.circuit.execution_time_ms.toFixed(0)}ms</span>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  )
}
