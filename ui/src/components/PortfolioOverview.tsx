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
  if (abs >= 1_000_000) return `$${fmt(n / 1_000_000)}M`
  if (abs >= 1_000) return `$${fmt(n / 1_000)}K`
  return `$${fmt(n)}`
}

export default function PortfolioOverview({ apiUrl }: Props) {
  const [data, setData] = useState<PortfolioData>(defaultPortfolio)

  useEffect(() => {
    const fetch_ = async () => {
      try {
        const resp = await fetch(`${apiUrl}/portfolio/risk`)
        const json = await resp.json()
        setData({ ...defaultPortfolio, ...json })
      } catch {}
    }
    fetch_()
    const id = setInterval(fetch_, 10000)
    return () => clearInterval(id)
  }, [apiUrl])

  const pnlPositive = data.daily_pnl >= 0
  const pnlSign = pnlPositive ? '+' : ''
  const netExposurePct = Math.abs(data.net_exposure) * 100
  const grossExposurePct = Math.min((data.gross_exposure * 100) / 200, 100)

  return (
    <div>
      <h2>Portfolio Overview</h2>

      <div className="portfolio-hero">
        <div className="portfolio-hero-item">
          <div className="portfolio-hero-label">Portfolio Value</div>
          <div className="portfolio-hero-value large">
            ${fmt(data.portfolio_value)}
          </div>
        </div>
        <div className="portfolio-hero-item">
          <div className="portfolio-hero-label">Daily P&amp;L</div>
          <div className={`portfolio-hero-value ${pnlPositive ? 'positive' : 'negative'}`}>
            {pnlSign}{fmtUsd(data.daily_pnl)}
          </div>
          <div className="portfolio-hero-sub">
            {pnlSign}{fmt(data.daily_pnl_pct)}%
          </div>
        </div>
        <div className="portfolio-hero-item">
          <div className="portfolio-hero-label">Open Positions</div>
          <div className="portfolio-hero-value">
            {data.open_positions}
          </div>
        </div>
        <div className="portfolio-hero-item">
          <div className="portfolio-hero-label">Buying Power</div>
          <div className="portfolio-hero-value">
            {fmtUsd(data.buying_power)}
          </div>
        </div>
      </div>

      <div className="exposure-bars">
        <div className="exposure-bar-row">
          <span className="exposure-bar-label">Net Exposure</span>
          <div className="exposure-bar">
            <div
              className="exposure-bar-fill"
              style={{ width: `${Math.min(netExposurePct / 50 * 100, 100)}%` }}
            />
          </div>
          <span className="exposure-bar-value">{fmt(netExposurePct, 1)}%</span>
        </div>
        <div className="exposure-bar-row">
          <span className="exposure-bar-label">Gross Exposure</span>
          <div className="exposure-bar">
            <div
              className="exposure-bar-fill"
              style={{ width: `${grossExposurePct}%` }}
            />
          </div>
          <span className="exposure-bar-value">{fmt(data.gross_exposure * 100, 1)}%</span>
        </div>
      </div>
    </div>
  )
}
