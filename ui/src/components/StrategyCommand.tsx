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
    const interval = setInterval(fetchStrategies, 30000)
    return () => clearInterval(interval)
  }, [apiUrl])

  return (
    <div>
      <h2>Strategy Command</h2>
      {strategies.length === 0 ? (
        <div style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
          No active strategies
        </div>
      ) : (
        strategies.map(s => (
          <div key={s.id} className="strategy-row">
            <div>
              <div className="strategy-name">{s.name}</div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                {s.description}
              </div>
            </div>
            <div className="strategy-meta">
              <span className={`pill ${s.mode}`}>{s.mode}</span>
              <span className={`status-dot ${s.status === 'active' ? 'active' : 'inactive'}`} />
            </div>
          </div>
        ))
      )}
    </div>
  )
}
