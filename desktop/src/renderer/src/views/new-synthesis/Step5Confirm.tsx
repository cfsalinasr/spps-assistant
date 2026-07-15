import { useState } from 'react'
import type { Dispatch } from 'react'
import { Button } from '../../components/ui/button'
import { Card, CardContent } from '../../components/ui/card'
import type { WizardAction, WizardState } from './wizardReducer'

interface Step5Props {
  state: WizardState
  dispatch: Dispatch<WizardAction>
  onDone: () => void
}

export default function Step5Confirm({ state, dispatch, onDone }: Step5Props): React.JSX.Element {
  const [name, setName] = useState(state.synthesisName)

  async function handleGenerate(): Promise<void> {
    dispatch({ type: 'SET_SYNTHESIS_NAME', name })
    dispatch({ type: 'GENERATE_START' })

    const outputDirectory = state.outputDirectory || (await window.spps.pickOutputDirectory()) || 'spps_output'

    const envelope = await window.spps.generateSynthesis({
      vessels: state.vessels.map((v) => ({
        ...v,
        resin_mass_g: state.resin.fixedResinMassG,
        substitution_mmol_g: state.resin.substitutionMmolG
      })),
      residue_info_map: Object.fromEntries(
        Object.entries(state.residueMap).map(([token, entry]) => [
          token,
          {
            token: entry.token,
            base_code: entry.base_code,
            protection: entry.protection,
            fmoc_mw: entry.fmoc_mw,
            free_mw: entry.free_mw
          }
        ])
      ),
      config_overrides: {
        name,
        deprotection_reagent: state.reagents.deprotectionReagent,
        activator: state.reagents.activator,
        use_oxyma: state.reagents.useOxyma,
        base: state.reagents.base,
        volume_mode: state.reagents.volumeMode,
        include_bb_test: state.reagents.completenessTest === 'bromophenol',
        include_kaiser_test: state.reagents.completenessTest === 'kaiser',
        resin_mass_strategy: state.resin.strategy,
        fixed_resin_mass_g: state.resin.fixedResinMassG,
        target_yield_mg: state.resin.targetYieldMg,
        output_directory: outputDirectory
      }
    })

    if (!envelope.ok || !envelope.data) {
      dispatch({ type: 'GENERATE_ERROR', error: envelope.error?.message ?? 'Generation failed.' })
      return
    }
    dispatch({ type: 'GENERATE_SUCCESS', paths: envelope.data })
  }

  if (state.generateResult.status === 'success') {
    const firstPath = Object.values(state.generateResult.paths ?? {})[0]
    return (
      <Card className="bg-bg2">
        <CardContent className="py-10 text-center">
          <p className="text-teal font-sans text-sm mb-4">Synthesis generated successfully.</p>
          <ul className="mb-4">
            {Object.entries(state.generateResult.paths ?? {}).map(([label, path]) => (
              <li key={label} className="text-text3 font-mono text-xs">
                {label}: {path}
              </li>
            ))}
          </ul>
          <div className="flex justify-center gap-3">
            {firstPath && (
              <Button onClick={() => window.spps.openFolder(firstPath)} className="bg-bg3">
                Open folder
              </Button>
            )}
            <Button onClick={onDone} className="bg-teal text-bg hover:bg-teal/90">
              Done
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div>
      <Card className="bg-bg2 mb-4">
        <CardContent className="py-6">
          <div className="mb-4">
            <label htmlFor="synthesis-name-input" className="text-text3 font-sans text-xs uppercase tracking-wide mb-1 block">
              Synthesis name
            </label>
            <input
              id="synthesis-name-input"
              className="bg-bg3 text-text font-sans text-sm px-2 py-1 w-64"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <dl className="grid grid-cols-2 gap-3">
            <div>
              <dt className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">Sequences</dt>
              <dd className="text-text font-mono text-sm">
                {state.vessels.length} vessel(s) ({state.fastaPath})
              </dd>
            </div>
            <div>
              <dt className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">Residue MW</dt>
              <dd className="text-text font-mono text-sm">
                {Object.keys(state.residueMap).length} unique token(s) confirmed
              </dd>
            </div>
            <div>
              <dt className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">Reagents</dt>
              <dd className="text-text font-mono text-sm">
                {state.reagents.activator} / {state.reagents.base} / {state.reagents.deprotectionReagent}
              </dd>
            </div>
            <div>
              <dt className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">Resin</dt>
              <dd className="text-text font-mono text-sm">
                {state.resin.strategy === 'fixed'
                  ? `Fixed mass, ${state.resin.fixedResinMassG} g`
                  : `Target yield, ${state.resin.targetYieldMg} mg`}
                , sub {state.resin.substitutionMmolG} mmol/g
              </dd>
            </div>
            <div>
              <dt className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">Output directory</dt>
              <dd className="text-text font-mono text-sm">{state.outputDirectory || '(choose on generate)'}</dd>
            </div>
          </dl>

          {state.generateResult.status === 'error' && (
            <p className="text-red font-sans text-sm mt-4">{state.generateResult.error}</p>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button onClick={() => dispatch({ type: 'SET_STEP', step: 4 })} className="bg-bg3">
          Back
        </Button>
        <Button
          disabled={state.generateResult.status === 'generating'}
          onClick={handleGenerate}
          className="bg-teal text-bg hover:bg-teal/90"
        >
          {state.generateResult.status === 'generating' ? 'Generating…' : 'Generate →'}
        </Button>
      </div>
    </div>
  )
}
