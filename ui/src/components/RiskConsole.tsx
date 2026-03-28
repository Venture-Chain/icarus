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

interface LimitBarProps {
  value: number
  max: number
  label: string
  valueLabel?: string
}

function LimitBar({ value, max, label, valueLabel }: LimitBarProps) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  const severity = pct > 90 ? 'breach' : pct > 70 ? 'warning' : 'ok'
  const display = valueLabel ?? `${value.toFixed(1)}% / ${max.toFixed(0)}%`

  return (
    <div className="limit-bar-row">
      <div className="limit-bar-header">
        <span className="metric-label">{label}</span>
        <span className="metric-value" style={{ fontSize: '11px' }}>{display}</span>
      </div>
      <div className="limit-bar">
        <div className={`limit-bar-fill ${severity}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function secondsAgo(ts: number): string {
  const s = Math.floor((Date.now() - ts) / 1000)
  if (s < 60) return `${s}s ago`
  return `${Math.floor(s / 60)}m ago`
}

export default function RiskConsole({ apiUrl }: Props) {
  const [risk, setRisk] = useState<RiskData>(defaultRisk)
  const [lastFetch, setLastFetch] = useState<number>(Date.now())
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const fetchRisk = async () => {
      try {
        const resp = await fetch(`${apiUrl}/portfolio/risk`)
        const data = await resp.json()
        setRisk({ ...defaultRisk, ...data })
        setLastFetch(Date.now())
      } catch {}
    }
    fetchRisk()
    const id = setInterval(fetchRisk, 10000)
    return () => clearInterval(id)
  }, [apiUrl])

  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 5000)
    return () => clearInterval(id)
  }, [])

  const sharpeClass = risk.sharpe > 1 ? 'positive' : risk.sharpe < 0 ? 'negative' : ''

  return (
    <div>
      <h2>Risk Console</h2>

      <div className="metric-section-label">Risk Metrics</div>
      <div className="metric">
        <span className="metric-label">VaR (95%)</span>
        <span className="metric-value negative">${risk.var_95.toLocaleString()}</span>
      </div>
      <div className="metric">
        <span className="metric-label">CVaR (95%)</span>
        <span className="metric-value negative">${risk.cvar_95.toLocaleString()}</span>
      </div>

      <div className="metric-separator" />
      <div className="metric-section-label">Performance</div>
      <div className="metric">
        <span className="metric-label">Sharpe Ratio</span>
        <span className={`metric-value ${sharpeClass}`}>{risk.sharpe.toFixed(2)}</span>
      </div>
      <div className="metric">
        <span className="metric-label">Beta</span>
        <span className="metric-value">{risk.beta.toFixed(2)}</span>
      </div>
      <div className="metric">
        <span className="metric-label">Max Drawdown</span>
        <span className="metric-value negative">{risk.max_drawdown.toFixed(1)}%</span>
      </div>

      <div className="metric-separator" />
      <div className="metric-section-label">Limits</div>
      <LimitBar value={risk.current_drawdown} max={10} label="Drawdown" />
      <LimitBar value={risk.net_exposure * 100} max={50} label="Net Exposure" />
      <LimitBar value={risk.gross_exposure * 100} max={200} label="Gross Exposure" />
      <LimitBar value={risk.largest_position_pct} max={10} label="Largest Position" />

      <div className="last-updated" key={tick}>
        Updated {secondsAgo(lastFetch)}
      </div>
    </div>
  )
}
