import { useState, useEffect } from 'react'

interface BrokerAccount {
  account_id: string
  broker_type: string
  mode: string
  connected: boolean
}

interface AccountDetail {
  account_id: string
  broker_type: string
  mode: string
  connected: boolean
  net_liquidation: number
  unrealized_pnl: number
}

interface Props {
  apiUrl: string
  selectedAccount: string
  onSelectAccount: (accountId: string) => void
}

function fmtUsd(n: number): string {
  const abs = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(1)}K`
  return `${sign}$${abs.toFixed(2)}`
}

export default function AccountCards({ apiUrl, selectedAccount, onSelectAccount }: Props) {
  const [accounts, setAccounts] = useState<AccountDetail[]>([])

  useEffect(() => {
    const fetchAccounts = async () => {
      try {
        const listResp = await fetch(`${apiUrl}/accounts/`)
        const list: BrokerAccount[] = await listResp.json()
        if (!Array.isArray(list) || list.length === 0) {
          setAccounts([])
          return
        }

        const details = await Promise.all(
          list.map(async (a) => {
            try {
              const resp = await fetch(`${apiUrl}/accounts/${a.account_id}`)
              const detail = await resp.json()
              return {
                account_id: a.account_id,
                broker_type: a.broker_type,
                mode: a.mode,
                connected: detail.connected ?? a.connected,
                net_liquidation: detail.net_liquidation ?? 0,
                unrealized_pnl: detail.unrealized_pnl ?? 0,
              } as AccountDetail
            } catch {
              return {
                ...a,
                net_liquidation: 0,
                unrealized_pnl: 0,
              } as AccountDetail
            }
          })
        )
        setAccounts(details)
      } catch {
        setAccounts([])
      }
    }

    fetchAccounts()
    const id = setInterval(fetchAccounts, 15000)
    return () => clearInterval(id)
  }, [apiUrl])

  if (accounts.length === 0) return null

  const handleClick = (accountId: string) => {
    if (accounts.length <= 1) return
    onSelectAccount(selectedAccount === accountId ? '' : accountId)
  }

  return (
    <div className="account-cards-row">
      {accounts.length > 1 && (
        <button
          className={`account-card account-card-all ${selectedAccount === '' ? 'selected' : ''}`}
          onClick={() => onSelectAccount('')}
        >
          <div className="card-label">ALL</div>
          <div className="card-equity">
            {fmtUsd(accounts.reduce((sum, a) => sum + a.net_liquidation, 0))}
          </div>
        </button>
      )}
      {accounts.map(a => (
        <button
          key={a.account_id}
          className={`account-card ${selectedAccount === a.account_id ? 'selected' : ''}`}
          onClick={() => handleClick(a.account_id)}
        >
          <div className="card-top">
            <span className={`status-dot ${a.connected ? 'active' : 'inactive'}`} />
            <span className="card-label">{a.account_id}</span>
          </div>
          <div className="card-badges">
            <span className="broker-badge">{a.broker_type.toUpperCase()}</span>
            <span className={`broker-badge ${a.mode === 'live' ? 'badge-live' : 'badge-paper'}`}>
              {a.mode}
            </span>
          </div>
          <div className="card-equity">{fmtUsd(a.net_liquidation)}</div>
          {a.unrealized_pnl !== 0 && (
            <div className={`card-pnl ${a.unrealized_pnl >= 0 ? 'positive' : 'negative'}`}>
              {a.unrealized_pnl >= 0 ? '+' : ''}{fmtUsd(a.unrealized_pnl)}
            </div>
          )}
        </button>
      ))}
    </div>
  )
}
