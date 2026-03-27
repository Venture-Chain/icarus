interface Props {
  apiUrl: string
}

export default function StrategyCommand({ apiUrl: _apiUrl }: Props) {
  return (
    <div>
      <h2>Strategy Command</h2>
      <div style={{ color: 'var(--text-secondary)' }}>
        No active strategies
      </div>
    </div>
  )
}
