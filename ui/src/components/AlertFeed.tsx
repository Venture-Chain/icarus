interface Props {
  apiUrl: string
}

export default function AlertFeed({ apiUrl: _apiUrl }: Props) {
  return (
    <div>
      <h2>Alert Feed</h2>
      <div style={{ color: 'var(--text-secondary)' }}>
        No alerts
      </div>
    </div>
  )
}
