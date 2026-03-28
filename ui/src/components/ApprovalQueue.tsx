import { useState, useEffect } from 'react'

interface Approval {
  id: number
  action_type: string
  description: string
  reasoning: string
  status: string
  created_at: string
  urgency?: 'high' | 'medium' | 'low'
}

interface Props {
  apiUrl: string
}

function urgencyClass(a: Approval): string {
  if (a.urgency === 'high') return 'urgency-high'
  if (a.urgency === 'low') return 'urgency-low'
  return 'urgency-medium'
}

export default function ApprovalQueue({ apiUrl }: Props) {
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [killActive, setKillActive] = useState(false)

  useEffect(() => {
    const fetchApprovals = async () => {
      try {
        const resp = await fetch(`${apiUrl}/approvals/`)
        const data = await resp.json()
        setApprovals((data.approvals || []).filter((a: Approval) => a.status === 'pending'))
      } catch (err) {
        console.error('ApprovalQueue fetch failed:', err)
      }
    }
    fetchApprovals()
    const id = setInterval(fetchApprovals, 5000)
    return () => clearInterval(id)
  }, [apiUrl])

  const handleDecision = async (id: number, status: string) => {
    try {
      await fetch(`${apiUrl}/approvals/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, decided_by: 'CIO' }),
      })
      setApprovals(prev => prev.filter(a => a.id !== id))
    } catch (err) {
      console.error('ApprovalQueue decision failed:', err)
    }
  }

  const handleKillSwitch = async () => {
    if (!confirm('Activate FLATTEN ALL? This will close all open positions immediately.')) return
    try {
      await fetch(`${apiUrl}/portfolio/kill-switch`, { method: 'POST' })
      setKillActive(true)
    } catch (err) {
      console.error('Kill switch failed:', err)
    }
  }

  return (
    <>
      <div className="panel-header-row">
        <h2>Approvals</h2>
        {approvals.length > 0 && (
          <span className="badge red">{approvals.length}</span>
        )}
      </div>

      {approvals.length === 0 ? (
        <div className="empty-state" style={{ flex: 'none', padding: '20px 16px' }}>
          <div className="empty-state-icon">[ok]</div>
          <div className="empty-state-text">No pending approvals</div>
        </div>
      ) : (
        <div className="approval-list">
          {approvals.map(a => (
            <div key={a.id} className={`approval-item ${urgencyClass(a)}`}>
              <div className="action-type">{a.action_type.replace(/_/g, ' ')}</div>
              <div className="description">{a.description}</div>
              {a.reasoning && (
                <div className="reasoning">{a.reasoning}</div>
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
          ))}
        </div>
      )}

      <div className="kill-switch-section">
        <div className="kill-switch-header">Emergency Controls</div>
        <div className="kill-switch-row">
          <span className={`kill-switch-status ${killActive ? 'armed' : ''}`}>
            {killActive
              ? 'ARMED. CIO approval needed to deactivate.'
              : 'Closes all open positions immediately.'}
          </span>
          <button
            className={`btn-kill ${killActive ? 'armed' : ''}`}
            onClick={handleKillSwitch}
            disabled={killActive}
            style={{ cursor: killActive ? 'not-allowed' : 'pointer' }}
          >
            {killActive ? 'ARMED' : 'FLATTEN ALL'}
          </button>
        </div>
      </div>
    </>
  )
}
