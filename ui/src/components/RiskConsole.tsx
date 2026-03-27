interface Props {
  apiUrl: string
}

export default function RiskConsole({ apiUrl: _apiUrl }: Props) {
  return (
    <div>
      <h2>Risk Console</h2>
      <div className="risk-metrics">
        <div className="metric">
          <span className="metric-label">VaR (95%)</span>
          <span className="metric-value">--</span>
        </div>
        <div className="metric">
          <span className="metric-label">Max Drawdown</span>
          <span className="metric-value">--</span>
        </div>
        <div className="metric">
          <span className="metric-label">Net Exposure</span>
          <span className="metric-value">--</span>
        </div>
        <div className="metric">
          <span className="metric-label">Beta</span>
          <span className="metric-value">--</span>
        </div>
      </div>
    </div>
  )
}
