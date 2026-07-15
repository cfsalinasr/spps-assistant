import type { ReactNode } from 'react'

interface PillProps {
  active: boolean
  onClick: () => void
  children: ReactNode
}

export function Pill({ active, onClick, children }: PillProps): React.JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        active
          ? 'bg-teal-dim text-teal border border-teal px-3 py-1.5 rounded text-xs font-medium mr-2 mb-2'
          : 'bg-bg3 text-text3 border border-transparent px-3 py-1.5 rounded text-xs font-medium mr-2 mb-2'
      }
    >
      {children}
    </button>
  )
}
