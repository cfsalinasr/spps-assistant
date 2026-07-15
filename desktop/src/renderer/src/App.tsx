import { useState } from 'react'
import Dashboard from './views/Dashboard'
import NewSynthesis from './views/NewSynthesis'

const TABS = ['Dashboard', 'New synthesis', 'Cycle guide', 'Materials', 'Peptide info'] as const
type Tab = (typeof TABS)[number]

function App(): React.JSX.Element {
  const [activeTab, setActiveTab] = useState<Tab>('Dashboard')

  return (
    <div className="min-h-screen bg-bg">
      <nav className="bg-bg2 border-b border-[color:var(--border)] flex px-2">
        {TABS.map((tab) => {
          const enabled = tab === 'Dashboard' || tab === 'New synthesis'
          const active = tab === activeTab
          return (
            <div
              key={tab}
              onClick={enabled ? () => setActiveTab(tab) : undefined}
              className={
                active
                  ? 'text-teal border-b-2 border-teal px-4 py-3 text-xs font-medium cursor-pointer'
                  : enabled
                    ? 'text-text2 px-4 py-3 text-xs font-medium cursor-pointer'
                    : 'text-text3 px-4 py-3 text-xs font-medium cursor-not-allowed'
              }
            >
              {tab}
            </div>
          )
        })}
      </nav>
      {activeTab === 'Dashboard' && <Dashboard onNewSynthesis={() => setActiveTab('New synthesis')} />}
      {activeTab === 'New synthesis' && <NewSynthesis onDone={() => setActiveTab('Dashboard')} />}
    </div>
  )
}

export default App
