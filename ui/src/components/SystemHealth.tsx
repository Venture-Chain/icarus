import { useState, useEffect } from 'react'

interface ServiceStatus {
  name: string
  status: 'active' | 'warning' | 'error' | 'inactive'
  latency?: number
}

interface Props {
  apiUrl: string
}

export default function SystemHealth({ apiUrl }: Props) {
  const [services, setServices] = useState<ServiceStatus[]>([
    { name: 'IB Gateway', status: 'inactive' },
    { name: 'Data Feeds', status: 'inactive' },
    { name: 'Strategy Engine', status: 'inactive' },
    { name: 'Risk Engine', status: 'inactive' },
    { name: 'TimescaleDB', status: 'inactive' },
    { name: 'Redis', status: 'inactive' },
  ])

  useEffect(() => {
    const checkHealth = async () => {
      const start = Date.now()
      try {
        const resp = await fetch(`${apiUrl}/health`)
        const latency = Date.now() - start
        if (resp.ok) {
          setServices(prev => prev.map(s => {
            if (s.name === 'IB Gateway' || s.name === 'Data Feeds' || s.name === 'TimescaleDB' || s.name === 'Redis') {
              return s
            }
            return { ...s, status: 'active' as const, latency }
          }))
        }
      } catch {
        setServices(prev => prev.map(s => ({ ...s, status: 'inactive' as const })))
      }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 15000)
    return () => clearInterval(interval)
  }, [apiUrl])

  return (
    <div>
      <h2>System Health</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {services.map(s => (
          <div key={s.name} className="health-row">
            <div className="label">
              <span className={`status-dot ${s.status}`} />
              <span style={{ fontSize: '13px' }}>{s.name}</span>
            </div>
            {s.latency !== undefined && (
              <span className="latency">{s.latency}ms</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
