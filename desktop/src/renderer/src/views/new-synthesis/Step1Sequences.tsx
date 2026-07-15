import { useState } from 'react'
import type { Dispatch } from 'react'
import { Button } from '../../components/ui/button'
import { Card, CardContent } from '../../components/ui/card'
import type { ResidueMwEntry, WizardAction, WizardState } from './wizardReducer'

interface Step1Props {
  state: WizardState
  dispatch: Dispatch<WizardAction>
}

interface MaterialsResidue {
  token: string
  base_code: string
  protection: string
  fmoc_mw: number
  free_mw: number
}

function buildResidueMapFromMaterials(
  materialsResidueMap: Record<string, MaterialsResidue> | undefined
): WizardState['residueMap'] {
  if (!materialsResidueMap) return {}
  const map: WizardState['residueMap'] = {}
  for (const [token, info] of Object.entries(materialsResidueMap)) {
    map[token] = { ...info, origin: 'materials' as const } satisfies ResidueMwEntry
  }
  return map
}

export default function Step1Sequences({
  state,
  dispatch
}: Readonly<Step1Props>): React.JSX.Element {
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function parseWith(fastaPath: string, materialsPath: string | null): Promise<void> {
    try {
      setLoading(true)
      setError(null)
      const envelope = await window.spps.parseSequences(fastaPath, materialsPath)
      if (!envelope.ok || !envelope.data) {
        setError(envelope.error?.message ?? 'Could not parse the FASTA file.')
        return
      }
      dispatch({
        type: 'SET_SEQUENCES',
        fastaPath,
        materialsPath,
        vessels: envelope.data.vessels,
        residueMap: buildResidueMapFromMaterials(envelope.data.materials_residue_map)
      })
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : 'Could not parse the FASTA file. Is the sidecar running?'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  async function pickAndParseFasta(): Promise<void> {
    const pickedFastaPath = await window.spps.pickFastaFile()
    if (!pickedFastaPath) return
    await parseWith(pickedFastaPath, state.materialsPath)
  }

  async function pickMaterialsFile(): Promise<void> {
    const materialsPath = await window.spps.pickMaterialsFile()
    if (!materialsPath || !state.fastaPath) return
    await parseWith(state.fastaPath, materialsPath)
  }

  return (
    <div>
      <Card className="bg-bg2 mb-4">
        <CardContent className="py-6">
          <div className="flex gap-3 mb-4">
            <Button onClick={pickAndParseFasta} disabled={loading}>
              {state.fastaPath ? 'Change FASTA file' : 'Browse for FASTA file'}
            </Button>
            {state.fastaPath && (
              <Button onClick={pickMaterialsFile} disabled={loading} className="bg-bg3">
                {state.materialsPath ? 'Change materials file' : '+ Add materials file (optional)'}
              </Button>
            )}
          </div>

          {loading && <p className="text-text3 font-sans text-sm">Parsing…</p>}
          {error && <p className="text-red font-sans text-sm">{error}</p>}

          {state.vessels.length > 0 && (
            <div>
              <p className="text-text3 font-mono text-xs mb-2">
                {state.fastaPath} — {state.vessels.length} sequence(s)
              </p>
              {state.vessels.map((vessel) => (
                <div key={vessel.number} className="mb-2">
                  <p className="text-text3 font-sans text-xs">
                    Vessel {vessel.number} — {vessel.name}
                  </p>
                  <p className="text-text font-mono text-sm">{vessel.original_tokens.join('')}</p>
                  <p className="text-text3 font-mono text-xs">
                    → reversed: {vessel.reversed_tokens.join('')}
                  </p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button
          disabled={state.vessels.length === 0}
          onClick={() => dispatch({ type: 'SET_STEP', step: 2 })}
          className="bg-teal text-bg hover:bg-teal/90"
        >
          Continue →
        </Button>
      </div>
    </div>
  )
}
