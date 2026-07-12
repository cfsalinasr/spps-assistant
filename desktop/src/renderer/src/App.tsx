import Dashboard from './views/Dashboard'

const TABS = ['Dashboard', 'New synthesis', 'Cycle guide', 'Materials', 'Peptide info'] as const

function App(): React.JSX.Element {
  return (
    <div className="min-h-screen bg-bg">
      <nav className="bg-bg2 border-b border-[color:var(--border)] flex px-2">
        {TABS.map((tab, index) => (
          <div
            key={tab}
            className={
              index === 0
                ? 'text-teal border-b-2 border-teal px-4 py-3 text-xs font-medium'
                : 'text-text3 px-4 py-3 text-xs font-medium cursor-not-allowed'
            }
          >
            {tab}
          </div>
        ))}
      </nav>
      <Dashboard />
    </div>
  )
}

export default App
