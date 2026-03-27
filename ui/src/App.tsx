import './App.css'
import StrategyCommand from './components/StrategyCommand'
import RiskConsole from './components/RiskConsole'
import ApprovalQueue from './components/ApprovalQueue'
import KillSwitch from './components/KillSwitch'
import AlertFeed from './components/AlertFeed'
import SystemHealth from './components/SystemHealth'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5100'

function App() {
  return (
    <div className="control-room">
      <header className="control-room-header">
        <h1>Icarus</h1>
        <span className="subtitle">Control Room</span>
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
          <AlertFeed apiUrl={API_URL} />
        </div>
        <div className="panel panel-health">
          <SystemHealth apiUrl={API_URL} />
        </div>
      </div>
    </div>
  )
}

export default App
