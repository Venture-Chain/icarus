import { useState, useEffect } from 'react'

interface Approval {
  id: number
  action_type: string
  description: string
  reasoning: string
  status: string
  created_at: string
}

interface Props {
  apiUrl: string
}

export default function ApprovalQueue({ apiUrl }: Props) {
  const [approvals, setApprovals] = useState<Approval[]>([])

  useEffect(() => {
    const fetchApprovals = async () => {
      try {
        const resp = await fetch(`${apiUrl}/approvals/`)
        const data = await resp.json()
        setApprovals((data.approvals || []).filter((a: Approval) => a.status === 'pending'))
      } catch {}
    }
    fetchApprovals()
    const interval = setInterval(fetchApprovals, 5000)
    return () => clearInterval(interval)
  }, [apiUrl])

  const handleDecision = async (id: number, status: string) => {
    try {
      await fetch(`${apiUrl}/approvals/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, decided_by: 'CIO' }),
      })
      setApprovals(prev => prev.filter(a => a.id !== id))
    } catch {}
  }

  return (
    <div>
      <h2>Approval Queue</h2>
      {approvals.length === 0 ? (
        <div style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
          No pending approvals
        </div>
      ) : (
        approvals.map(a => (
          <div key={a.id} className="approval-item">
            <div className="action-type">{a.action_type.replace(/_/g, ' ')}</div>
            <div className="description">{a.description}</div>
            {a.reasoning && (
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                {a.reasoning}
              </div>
            )}
            <div className="approval-buttons">
              <button className="btn btn-approve" onClick={() => handleDecision(a.id, 'approved')}>
                Approve
              </button>
              <button className="btn btn-reject" onClick={() => handleDecision(a.id, 'rejected')}>
                Reject
              </button>
            </div>
          </div>
        ))
      )}
    </div>
  )
}
