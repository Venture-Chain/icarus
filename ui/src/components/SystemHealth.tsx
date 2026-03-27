interface Props {
  apiUrl: string
}

export default function SystemHealth({ apiUrl: _apiUrl }: Props) {
  const services = [
    { name: 'IB Gateway', status: 'inactive' },
    { name: 'Data Feeds', status: 'inactive' },
    { name: 'Strategy Engine', status: 'inactive' },
    { name: 'Risk Engine', status: 'inactive' },
    { name: 'TimescaleDB', status: 'inactive' },
    { name: 'Redis', status: 'inactive' },
  ]

  return (
    <div>
      <h2>System Health</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {services.map(s => (
          <div key={s.name} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className={`status-dot ${s.status}`} />
            <span>{s.name}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
