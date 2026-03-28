import { useState, useEffect } from 'react'

interface PortfolioData {
  portfolio_value: number
  daily_pnl: number
  daily_pnl_pct: number
  open_positions: number
  buying_power: number
  net_exposure: number
  gross_exposure: number
}

interface Props {
  apiUrl: string
}

const defaultPortfolio: PortfolioData = {
  portfolio_value: 0,
  daily_pnl: 0,
  daily_pnl_pct: 0,
  open_positions: 0,
  buying_power: 0,
  net_exposure: 0,
  gross_exposure: 0,
}

function fmt(n: number, decimals = 2): string {
  return n.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

function fmtUsd(n: number): string {
  const abs = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  if (abs >= 1_000_000) return `${sign}$${fmt(abs / 1_000_000)}M`
  if (abs >= 1_000) return `${sign}$${fmt(abs / 1_000)}K`
  return `${sign}$${fmt(abs)}`
}

export default function PortfolioOverview({ apiUrl }: Props) {
  const [data, setData] = useState<PortfolioData>(defaultPortfolio)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const resp = await fetch(`${apiUrl}/portfolio/risk`)
        const json = await resp.json()
        setData({ ...defaultPortfolio, ...json })
      } catch (err) {
        console.error('PortfolioOverview fetch failed:', err)
      }
    }
    fetchData()
    const id = setInterval(fetchData, 10000)
    return () => clearInterval(id)
  }, [apiUrl])

  const pnlPositive = data.daily_pnl >= 0
  const pnlSign = pnlPositive ? '+' : ''
  const netPct = Math.abs(data.net_exposure) * 100
  const grossPct = data.gross_exposure * 100

  return (
    <>
      <h2>Portfolio</h2>

      <div className="pf-value-block">
        <div className="pf-value-label">Total Value</div>
        <div className="pf-value-number">${fmt(data.portfolio_value)}</div>
      </div>

      <div className="pf-pnl-block">
        <div className="pf-value-label">Daily P&amp;L</div>
        <div className={`pf-pnl-number ${pnlPositive ? 'positive' : 'negative'}`}>
          {pnlSign}{fmtUsd(data.daily_pnl)}
        </div>
        <div className={`pf-pnl-pct ${pnlPositive ? 'positive' : 'negative'}`}>
          {pnlSign}{fmt(data.daily_pnl_pct)}%
        </div>
      </div>

      <div className="pf-stats">
        <div className="pf-stat-row">
          <span className="pf-stat-label">Positions</span>
          <span className="pf-stat-value">{data.open_positions}</span>
        </div>
        <div className="pf-stat-row">
          <span className="pf-stat-label">Buying Power</span>
          <span className="pf-stat-value">{fmtUsd(data.buying_power)}</span>
        </div>
      </div>

      <div className="pf-exposure">
        <div className="pf-exposure-row">
          <span className="pf-stat-label">Net Exp.</span>
          <div className="exposure-bar">
            <div
              className="exposure-bar-fill"
              style={{ width: `${Math.min((netPct / 50) * 100, 100)}%` }}
            />
          </div>
          <span className="pf-exp-val">{fmt(netPct, 1)}%</span>
        </div>
        <div className="pf-exposure-row">
          <span className="pf-stat-label">Gross Exp.</span>
          <div className="exposure-bar">
            <div
              className="exposure-bar-fill"
              style={{ width: `${Math.min((grossPct / 200) * 100, 100)}%` }}
            />
          </div>
          <span className="pf-exp-val">{fmt(grossPct, 1)}%</span>
        </div>
      </div>
    </>
  )
}
