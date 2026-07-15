// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, type RenderResult } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Step4Resin from './Step4Resin'
import {
  initialWizardState,
  wizardReducer,
  type WizardAction,
  type WizardState
} from './wizardReducer'

function renderStep4(state: WizardState = initialWizardState): RenderResult & {
  dispatch: ReturnType<typeof vi.fn>
} {
  let currentState = state
  const dispatch = vi.fn((action: WizardAction) => {
    currentState = wizardReducer(currentState, action)
  })
  const utils = render(<Step4Resin state={currentState} dispatch={dispatch} />)
  return { ...utils, dispatch }
}

describe('Step4Resin', () => {
  it('shows the fixed-mass input by default and Continue is enabled with valid defaults', () => {
    renderStep4()

    expect(screen.getByLabelText(/resin mass per vessel/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/target yield/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled()
  })

  it('switching to target yield shows the target yield input instead of resin mass', async () => {
    const user = userEvent.setup()
    let state = initialWizardState
    const dispatch = vi.fn((action: WizardAction) => {
      state = wizardReducer(state, action)
    })
    const { rerender } = render(<Step4Resin state={state} dispatch={dispatch} />)

    await user.click(screen.getByRole('button', { name: /target yield/i }))
    rerender(<Step4Resin state={state} dispatch={dispatch} />)

    expect(screen.queryByLabelText(/resin mass per vessel/i)).not.toBeInTheDocument()
    expect(screen.getByLabelText(/target yield/i)).toBeInTheDocument()
  })

  it('Continue is disabled when target yield is selected but not set', async () => {
    const user = userEvent.setup()
    let state = initialWizardState
    const dispatch = vi.fn((action: WizardAction) => {
      state = wizardReducer(state, action)
    })
    const { rerender } = render(<Step4Resin state={state} dispatch={dispatch} />)

    await user.click(screen.getByRole('button', { name: /target yield/i }))
    rerender(<Step4Resin state={state} dispatch={dispatch} />)

    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled()
  })

  it('Back dispatches SET_STEP to 3, Continue dispatches SET_STEP to 5', async () => {
    const user = userEvent.setup()
    const { dispatch } = renderStep4()

    await user.click(screen.getByRole('button', { name: /back/i }))
    expect(dispatch).toHaveBeenCalledWith({ type: 'SET_STEP', step: 3 })

    await user.click(screen.getByRole('button', { name: /continue/i }))
    expect(dispatch).toHaveBeenCalledWith({ type: 'SET_STEP', step: 5 })
  })
})
