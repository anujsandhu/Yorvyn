import { Menu, Plus, Zap } from 'lucide-react'
import { useApp } from '../context/AppContext'
import { Logo } from './Logo'
import './TopNav.css'

export function TopNav() {
  const { setSidebarOpen, resetToQuiz, tempMode, setTempMode } = useApp()

  const handleTempToggle = () => {
    setTempMode(!tempMode)
  }

  return (
    <header className="tn-root">
      <div className="tn-inner">
        {/* Left — hamburger */}
        <button
          className="tn-icon-btn"
          onClick={() => setSidebarOpen(prev => !prev)}
          aria-label="Toggle menu"
        >
          <Menu size={20} strokeWidth={1.8} />
        </button>

        {/* Center — full logo image */}
        <div className="tn-logo" aria-label="Yorvyn home">
          <Logo size="md" />
        </div>

        {/* Right — Controls */}
        <div className="tn-controls">
          {/* Temp toggle */}
          <button
            className={`tn-temp-toggle ${tempMode ? 'tn-temp-active' : ''}`}
            onClick={handleTempToggle}
            aria-label={tempMode ? 'Temporary mode active' : 'Enable temporary mode'}
            title={tempMode ? 'Temporary session - not saved' : 'Enable temporary mode'}
          >
            <Zap size={14} strokeWidth={2.5} />
            <span>Temp</span>
          </button>

          {/* New Search button */}
          <button
            className="tn-new-search-btn"
            onClick={resetToQuiz}
            aria-label="New search"
          >
            <Plus size={16} strokeWidth={2.5} />
            <span>New Search</span>
          </button>
        </div>
      </div>

      {/* Temp mode badge */}
      {tempMode && (
        <div className="tn-temp-badge">
          <Zap size={12} />
          <span>Temporary session</span>
        </div>
      )}
    </header>
  )
}
