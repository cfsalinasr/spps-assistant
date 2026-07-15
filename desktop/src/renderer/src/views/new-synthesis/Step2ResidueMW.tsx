import { useEffect, useState } from 'react'
import type { Dispatch } from 'react'
import { Button } from '../../components/ui/button'
import { Card, CardContent } from '../../components/ui/card'
import type { ResidueMwEntry, WizardAction, WizardState } from './wizardReducer'

interface Step2Props {
  state: WizardState
  dispatch: Dispatch<WizardAction>
}

function uniqueTokens(state: WizardState): string[] {
  const tokens = new Set<string>()
  for (const vessel of state.vessels) {
    for (const token of vessel.original_tokens) tokens.add(token)
  }
  return Array.from(tokens)
}

export default function Step2ResidueMW({ state, dispatch }: Readonly<Step2Props>): React.JSX.Element {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    window.spps
      .getResidues()
      .then((envelope) => {
        if (cancelled) return
        if (!envelope.ok || !envelope.data) {
          setError('Could not load the residue library. Is the sidecar running?')
          setLoading(false)
          return
        }
        const dbMap = new Map(envelope.data.map((r) => [r.token, r]))
        const merged: WizardState['residueMap'] = { ...state.residueMap }
        for (const token of uniqueTokens(state)) {
          if (merged[token]) continue
          const fromDb = dbMap.get(token)
          merged[token] = fromDb
            ? { ...fromDb, origin: 'db' }
            : { token, base_code: token, protection: '', fmoc_mw: 0, free_mw: 0, origin: 'manual' }
        }
        dispatch({ type: 'SET_RESIDUE_MAP', residueMap: merged })
        setLoading(false)
      })
      .catch(() => {
        if (!cancelled) {
          setError('Could not load the residue library. Is the sidecar running?')
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function updateEntry(token: string, patch: Partial<ResidueMwEntry>): void {
    const current = state.residueMap[token]
    const updated: ResidueMwEntry = { ...current, ...patch, token, origin: 'manual' }
    dispatch({
      type: 'SET_RESIDUE',
      token,
      entry: updated
    })
  }

  async function saveEditedResidues(): Promise<void> {
    const toSave = Object.values(state.residueMap).filter((entry) => entry.origin !== 'materials')
    await Promise.all(
      toSave.map((entry) =>
        window.spps.saveResidue({
          token: entry.token,
          base_code: entry.base_code,
          protection: entry.protection,
          fmoc_mw: entry.fmoc_mw,
          free_mw: entry.free_mw
        })
      )
    )
    dispatch({ type: 'SET_STEP', step: 3 })
  }

  const tokens = uniqueTokens(state)
  const allFilled =
    tokens.length > 0 &&
    tokens.every((token) => {
      const entry = state.residueMap[token]
      return entry && entry.fmoc_mw > 0 && entry.free_mw > 0
    })

  return (
    <div>
      <Card className="bg-bg2 mb-4">
        <CardContent className="py-6">
          {loading && <p className="text-text3 font-sans text-sm">Loading residue library…</p>}
          {error && <p className="text-red font-sans text-sm">{error}</p>}
          {!loading &&
            tokens.map((token) => {
              const entry = state.residueMap[token]
              return (
                <div key={token} className="flex items-center gap-3 mb-2">
                  <span className="text-text font-mono text-sm w-16">{token}</span>
                  <input
                    className="bg-bg3 text-text font-mono text-sm px-2 py-1 w-24"
                    type="number"
                    step="0.1"
                    value={entry?.fmoc_mw ?? ''}
                    onChange={(e) => updateEntry(token, { fmoc_mw: Number(e.target.value) })}
                    aria-label={`${token} Fmoc-MW`}
                  />
                  <input
                    className="bg-bg3 text-text font-mono text-sm px-2 py-1 w-24"
                    type="number"
                    step="0.1"
                    value={entry?.free_mw ?? ''}
                    onChange={(e) => updateEntry(token, { free_mw: Number(e.target.value) })}
                    aria-label={`${token} Free-AA-MW`}
                  />
                  <span className="text-text3 font-sans text-xs">{entry?.origin}</span>
                </div>
              )
            })}
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button onClick={() => dispatch({ type: 'SET_STEP', step: 1 })} className="bg-bg3">
          Back
        </Button>
        <Button
          disabled={!allFilled}
          onClick={saveEditedResidues}
          className="bg-teal text-bg hover:bg-teal/90"
        >
          Continue →
        </Button>
      </div>
    </div>
  )
}
