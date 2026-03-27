import { useState } from 'react'

interface Props {
  apiUrl: string
}

export default function KillSwitch({ apiUrl }: Props) {
  const [active, setActive] = useState(false)

  const handleActivate = async () => {
    if (!confirm('Activate kill switch? This will flatten ALL positions.')) return
    try {
      await fetch(`${apiUrl}/portfolio/kill-switch`, { method: 'POST' })
      setActive(true)
    } catch (err) {
      console.error('Kill switch failed:', err)
    }
  }

  return (
    <div>
      <h2>Kill Switch</h2>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', paddingTop: '20px' }}>
        <button
          onClick={handleActivate}
          disabled={active}
          style={{
            width: '120px',
            height: '120px',
            borderRadius: '50%',
            border: active ? '3px solid var(--red)' : '3px solid var(--border)',
            background: active ? 'rgba(239, 68, 68, 0.2)' : 'rgba(239, 68, 68, 0.05)',
            color: active ? 'var(--red)' : 'var(--text-secondary)',
            fontSize: '12px',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '1px',
            cursor: active ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s',
          }}
        >
          {active ? 'Active' : 'Flatten All'}
        </button>
        <span style={{ color: active ? 'var(--red)' : 'var(--text-secondary)', fontSize: '12px' }}>
          {active ? 'Kill switch engaged. CIO approval needed to deactivate.' : 'Emergency: closes all positions'}
        </span>
      </div>
    </div>
  )
}
