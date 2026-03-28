import { useState, useEffect } from 'react'

interface Strategy {
  id: number
  name: string
  mode: string
  status: string
  risk_budget: number
  description: string
}

interface Props {
  apiUrl: string
}

export default function StrategyCommand({ apiUrl }: Props) {
  const [strategies, setStrategies] = useState<Strategy[]>([])

  useEffect(() => {
    const fetchStrategies = async () => {
      try {
        const resp = await fetch(`${apiUrl}/strategies/`)
        const data = await resp.json()
        setStrategies(data.strategies || [])
      } catch {}
    }
    fetchStrategies()
    const id = setInterval(fetchStrategies, 30000)
    return () => clearInterval(id)
  }, [apiUrl])

  const modeClass = (mode: string) => {
    if (mode === 'live') return 'live'
    if (mode === 'backtest') return 'backtest'
    return 'paper'
  }

  return (
    <div>
      <h2>Strategy Command</h2>
      {strategies.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">[--]</div>
          <div className="empty-state-text">No strategies loaded</div>
          <div className="empty-state-sub">Deploy a strategy to get started</div>
        </div>
      ) : (
        strategies.map(s => (
          <div key={s.id} className="strategy-row">
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="strategy-name">{s.name}</div>
              {s.description && (
                <div className="strategy-desc">{s.description}</div>
              )}
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px' }}>
                <div className="strategy-budget-bar">
                  <div
                    className="strategy-budget-fill"
                    style={{ width: `${Math.min(s.risk_budget, 100)}%` }}
                  />
                </div>
                <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace', fontVariantNumeric: 'tabular-nums' }}>
                  {s.risk_budget}%
                </span>
              </div>
            </div>
            <div className="strategy-meta">
              <span className={`pill ${modeClass(s.mode)}`}>{s.mode}</span>
              <span className={`status-dot ${s.status === 'active' ? 'active' : 'inactive'}`} />
            </div>
          </div>
        ))
      )}
    </div>
  )
}
