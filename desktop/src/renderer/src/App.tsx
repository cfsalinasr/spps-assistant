import { useEffect, useState } from 'react'
import Dashboard from './views/Dashboard'
import NewSynthesis from './views/NewSynthesis'
import CycleGuide from './views/CycleGuide'
import Materials from './views/Materials'
import PeptideInfo from './views/PeptideInfo'

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
  const [materialsEnabled, setMaterialsEnabled] = useState(false)

  useEffect(() => {
    let cancelled = false
    window.spps
      .getLastSynthesis()
      .then((envelope) => {
        if (cancelled) return
        if (envelope.ok && envelope.data?.cycle_guide) {
          setCycleGuideEnabled(true)
        }
        if (envelope.ok && envelope.data?.materials) {
          setMaterialsEnabled(true)
        }
      })
      .catch(() => {
        // Leave the tabs disabled — matches the "no active synthesis" state.
      })
    return () => {
      cancelled = true
    }
  }, [])

  function handleViewCycleGuide(): void {
    setCycleGuideEnabled(true)
    setActiveTab('Cycle guide')
  }

  function handleViewMaterials(): void {
    setMaterialsEnabled(true)
    setActiveTab('Materials')
  }

  return (
    <div className="min-h-screen bg-bg">
      <nav className="bg-bg2 border-b border-[color:var(--border)] flex px-2">
        {TABS.map((tab) => {
          const enabled =
            tab === 'Dashboard' ||
            tab === 'New synthesis' ||
            tab === 'Peptide info' ||
            (tab === 'Cycle guide' && cycleGuideEnabled) ||
            (tab === 'Materials' && materialsEnabled)
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
          onViewMaterials={handleViewMaterials}
        />
      )}
      {activeTab === 'New synthesis' && (
        <NewSynthesis
          onDone={() => setActiveTab('Dashboard')}
          onViewCycleGuide={handleViewCycleGuide}
          onViewMaterials={handleViewMaterials}
        />
      )}
      {activeTab === 'Cycle guide' && (
        <CycleGuide onNewSynthesis={() => setActiveTab('New synthesis')} />
      )}
      {activeTab === 'Materials' && (
        <Materials onNewSynthesis={() => setActiveTab('New synthesis')} />
      )}
      {activeTab === 'Peptide info' && <PeptideInfo />}
    </div>
  )
}

export default App
