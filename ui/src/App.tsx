import { useState, useEffect, useRef } from 'react'
import './App.css'
import StrategyCommand from './components/StrategyCommand'
import RiskConsole from './components/RiskConsole'
import ApprovalQueue from './components/ApprovalQueue'
import KillSwitch from './components/KillSwitch'
import AlertFeed from './components/AlertFeed'
import SystemHealth from './components/SystemHealth'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5100'
const WS_URL = API_URL.replace('http', 'ws') + '/ws'

export interface Alert {
  id: number
  type: string
  message: string
  severity: 'info' | 'warning' | 'critical'
  timestamp: string
}

function App() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

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

  return (
    <div className="control-room">
      <header className="control-room-header">
        <h1>Icarus</h1>
        <span className="subtitle">Control Room</span>
        <span className={`connection-status ${connected ? 'connected' : 'disconnected'}`}>
          {connected ? 'LIVE' : 'DISCONNECTED'}
        </span>
      </header>
      <div className="grid">
        <div className="panel panel-strategies">
          <StrategyCommand apiUrl={API_URL} />
        </div>
        <div className="panel panel-risk">
          <RiskConsole apiUrl={API_URL} />
        </div>
        <div className="panel panel-approvals">
          <ApprovalQueue apiUrl={API_URL} />
        </div>
        <div className="panel panel-killswitch">
          <KillSwitch apiUrl={API_URL} />
        </div>
        <div className="panel panel-alerts">
          <AlertFeed alerts={alerts} />
        </div>
        <div className="panel panel-health">
          <SystemHealth apiUrl={API_URL} />
        </div>
      </div>
    </div>
  )
}

export default App
