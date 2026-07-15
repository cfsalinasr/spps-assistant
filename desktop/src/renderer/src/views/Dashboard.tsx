import { useEffect, useState } from 'react'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import type { SppsConfig } from '../../../preload/index.d'

type LoadState =
  { status: 'loading' } | { status: 'error' } | { status: 'loaded'; config: SppsConfig }

type LastSynthesisState =
  | { status: 'loading' }
  | { status: 'none' }
  | { status: 'active'; name: string; vesselCount: number; generatedAt: string }

const CONFIG_FIELDS: Array<{ key: string; label: string }> = [
  { key: 'activator', label: 'Activator' },
  { key: 'base', label: 'Base' },
  { key: 'deprotection_reagent', label: 'Deprotection reagent' },
  { key: 'aa_equivalents', label: 'AA equivalents' },
  { key: 'vessel_method', label: 'Vessel method' }
]

interface DashboardProps {
  onNewSynthesis: () => void
}

export default function Dashboard({ onNewSynthesis }: DashboardProps): React.JSX.Element {
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [lastSynthesis, setLastSynthesis] = useState<LastSynthesisState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    window.spps
      .getConfig()
      .then((envelope) => {
        if (cancelled) return
        if (envelope.ok && envelope.data) {
          setState({ status: 'loaded', config: envelope.data })
        } else {
          setState({ status: 'error' })
        }
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'error' })
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    window.spps
      .getLastSynthesis()
      .then((envelope) => {
        if (cancelled) return
        if (envelope.ok && envelope.data) {
          setLastSynthesis({
            status: 'active',
            name: envelope.data.name,
            vesselCount: envelope.data.vessel_count,
            generatedAt: envelope.data.generated_at
          })
        } else {
          setLastSynthesis({ status: 'none' })
        }
      })
      .catch(() => {
        if (!cancelled) setLastSynthesis({ status: 'none' })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="bg-bg p-5">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-text font-sans text-base font-medium">Dashboard</h1>
        <Button onClick={onNewSynthesis} className="bg-teal text-bg hover:bg-teal/90">
          + New synthesis
        </Button>
      </div>

      <Card className="bg-bg2 mb-4">
        <CardHeader>
          <CardTitle className="text-text text-sm font-medium">
            Current synthesis defaults
          </CardTitle>
        </CardHeader>
        <CardContent>
          {state.status === 'loading' && (
            <p className="text-text3 font-sans text-sm">Loading configuration…</p>
          )}
          {state.status === 'error' && (
            <p className="text-red font-sans text-sm">
              Couldn&apos;t load configuration. Is the sidecar running?
            </p>
          )}
          {state.status === 'loaded' && (
            <dl className="grid grid-cols-2 gap-3">
              {CONFIG_FIELDS.map(({ key, label }) => (
                <div key={key}>
                  <dt className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">
                    {label}
                  </dt>
                  <dd className="text-text font-mono text-sm">
                    {String(state.config[key] ?? '—')}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </CardContent>
      </Card>

      <Card className="bg-bg2">
        <CardContent className="flex flex-col items-center justify-center py-10 text-center">
          {lastSynthesis.status === 'active' ? (
            <>
              <p className="text-text font-sans text-sm mb-1">{lastSynthesis.name}</p>
              <p className="text-text3 font-mono text-xs">
                {lastSynthesis.vesselCount} vessel(s) — generated {lastSynthesis.generatedAt}
              </p>
            </>
          ) : (
            <>
              <p className="text-text2 font-sans text-sm mb-4">No active syntheses</p>
              <Button onClick={onNewSynthesis} className="bg-teal text-bg hover:bg-teal/90">
                + New synthesis
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
