import { useState, useEffect } from 'react'

interface ServiceStatus {
  name: string
  status: 'active' | 'warning' | 'error' | 'inactive'
  latency?: number
  group: 'core' | 'trading'
  badge?: string
}

interface BrokerAccount {
  broker_type: string
  account_id: string
  mode: string
  connected: boolean
}

interface Props {
  apiUrl: string
}

const coreServices: ServiceStatus[] = [
  { name: 'API', status: 'inactive', group: 'core' },
  { name: 'TimescaleDB', status: 'inactive', group: 'core' },
  { name: 'Redis', status: 'inactive', group: 'core' },
]

const engineServices: ServiceStatus[] = [
  { name: 'Strategy Engine', status: 'inactive', group: 'trading' },
  { name: 'Risk Engine', status: 'inactive', group: 'trading' },
  { name: 'Data Feeds', status: 'inactive', group: 'trading' },
]

export default function SystemHealth({ apiUrl }: Props) {
  const [core, setCore] = useState<ServiceStatus[]>(coreServices)
  const [engines, setEngines] = useState<ServiceStatus[]>(engineServices)
  const [brokerAccounts, setBrokerAccounts] = useState<BrokerAccount[]>([])

  useEffect(() => {
    const checkHealth = async () => {
      const start = Date.now()
      try {
        const resp = await fetch(`${apiUrl}/health`)
        const latency = Date.now() - start
        if (resp.ok) {
          setCore(prev => prev.map(s =>
            s.name === 'API' ? { ...s, status: 'active' as const, latency } : s
          ))
          setEngines(prev => prev.map(s =>
            s.name === 'Strategy Engine' || s.name === 'Risk Engine'
              ? { ...s, status: 'active' as const, latency }
              : s
          ))
        }
      } catch {
        setCore(prev => prev.map(s => ({ ...s, status: 'inactive' as const, latency: undefined })))
        setEngines(prev => prev.map(s => ({ ...s, status: 'inactive' as const, latency: undefined })))
      }
    }
    checkHealth()
    const id = setInterval(checkHealth, 15000)
    return () => clearInterval(id)
  }, [apiUrl])

  useEffect(() => {
    const fetchAccounts = async () => {
      try {
        const resp = await fetch(`${apiUrl}/accounts/`)
        const data = await resp.json()
        if (Array.isArray(data)) setBrokerAccounts(data)
      } catch {}
    }
    fetchAccounts()
    const id = setInterval(fetchAccounts, 15000)
    return () => clearInterval(id)
  }, [apiUrl])

  const renderRow = (s: ServiceStatus) => (
    <div key={s.name} className="health-row">
      <div className="label">
        <span className={`status-dot ${s.status}`} />
        <span>{s.name}</span>
        {s.badge && <span className="broker-badge">{s.badge}</span>}
      </div>
      <div className="health-row-right">
        {s.latency !== undefined ? (
          <span className="latency-badge">{s.latency}ms</span>
        ) : (
          <span className="latency-badge">--</span>
        )}
        <span className="uptime-label">--</span>
      </div>
    </div>
  )

  return (
    <>
      <h2>System Health</h2>

      <div className="health-content">
        <div className="health-group-label">Core</div>
        {core.map(renderRow)}

        <div className="health-group-label">Engines</div>
        {engines.map(renderRow)}

        <div className="health-group-label">Broker Accounts</div>
        {brokerAccounts.length === 0 ? (
          <div className="health-row">
            <div className="label">
              <span className="status-dot inactive" />
              <span style={{ color: 'var(--text-muted)' }}>No accounts configured</span>
            </div>
          </div>
        ) : (
          brokerAccounts.map(a => (
            <div key={a.account_id} className="health-row">
              <div className="label">
                <span className={`status-dot ${a.connected ? 'active' : 'inactive'}`} />
                <span>{a.account_id}</span>
                <span className="broker-badge">{a.broker_type.toUpperCase()}</span>
                <span className={`broker-badge ${a.mode === 'live' ? 'badge-live' : 'badge-paper'}`}>
                  {a.mode}
                </span>
              </div>
              <div className="health-row-right">
                <span className="latency-badge">{a.connected ? 'OK' : '--'}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </>
  )
}
