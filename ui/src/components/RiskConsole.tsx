import { useState, useEffect } from 'react'

interface RiskData {
  var_95: number
  cvar_95: number
  max_drawdown: number
  current_drawdown: number
  net_exposure: number
  gross_exposure: number
  beta: number
  sharpe: number
  portfolio_value: number
  largest_position_pct: number
}

interface Props {
  apiUrl: string
}

const defaultRisk: RiskData = {
  var_95: 0, cvar_95: 0, max_drawdown: 0, current_drawdown: 0,
  net_exposure: 0, gross_exposure: 0, beta: 0, sharpe: 0,
  portfolio_value: 0, largest_position_pct: 0,
}

function LimitBar({ value, max, label }: { value: number; max: number; label: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  const severity = pct > 90 ? 'breach' : pct > 70 ? 'warning' : 'ok'

  return (
    <div className="metric">
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span className="metric-label">{label}</span>
          <span className="metric-value" style={{ fontSize: '12px' }}>
            {value.toFixed(1)}% / {max.toFixed(0)}%
          </span>
        </div>
        <div className="limit-bar">
          <div className={`limit-bar-fill ${severity}`} style={{ width: `${pct}%` }} />
        </div>
      </div>
    </div>
  )
}

export default function RiskConsole({ apiUrl }: Props) {
  const [risk, setRisk] = useState<RiskData>(defaultRisk)

  useEffect(() => {
    const fetchRisk = async () => {
      try {
        const resp = await fetch(`${apiUrl}/portfolio/risk`)
        const data = await resp.json()
        setRisk(data)
      } catch {}
    }
    fetchRisk()
    const interval = setInterval(fetchRisk, 10000)
    return () => clearInterval(interval)
  }, [apiUrl])

  return (
    <div>
      <h2>Risk Console</h2>
      <div className="metric">
        <span className="metric-label">Portfolio Value</span>
        <span className="metric-value">${risk.portfolio_value.toLocaleString()}</span>
      </div>
      <div className="metric">
        <span className="metric-label">VaR (95%)</span>
        <span className="metric-value negative">${risk.var_95.toLocaleString()}</span>
      </div>
      <div className="metric">
        <span className="metric-label">Sharpe</span>
        <span className={`metric-value ${risk.sharpe > 1 ? 'positive' : risk.sharpe < 0 ? 'negative' : ''}`}>
          {risk.sharpe.toFixed(2)}
        </span>
      </div>
      <div className="metric">
        <span className="metric-label">Beta</span>
        <span className="metric-value">{risk.beta.toFixed(2)}</span>
      </div>
      <LimitBar value={risk.current_drawdown} max={10} label="Drawdown" />
      <LimitBar value={risk.net_exposure * 100} max={50} label="Net Exposure" />
      <LimitBar value={risk.gross_exposure * 100} max={200} label="Gross Exposure" />
      <LimitBar value={risk.largest_position_pct} max={10} label="Largest Position" />
    </div>
  )
}
