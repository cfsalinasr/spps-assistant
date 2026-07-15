// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Step2ResidueMW from './Step2ResidueMW'
import { initialWizardState, wizardReducer, type WizardAction, type WizardState } from './wizardReducer'

const TWO_VESSEL_STATE: WizardState = {
  ...initialWizardState,
  fastaPath: '/tmp/seqs.fasta',
  vessels: [
    {
      number: 1,
      name: 'Pep1',
      original_tokens: ['A', 'G'],
      reversed_tokens: ['G', 'A'],
      resin_mass_g: 0.1,
      substitution_mmol_g: 0.3
    }
  ]
}

function renderStep2(state: WizardState) {
  let currentState = state
  let utils: any
  const dispatch = vi.fn((action: WizardAction) => {
    currentState = wizardReducer(currentState, action)
    utils.rerender(<Step2ResidueMW state={currentState} dispatch={dispatch} />)
  })
  utils = render(<Step2ResidueMW state={currentState} dispatch={dispatch} />)
  return { ...utils, dispatch, getState: () => currentState }
}

describe('Step2ResidueMW', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fills in unique tokens from the DB and marks them origin db', async () => {
    vi.stubGlobal('spps', {
      getResidues: vi.fn().mockResolvedValue({
        ok: true,
        data: [
          { token: 'A', base_code: 'A', protection: '', fmoc_mw: 311.3, free_mw: 71.08 },
          { token: 'G', base_code: 'G', protection: '', fmoc_mw: 297.3, free_mw: 57.05 }
        ]
      }),
      saveResidue: vi.fn()
    })

    renderStep2(TWO_VESSEL_STATE)

    await waitFor(() => expect(screen.getByDisplayValue('311.3')).toBeInTheDocument())
    expect(screen.getByDisplayValue('297.3')).toBeInTheDocument()
  })

  it('does not overwrite a token already seeded from a materials file', async () => {
    const stateWithMaterialsToken: WizardState = {
      ...TWO_VESSEL_STATE,
      materialsPath: '/tmp/mats.csv',
      residueMap: {
        A: { token: 'A', base_code: 'A', protection: '', fmoc_mw: 999.9, free_mw: 888.8, origin: 'materials' }
      }
    }
    vi.stubGlobal('spps', {
      getResidues: vi.fn().mockResolvedValue({
        ok: true,
        data: [{ token: 'A', base_code: 'A', protection: '', fmoc_mw: 1.0, free_mw: 1.0 }]
      }),
      saveResidue: vi.fn()
    })

    renderStep2(stateWithMaterialsToken)

    await waitFor(() => expect(screen.getByDisplayValue('999.9')).toBeInTheDocument())
  })

  it('Continue is disabled until every unique token has a non-zero MW', async () => {
    vi.stubGlobal('spps', {
      getResidues: vi.fn().mockResolvedValue({ ok: true, data: [] }),
      saveResidue: vi.fn()
    })

    renderStep2(TWO_VESSEL_STATE)

    await waitFor(() => expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled())
  })

  it('Continue saves only non-materials rows to the DB, then advances to step 3', async () => {
    const saveResidue = vi.fn().mockResolvedValue({ ok: true, data: {} })
    vi.stubGlobal('spps', {
      getResidues: vi.fn().mockResolvedValue({
        ok: true,
        data: [
          { token: 'A', base_code: 'A', protection: '', fmoc_mw: 311.3, free_mw: 71.08 },
          { token: 'G', base_code: 'G', protection: '', fmoc_mw: 297.3, free_mw: 57.05 }
        ]
      }),
      saveResidue
    })
    const user = userEvent.setup()

    const { dispatch } = renderStep2(TWO_VESSEL_STATE)
    await waitFor(() => expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled())
    await user.click(screen.getByRole('button', { name: /continue/i }))

    expect(saveResidue).toHaveBeenCalledTimes(2)
    expect(dispatch).toHaveBeenCalledWith({ type: 'SET_STEP', step: 3 })
  })
})
