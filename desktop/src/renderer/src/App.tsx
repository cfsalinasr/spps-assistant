import { useEffect, useState } from 'react'
import Dashboard from './views/Dashboard'
import NewSynthesis from './views/NewSynthesis'
import CycleGuide from './views/CycleGuide'

const TABS = ['Dashboard', 'New synthesis', 'Cycle guide', 'Materials', 'Peptide info'] as const
type Tab = (typeof TABS)[number]

function getTabClassName(active: boolean, enabled: boolean): string {
  if (active) {
    return 'text-teal border-b-2 border-teal px-4 py-3 text-xs font-medium cursor-pointer'
  }
  if (enabled) {
    return 'text-text2 px-4 py-3 text-xs font-medium cursor-pointer'
  }
  return 'text-text3 px-4 py-3 text-xs font-medium cursor-not-allowed'
}

function App(): React.JSX.Element {
  const [activeTab, setActiveTab] = useState<Tab>('Dashboard')
  const [cycleGuideEnabled, setCycleGuideEnabled] = useState(false)

  useEffect(() => {
    let cancelled = false
    window.spps
      .getLastSynthesis()
      .then((envelope) => {
        if (!cancelled && envelope.ok && envelope.data?.cycle_guide) {
          setCycleGuideEnabled(true)
        }
      })
      .catch(() => {
        // Leave the tab disabled — matches the "no active synthesis" state.
      })
    return () => {
      cancelled = true
    }
  }, [])

  function handleViewCycleGuide(): void {
    setCycleGuideEnabled(true)
    setActiveTab('Cycle guide')
  }

  return (
    <div className="min-h-screen bg-bg">
      <nav className="bg-bg2 border-b border-[color:var(--border)] flex px-2">
        {TABS.map((tab) => {
          const enabled =
            tab === 'Dashboard' ||
            tab === 'New synthesis' ||
            (tab === 'Cycle guide' && cycleGuideEnabled)
          const active = tab === activeTab
          return (
            <button
              key={tab}
              type="button"
              disabled={!enabled}
              onClick={() => setActiveTab(tab)}
              className={getTabClassName(active, enabled)}
            >
              {tab}
            </button>
          )
        })}
      </nav>
      {activeTab === 'Dashboard' && (
        <Dashboard
          onNewSynthesis={() => setActiveTab('New synthesis')}
          onViewCycleGuide={handleViewCycleGuide}
        />
      )}
      {activeTab === 'New synthesis' && (
        <NewSynthesis
          onDone={() => setActiveTab('Dashboard')}
          onViewCycleGuide={handleViewCycleGuide}
        />
      )}
      {activeTab === 'Cycle guide' && (
        <CycleGuide onNewSynthesis={() => setActiveTab('New synthesis')} />
      )}
    </div>
  )
}

export default App
