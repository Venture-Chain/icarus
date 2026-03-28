import type { Alert } from '../App'

interface Props {
  alerts: Alert[]
}

function formatTime(ts: string): string {
  try {
    const d = new Date(ts)
    if (isNaN(d.getTime())) return '--:--:--'
    return d.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return '--:--:--'
  }
}

export default function AlertFeed({ alerts }: Props) {
  return (
    <>
      <div className="panel-header-row">
        <h2>Alert Feed</h2>
        {alerts.length > 0 && (
          <span className="badge">{alerts.length}</span>
        )}
      </div>

      {alerts.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">[~]</div>
          <div className="empty-state-text">No alerts</div>
          <div className="empty-state-sub">System is quiet</div>
        </div>
      ) : (
        <div className="alert-feed-list">
          {alerts.map(a => (
            <div key={a.id} className={`alert-item ${a.severity}`}>
              <span className="alert-time">{formatTime(a.timestamp)}</span>
              <span className="alert-msg">{a.message}</span>
            </div>
          ))}
        </div>
      )}
    </>
  )
}
