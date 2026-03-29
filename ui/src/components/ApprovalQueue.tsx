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

interface BrokerAccount {
  account_id: string
  broker_type: string
  mode: string
  connected: boolean
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
  const [accounts, setAccounts] = useState<BrokerAccount[]>([])
  const [killTarget, setKillTarget] = useState<string>('')

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

  useEffect(() => {
    fetch(`${apiUrl}/accounts/`)
      .then(r => r.json())
      .then(d => { if (Array.isArray(d)) setAccounts(d) })
      .catch(() => {})
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
    const target = killTarget || 'ALL ACCOUNTS'
    if (!confirm(`Activate FLATTEN ALL for ${target}? This will close all open positions immediately.`)) return
    try {
      await fetch(`${apiUrl}/portfolio/kill-switch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: killTarget || null }),
      })
      setKillActive(true)
    } catch (err) {
      console.error('Kill switch failed:', err)
    }
  }

  const killLabel = killTarget
    ? `KILL: ${killTarget}`
    : 'KILL SWITCH'

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
        {accounts.length > 1 && (
          <select
            className="account-selector kill-target-selector"
            value={killTarget}
            onChange={e => setKillTarget(e.target.value)}
          >
            <option value="">ALL ACCOUNTS</option>
            {accounts.map(a => (
              <option key={a.account_id} value={a.account_id}>
                {a.account_id} ({a.broker_type})
              </option>
            ))}
          </select>
        )}
        <button
          className={`btn-kill-big ${killActive ? 'armed' : ''}`}
          onClick={handleKillSwitch}
          disabled={killActive}
        >
          {killActive ? 'KILL SWITCH ARMED' : killLabel}
        </button>
        <div className="kill-switch-sub">
          {killActive
            ? 'All positions flattened. CIO approval needed to deactivate.'
            : 'Emergency: closes all open positions immediately'}
        </div>
      </div>
    </>
  )
}
