import type { Alert } from '../App'

interface Props {
  alerts: Alert[]
}

export default function AlertFeed({ alerts }: Props) {
  return (
    <div>
      <h2>Alert Feed</h2>
      {alerts.length === 0 ? (
        <div style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
          No alerts
        </div>
      ) : (
        <div style={{ maxHeight: '220px', overflowY: 'auto' }}>
          {alerts.map(a => (
            <div key={a.id} className={`alert-item ${a.severity}`}>
              <span className="alert-time">
                {new Date(a.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
              <span className="alert-msg">{a.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
