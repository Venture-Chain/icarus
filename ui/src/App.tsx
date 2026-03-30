import { useState, useEffect, useRef } from 'react'
import './App.css'
import AccountCards from './components/AccountCards'
import PortfolioOverview from './components/PortfolioOverview'
import StrategyCommand from './components/StrategyCommand'
import RiskConsole from './components/RiskConsole'
import ApprovalQueue from './components/ApprovalQueue'
import AlertFeed from './components/AlertFeed'
import SystemHealth from './components/SystemHealth'
import QuantumLab from './components/QuantumLab'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5100'
const WS_URL = API_URL.replace('http', 'ws') + '/ws'

export interface Alert {
  id: number
  type: string
  message: string
  severity: 'info' | 'warning' | 'critical'
  timestamp: string
  account_id?: string
}

function useCurrentTime() {
  const [time, setTime] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return time
}

function isMarketOpen(date: Date): boolean {
  const eastern = new Date(date.toLocaleString('en-US', { timeZone: 'America/New_York' }))
  const day = eastern.getDay()
  if (day === 0 || day === 6) return false
  const h = eastern.getHours()
  const m = eastern.getMinutes()
  const minutes = h * 60 + m
  return minutes >= 9 * 60 + 30 && minutes < 16 * 60
}

type View = 'control-room' | 'quantum-lab'

function App() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [connected, setConnected] = useState(false)
  const [quantumAvailable, setQuantumAvailable] = useState(false)
  const [view, setView] = useState<View>('control-room')
  const [selectedAccount, setSelectedAccount] = useState('')
  const wsRef = useRef<WebSocket | null>(null)
  const now = useCurrentTime()

  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        setTimeout(connect, 3000)
      }
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'alert') {
            setAlerts(prev => [
              { id: Date.now(), ...data },
              ...prev.slice(0, 49),
            ])
          }
        } catch {}
      }
    }

    connect()
    return () => wsRef.current?.close()
  }, [])

  useEffect(() => {
    fetch(`${API_URL}/quantum/status`)
      .then(r => r.json())
      .then(data => setQuantumAvailable(data.enabled === true))
      .catch(() => setQuantumAvailable(false))
  }, [])

  const marketOpen = isMarketOpen(now)
  const timeStr = now.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: 'America/New_York',
  })

  return (
    <div className="control-room">
      <header className="control-room-header">
        <div className="header-brand">
          <span className="header-title">ICARUS</span>
          {quantumAvailable ? (
            <div className="header-nav">
              <button
                className={`header-nav-btn ${view === 'control-room' ? 'active' : ''}`}
                onClick={() => setView('control-room')}
              >
                Control Room
              </button>
              <button
                className={`header-nav-btn quantum ${view === 'quantum-lab' ? 'active' : ''}`}
                onClick={() => setView('quantum-lab')}
              >
                Quantum Lab
              </button>
            </div>
          ) : (
            <span className="header-subtitle">Control Room</span>
          )}
        </div>
        <div className="header-right">
          <span className={`market-status ${marketOpen ? 'open' : 'closed'}`}>
            {marketOpen ? 'MKT OPEN' : 'MKT CLOSED'}
          </span>
          <span className="header-time">{timeStr} ET</span>
          <span className={`connection-badge ${connected ? 'connected' : 'disconnected'}`}>
            {connected ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
      </header>

      {view === 'control-room' ? (
        <>
          <AccountCards
            apiUrl={API_URL}
            selectedAccount={selectedAccount}
            onSelectAccount={setSelectedAccount}
          />
          <div className="grid">
            <div className="panel panel-risk">
              <RiskConsole apiUrl={API_URL} selectedAccount={selectedAccount} />
            </div>
            <div className="panel panel-portfolio">
              <PortfolioOverview apiUrl={API_URL} selectedAccount={selectedAccount} />
            </div>
            <div className="panel panel-health">
              <SystemHealth apiUrl={API_URL} />
            </div>
            <div className="panel panel-strategies">
              <StrategyCommand apiUrl={API_URL} />
            </div>
            <div className="panel panel-approvals">
              <ApprovalQueue apiUrl={API_URL} selectedAccount={selectedAccount} />
            </div>
            <div className="panel panel-alerts">
              <AlertFeed alerts={alerts} selectedAccount={selectedAccount} />
            </div>
          </div>
        </>
      ) : (
        <div className="quantum-view">
          <QuantumLab apiUrl={API_URL} />
        </div>
      )}
    </div>
  )
}

export default App
