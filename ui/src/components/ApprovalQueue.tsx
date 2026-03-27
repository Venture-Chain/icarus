interface Props {
  apiUrl: string
}

export default function ApprovalQueue({ apiUrl: _apiUrl }: Props) {
  return (
    <div>
      <h2>Approval Queue</h2>
      <div style={{ color: 'var(--text-secondary)' }}>
        No pending approvals
      </div>
    </div>
  )
}
