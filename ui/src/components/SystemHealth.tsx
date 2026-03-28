import { useState, useEffect } from 'react'

interface ServiceStatus {
  name: string
  status: 'active' | 'warning' | 'error' | 'inactive'
  latency?: number
  group: 'core' | 'trading'
}

interface Props {
  apiUrl: string
}

const defaultServices: ServiceStatus[] = [
  { name: 'API', status: 'inactive', group: 'core' },
  { name: 'TimescaleDB', status: 'inactive', group: 'core' },
  { name: 'Redis', status: 'inactive', group: 'core' },
  { name: 'IB Gateway', status: 'inactive', group: 'trading' },
  { name: 'Strategy Engine', status: 'inactive', group: 'trading' },
  { name: 'Risk Engine', status: 'inactive', group: 'trading' },
  { name: 'Data Feeds', status: 'inactive', group: 'trading' },
]

export default function SystemHealth({ apiUrl }: Props) {
  const [services, setServices] = useState<ServiceStatus[]>(defaultServices)

  useEffect(() => {
    const checkHealth = async () => {
      const start = Date.now()
      try {
        const resp = await fetch(`${apiUrl}/health`)
        const latency = Date.now() - start
        if (resp.ok) {
          setServices(prev => prev.map(s => {
            if (s.name === 'API' || s.name === 'Strategy Engine' || s.name === 'Risk Engine') {
              return { ...s, status: 'active' as const, latency }
            }
            return s
          }))
        }
      } catch {
        setServices(prev => prev.map(s => ({ ...s, status: 'inactive' as const, latency: undefined })))
      }
    }
    checkHealth()
    const id = setInterval(checkHealth, 15000)
    return () => clearInterval(id)
  }, [apiUrl])

  const coreServices = services.filter(s => s.group === 'core')
  const tradingServices = services.filter(s => s.group === 'trading')

  const uptimePct = (list: ServiceStatus[]) => {
    const active = list.filter(s => s.status === 'active').length
    return Math.round((active / list.length) * 100)
  }

  return (
    <div>
      <h2>System Health</h2>

      <div className="health-group-label">Core</div>
      {coreServices.map(s => (
        <div key={s.name} className="health-row">
          <div className="label">
            <span className={`status-dot ${s.status}`} />
            <span>{s.name}</span>
          </div>
          <div className="health-row-right">
            {s.latency !== undefined && (
              <span className="latency-badge">{s.latency}ms</span>
            )}
            <span className="uptime-label">--</span>
          </div>
        </div>
      ))}
      <div style={{ paddingLeft: '8px', marginBottom: '4px' }}>
        <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>
          {uptimePct(coreServices)}% up
        </span>
      </div>

      <div className="health-group-label">Trading</div>
      {tradingServices.map(s => (
        <div key={s.name} className="health-row">
          <div className="label">
            <span className={`status-dot ${s.status}`} />
            <span>{s.name}</span>
          </div>
          <div className="health-row-right">
            {s.latency !== undefined && (
              <span className="latency-badge">{s.latency}ms</span>
            )}
            <span className="uptime-label">--</span>
          </div>
        </div>
      ))}
      <div style={{ paddingLeft: '8px' }}>
        <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>
          {uptimePct(tradingServices)}% up
        </span>
      </div>
    </div>
  )
}
