import type { Dispatch } from 'react'
import { Button } from '../../components/ui/button'
import { Pill } from './Pill'
import type { WizardAction, WizardState } from './wizardReducer'

interface Step4Props {
  state: WizardState
  dispatch: Dispatch<WizardAction>
}

export default function Step4Resin({ state, dispatch }: Step4Props): React.JSX.Element {
  const { resin } = state
  const isValid =
    resin.substitutionMmolG > 0 &&
    (resin.strategy === 'fixed' ? resin.fixedResinMassG > 0 : (resin.targetYieldMg ?? 0) > 0)

  return (
    <div>
      <div className="mb-4">
        <p className="text-text3 font-sans text-xs uppercase tracking-wide mb-2">Resin mass strategy</p>
        <Pill
          active={resin.strategy === 'fixed'}
          onClick={() => dispatch({ type: 'SET_RESIN', resin: { strategy: 'fixed' } })}
        >
          Fixed mass
        </Pill>
        <Pill
          active={resin.strategy === 'target'}
          onClick={() => dispatch({ type: 'SET_RESIN', resin: { strategy: 'target' } })}
        >
          Target yield
        </Pill>
      </div>

      <div className="mb-4">
        <label htmlFor="substitution-input" className="text-text3 font-sans text-xs uppercase tracking-wide mb-1 block">
          Substitution value (mmol/g)
        </label>
        <input
          id="substitution-input"
          className="bg-bg3 text-text font-mono text-sm px-2 py-1 w-32"
          type="number"
          step="0.01"
          value={resin.substitutionMmolG}
          onChange={(e) =>
            dispatch({ type: 'SET_RESIN', resin: { substitutionMmolG: Number(e.target.value) } })
          }
        />
      </div>

      {resin.strategy === 'fixed' ? (
        <div className="mb-4">
          <label htmlFor="fixed-mass-input" className="text-text3 font-sans text-xs uppercase tracking-wide mb-1 block">
            Resin mass per vessel (g)
          </label>
          <input
            id="fixed-mass-input"
            className="bg-bg3 text-text font-mono text-sm px-2 py-1 w-32"
            type="number"
            step="0.01"
            value={resin.fixedResinMassG}
            onChange={(e) =>
              dispatch({ type: 'SET_RESIN', resin: { fixedResinMassG: Number(e.target.value) } })
            }
          />
        </div>
      ) : (
        <div className="mb-4">
          <label htmlFor="target-yield-input" className="text-text3 font-sans text-xs uppercase tracking-wide mb-1 block">
            Target yield (mg)
          </label>
          <input
            id="target-yield-input"
            className="bg-bg3 text-text font-mono text-sm px-2 py-1 w-32"
            type="number"
            step="1"
            value={resin.targetYieldMg ?? ''}
            onChange={(e) =>
              dispatch({ type: 'SET_RESIN', resin: { targetYieldMg: Number(e.target.value) } })
            }
          />
        </div>
      )}

      <div className="flex justify-between mt-4">
        <Button onClick={() => dispatch({ type: 'SET_STEP', step: 3 })} className="bg-bg3">
          Back
        </Button>
        <Button
          disabled={!isValid}
          onClick={() => dispatch({ type: 'SET_STEP', step: 5 })}
          className="bg-teal text-bg hover:bg-teal/90"
        >
          Continue →
        </Button>
      </div>
    </div>
  )
}
