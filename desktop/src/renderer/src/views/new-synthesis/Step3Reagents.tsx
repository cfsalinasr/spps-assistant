import type { Dispatch } from 'react'
import { Button } from '../../components/ui/button'
import { Pill } from './Pill'
import type { WizardAction, WizardState } from './wizardReducer'

interface Step3Props {
  state: WizardState
  dispatch: Dispatch<WizardAction>
}

const DEPROTECTION_OPTIONS = ['Piperidine 20%', 'Piperazine 20%']
const ACTIVATOR_OPTIONS = ['HBTU', 'TBTU', 'HCTU', 'DIC', 'DCC']
const BASE_OPTIONS_STANDARD = ['DIEA', 'Pyridine']
const COMPLETENESS_TEST_OPTIONS: Array<{ value: WizardState['reagents']['completenessTest']; label: string }> = [
  { value: 'bromophenol', label: 'Bromophenol Blue' },
  { value: 'kaiser', label: 'Kaiser / Ninhydrin' },
  { value: 'none', label: 'None' }
]

export default function Step3Reagents({ state, dispatch }: Step3Props): React.JSX.Element {
  const { reagents } = state
  const isDicOrDcc = reagents.activator === 'DIC' || reagents.activator === 'DCC'
  const baseOptions = isDicOrDcc ? ['None (DIC/DCC)'] : BASE_OPTIONS_STANDARD

  function setActivator(activator: string): void {
    const forcesNoBase = activator === 'DIC' || activator === 'DCC'
    const nextBase = forcesNoBase
      ? 'None (DIC/DCC)'
      : reagents.base === 'None (DIC/DCC)'
        ? 'DIEA'
        : reagents.base
    dispatch({ type: 'SET_REAGENTS', reagents: { activator, base: nextBase } })
  }

  return (
    <div>
      <div className="mb-4">
        <p className="text-text3 font-sans text-xs uppercase tracking-wide mb-2">Deprotection reagent</p>
        {DEPROTECTION_OPTIONS.map((option) => (
          <Pill
            key={option}
            active={reagents.deprotectionReagent === option}
            onClick={() => dispatch({ type: 'SET_REAGENTS', reagents: { deprotectionReagent: option } })}
          >
            {option}
          </Pill>
        ))}
      </div>

      <div className="mb-4">
        <p className="text-text3 font-sans text-xs uppercase tracking-wide mb-2">Coupling activator</p>
        {ACTIVATOR_OPTIONS.map((option) => (
          <Pill key={option} active={reagents.activator === option} onClick={() => setActivator(option)}>
            {option}
          </Pill>
        ))}
        <div className="mt-2">
          <Pill
            active={reagents.useOxyma}
            onClick={() => dispatch({ type: 'SET_REAGENTS', reagents: { useOxyma: true } })}
          >
            + Oxyma
          </Pill>
          <Pill
            active={!reagents.useOxyma}
            onClick={() => dispatch({ type: 'SET_REAGENTS', reagents: { useOxyma: false } })}
          >
            No additive
          </Pill>
        </div>
      </div>

      <div className="mb-4">
        <p className="text-text3 font-sans text-xs uppercase tracking-wide mb-2">Base</p>
        {baseOptions.map((option) => (
          <Pill
            key={option}
            active={reagents.base === option}
            onClick={() => dispatch({ type: 'SET_REAGENTS', reagents: { base: option } })}
          >
            {option}
          </Pill>
        ))}
      </div>

      <div className="mb-4">
        <p className="text-text3 font-sans text-xs uppercase tracking-wide mb-2">Volume mode</p>
        <Pill
          active={reagents.volumeMode === 'stoichiometry'}
          onClick={() => dispatch({ type: 'SET_REAGENTS', reagents: { volumeMode: 'stoichiometry' } })}
        >
          Stoichiometry-based
        </Pill>
        <Pill
          active={reagents.volumeMode === 'legacy'}
          onClick={() => dispatch({ type: 'SET_REAGENTS', reagents: { volumeMode: 'legacy' } })}
        >
          Legacy (2 mL/vessel)
        </Pill>
      </div>

      <div className="mb-4">
        <p className="text-text3 font-sans text-xs uppercase tracking-wide mb-2">Coupling completeness test</p>
        {COMPLETENESS_TEST_OPTIONS.map(({ value, label }) => (
          <Pill
            key={value}
            active={reagents.completenessTest === value}
            onClick={() => dispatch({ type: 'SET_REAGENTS', reagents: { completenessTest: value } })}
          >
            {label}
          </Pill>
        ))}
      </div>

      <div className="flex justify-between mt-4">
        <Button onClick={() => dispatch({ type: 'SET_STEP', step: 2 })} className="bg-bg3">
          Back
        </Button>
        <Button
          onClick={() => dispatch({ type: 'SET_STEP', step: 4 })}
          className="bg-teal text-bg hover:bg-teal/90"
        >
          Continue →
        </Button>
      </div>
    </div>
  )
}
