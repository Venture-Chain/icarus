import { useState, useEffect } from 'react'

interface RiskData {
  var_95: number
  cvar_95: number
  sharpe: number
  beta: number
  max_drawdown: number
  drawdown_pct: number
  drawdown_limit: number
  net_exposure_pct: number
  net_exposure_limit: number
  gross_exposure_pct: number
  gross_exposure_limit: number
  largest_position_pct: number
  largest_position_limit: number
}

interface Props {
  apiUrl: string
  selectedAccount: string
}

const defaultRisk: RiskData = {
  var_95: 0,
  cvar_95: 0,
  sharpe: 0,
  beta: 0,
  max_drawdown: 0,
  drawdown_pct: 0,
  drawdown_limit: 10,
  net_exposure_pct: 0,
  net_exposure_limit: 50,
  gross_exposure_pct: 0,
  gross_exposure_limit: 200,
  largest_position_pct: 0,
  largest_position_limit: 10,
}

interface LimitBarProps {
  value: number
  max: number
  label: string
  currentLabel: string
}

function LimitBar({ value, max, label, currentLabel }: LimitBarProps) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  const severity = pct > 85 ? 'breach' : pct > 60 ? 'warning' : 'ok'

  return (
    <div className="limit-bar-row">
      <div className="limit-bar-header">
        <span className="metric-label">{label}</span>
        <span className="metric-value" style={{ fontSize: '12px' }}>{currentLabel}</span>
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

export default function RiskConsole({ apiUrl, selectedAccount }: Props) {
  const [risk, setRisk] = useState<RiskData>(defaultRisk)
  const [lastFetch, setLastFetch] = useState<number>(Date.now())
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const fetchRisk = async () => {
      try {
        const params = selectedAccount ? `?account_id=${selectedAccount}` : ''
        const resp = await fetch(`${apiUrl}/portfolio/risk${params}`)
        const data = await resp.json()
        setRisk({ ...defaultRisk, ...data })
        setLastFetch(Date.now())
      } catch (err) {
        console.error('RiskConsole fetch failed:', err)
      }
    }
    fetchRisk()
    const id = setInterval(fetchRisk, 10000)
    return () => clearInterval(id)
  }, [apiUrl, selectedAccount])

  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 5000)
    return () => clearInterval(id)
  }, [])

  const sharpeClass = risk.sharpe > 1 ? 'positive' : risk.sharpe < 0 ? 'negative' : 'warning'

  return (
    <>
      <h2>Risk Console</h2>

      <div className="risk-hero">
        <div className="risk-hero-item">
          <div className="risk-hero-label">VaR (95%)</div>
          <div className="risk-hero-value">${risk.var_95.toLocaleString()}</div>
        </div>
        <div className="risk-hero-item">
          <div className="risk-hero-label">CVaR (95%)</div>
          <div className="risk-hero-value">${risk.cvar_95.toLocaleString()}</div>
        </div>
      </div>

      <div className="metric-section-label">Performance</div>
      <div className="metric">
        <span className="metric-label">Sharpe Ratio</span>
        <span className={`metric-value ${sharpeClass}`} style={{ fontSize: '20px' }}>
          {risk.sharpe.toFixed(2)}
        </span>
      </div>
      <div className="metric">
        <span className="metric-label">Beta</span>
        <span className="metric-value" style={{ fontSize: '20px' }}>
          {risk.beta.toFixed(2)}
        </span>
      </div>
      <div className="metric">
        <span className="metric-label">Max Drawdown</span>
        <span className="metric-value negative" style={{ fontSize: '20px' }}>
          {risk.max_drawdown.toFixed(1)}%
        </span>
      </div>

      <div className="metric-separator" />
      <div className="metric-section-label">Limits</div>

      <LimitBar
        value={risk.drawdown_pct}
        max={risk.drawdown_limit}
        label="Drawdown"
        currentLabel={`${risk.drawdown_pct.toFixed(1)}% / ${risk.drawdown_limit.toFixed(0)}%`}
      />
      <LimitBar
        value={risk.net_exposure_pct}
        max={risk.net_exposure_limit}
        label="Net Exposure"
        currentLabel={`${risk.net_exposure_pct.toFixed(1)}% / ${risk.net_exposure_limit.toFixed(0)}%`}
      />
      <LimitBar
        value={risk.gross_exposure_pct}
        max={risk.gross_exposure_limit}
        label="Gross Exposure"
        currentLabel={`${risk.gross_exposure_pct.toFixed(1)}% / ${risk.gross_exposure_limit.toFixed(0)}%`}
      />
      <LimitBar
        value={risk.largest_position_pct}
        max={risk.largest_position_limit}
        label="Largest Position"
        currentLabel={`${risk.largest_position_pct.toFixed(1)}% / ${risk.largest_position_limit.toFixed(0)}%`}
      />

      <div className="last-updated" key={tick}>
        Updated {secondsAgo(lastFetch)}
      </div>
    </>
  )
}
