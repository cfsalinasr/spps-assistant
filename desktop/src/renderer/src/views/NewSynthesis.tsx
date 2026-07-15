import { useReducer } from 'react'
import { initialWizardState, wizardReducer } from './new-synthesis/wizardReducer'
import Step1Sequences from './new-synthesis/Step1Sequences'
import Step2ResidueMW from './new-synthesis/Step2ResidueMW'
import Step3Reagents from './new-synthesis/Step3Reagents'
import Step4Resin from './new-synthesis/Step4Resin'
import Step5Confirm from './new-synthesis/Step5Confirm'

const STEP_LABELS = ['Sequences', 'Residue MW', 'Reagents', 'Resin', 'Confirm'] as const

type StepStatus = 'done' | 'active' | 'upcoming'

function getStepStatus(stepNum: number, currentStep: number): StepStatus {
  if (stepNum < currentStep) return 'done'
  if (stepNum === currentStep) return 'active'
  return 'upcoming'
}

function getStepClassName(status: StepStatus): string {
  if (status === 'done') {
    return 'text-teal bg-teal-dim flex-1 text-center py-2 text-xs font-medium'
  }
  if (status === 'active') {
    return 'text-text bg-bg3 flex-1 text-center py-2 text-xs font-medium'
  }
  return 'text-text3 flex-1 text-center py-2 text-xs font-medium'
}

interface NewSynthesisProps {
  onDone: () => void
}

export default function NewSynthesis({ onDone }: Readonly<NewSynthesisProps>): React.JSX.Element {
  const [state, dispatch] = useReducer(wizardReducer, initialWizardState)

  return (
    <div className="bg-bg p-5">
      <div className="mb-5">
        <h1 className="text-text font-sans text-base font-medium">New synthesis</h1>
        <p className="text-text3 font-sans text-xs">
          Configure parameters before generating guides
        </p>
      </div>

      <div className="flex mb-5">
        {STEP_LABELS.map((label, index) => {
          const stepNum = (index + 1) as 1 | 2 | 3 | 4 | 5
          const status = getStepStatus(stepNum, state.step)
          return (
            <div key={label} className={getStepClassName(status)}>
              <span className="font-mono block">{String(stepNum).padStart(2, '0')}</span>
              {label}
            </div>
          )
        })}
      </div>

      {state.step === 1 && <Step1Sequences state={state} dispatch={dispatch} />}
      {state.step === 2 && <Step2ResidueMW state={state} dispatch={dispatch} />}
      {state.step === 3 && <Step3Reagents state={state} dispatch={dispatch} />}
      {state.step === 4 && <Step4Resin state={state} dispatch={dispatch} />}
      {state.step === 5 && <Step5Confirm state={state} dispatch={dispatch} onDone={onDone} />}
    </div>
  )
}
