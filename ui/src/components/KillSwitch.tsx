import { useState } from 'react'

interface Props {
  apiUrl: string
  selectedAccount: string
}

export default function KillSwitch({ apiUrl, selectedAccount }: Props) {
  const [killActive, setKillActive] = useState(false)

  const handleKillSwitch = async () => {
    const target = selectedAccount || 'ALL ACCOUNTS'
    if (!confirm(`Activate FLATTEN ALL for ${target}? This will close all open positions immediately.`)) return
    try {
      await fetch(`${apiUrl}/portfolio/kill-switch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: selectedAccount || null }),
      })
      setKillActive(true)
    } catch (err) {
      console.error('Kill switch failed:', err)
    }
  }

  const killLabel = selectedAccount
    ? `KILL: ${selectedAccount}`
    : 'KILL SWITCH'

  return (
    <>
      <h2>Emergency Controls</h2>
      <div className="kill-switch-section">
        <button
          className={`btn-kill-big ${killActive ? 'armed' : ''}`}
          onClick={handleKillSwitch}
          disabled={killActive}
        >
          {killActive ? 'KILL SWITCH ARMED' : killLabel}
        </button>
        <div className="kill-switch-sub">
          {killActive
            ? 'All positions flattened.'
            : selectedAccount
              ? `Emergency: closes all positions on ${selectedAccount}`
              : 'Emergency: closes all open positions immediately'}
        </div>
      </div>
    </>
  )
}
