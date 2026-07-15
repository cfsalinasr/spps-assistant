// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, type RenderResult } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Step3Reagents from './Step3Reagents'
import {
  initialWizardState,
  wizardReducer,
  type WizardAction,
  type WizardState
} from './wizardReducer'

function renderStep3(state: WizardState = initialWizardState): RenderResult & {
  dispatch: ReturnType<typeof vi.fn>
  getState: () => WizardState
  rerenderWithLatest: () => WizardState
} {
  let currentState = state
  const dispatch = vi.fn((action: WizardAction) => {
    currentState = wizardReducer(currentState, action)
  })
  const utils = render(<Step3Reagents state={currentState} dispatch={dispatch} />)
  return {
    ...utils,
    dispatch,
    getState: () => currentState,
    rerenderWithLatest: () => currentState
  }
}

describe('Step3Reagents', () => {
  it('renders the default activator, base, and deprotection reagent as active', () => {
    renderStep3()

    expect(screen.getByText('HBTU').className).toContain('text-teal')
    expect(screen.getByText('DIEA').className).toContain('text-teal')
    expect(screen.getByText('Piperidine 20%').className).toContain('text-teal')
  })

  it('clicking a deprotection reagent pill dispatches SET_REAGENTS', async () => {
    const user = userEvent.setup()
    const { dispatch } = renderStep3()

    await user.click(screen.getByText('Piperazine 20%'))

    expect(dispatch).toHaveBeenCalledWith({
      type: 'SET_REAGENTS',
      reagents: { deprotectionReagent: 'Piperazine 20%' }
    })
  })

  it('selecting DIC as activator switches base options to only "None (DIC/DCC)"', async () => {
    const user = userEvent.setup()
    let state = initialWizardState
    const dispatch = vi.fn((action: WizardAction) => {
      state = wizardReducer(state, action)
    })
    const { rerender } = render(<Step3Reagents state={state} dispatch={dispatch} />)

    await user.click(screen.getByText('DIC'))
    rerender(<Step3Reagents state={state} dispatch={dispatch} />)

    expect(screen.queryByText('DIEA')).not.toBeInTheDocument()
    expect(screen.queryByText('Pyridine')).not.toBeInTheDocument()
    expect(screen.getByText('None (DIC/DCC)').className).toContain('text-teal')
  })

  it('switching back to HBTU after DIC restores the standard base options', async () => {
    const user = userEvent.setup()
    let state = initialWizardState
    const dispatch = vi.fn((action: WizardAction) => {
      state = wizardReducer(state, action)
    })
    const { rerender } = render(<Step3Reagents state={state} dispatch={dispatch} />)

    await user.click(screen.getByText('DIC'))
    rerender(<Step3Reagents state={state} dispatch={dispatch} />)
    await user.click(screen.getByText('HBTU'))
    rerender(<Step3Reagents state={state} dispatch={dispatch} />)

    expect(screen.getByText('DIEA')).toBeInTheDocument()
    expect(screen.getByText('Pyridine')).toBeInTheDocument()
  })

  it('Back dispatches SET_STEP to 2, Continue dispatches SET_STEP to 4', async () => {
    const user = userEvent.setup()
    const { dispatch } = renderStep3()

    await user.click(screen.getByRole('button', { name: /back/i }))
    expect(dispatch).toHaveBeenCalledWith({ type: 'SET_STEP', step: 2 })

    await user.click(screen.getByRole('button', { name: /continue/i }))
    expect(dispatch).toHaveBeenCalledWith({ type: 'SET_STEP', step: 4 })
  })
})
