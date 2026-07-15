// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Step1Sequences from './Step1Sequences'
import { initialWizardState, wizardReducer, type WizardAction, type WizardState } from './wizardReducer'

function renderStep1(state: WizardState = initialWizardState) {
  let currentState = state
  const dispatch = vi.fn((action: WizardAction) => {
    currentState = wizardReducer(currentState, action)
  })
  const utils = render(<Step1Sequences state={currentState} dispatch={dispatch} />)
  return { ...utils, dispatch, getState: () => currentState }
}

describe('Step1Sequences', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('Continue is disabled until a FASTA file has been parsed', () => {
    vi.stubGlobal('spps', {
      pickFastaFile: vi.fn(),
      pickMaterialsFile: vi.fn(),
      parseSequences: vi.fn()
    })

    renderStep1()

    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled()
  })

  it('parses the picked FASTA file and shows the vessel preview with reversed sequences', async () => {
    vi.stubGlobal('spps', {
      pickFastaFile: vi.fn().mockResolvedValue('/tmp/seqs.fasta'),
      pickMaterialsFile: vi.fn(),
      parseSequences: vi.fn().mockResolvedValue({
        ok: true,
        data: {
          vessels: [
            {
              number: 1,
              name: 'Peptide1',
              original_tokens: ['A', 'G'],
              reversed_tokens: ['G', 'A'],
              resin_mass_g: 0.1,
              substitution_mmol_g: 0.3
            }
          ]
        }
      })
    })
    const user = userEvent.setup()

    renderStep1()
    await user.click(screen.getByRole('button', { name: /browse for fasta file/i }))

    await waitFor(() => expect(screen.getByText(/1 sequence/i)).toBeInTheDocument())
    expect(screen.getByText('AG')).toBeInTheDocument()
    expect(screen.getByText(/reversed: GA/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled()
  })

  it('shows an error banner if parsing fails', async () => {
    vi.stubGlobal('spps', {
      pickFastaFile: vi.fn().mockResolvedValue('/tmp/bad.fasta'),
      pickMaterialsFile: vi.fn(),
      parseSequences: vi.fn().mockResolvedValue({
        ok: false,
        error: { code: 'parse_failed', message: 'Could not parse FASTA file: bad format' }
      })
    })
    const user = userEvent.setup()

    renderStep1()
    await user.click(screen.getByRole('button', { name: /browse for fasta file/i }))

    await waitFor(() =>
      expect(screen.getByText(/could not parse fasta file/i)).toBeInTheDocument()
    )
  })

  it('clicking Continue dispatches SET_STEP to 2', async () => {
    vi.stubGlobal('spps', {
      pickFastaFile: vi.fn().mockResolvedValue('/tmp/seqs.fasta'),
      pickMaterialsFile: vi.fn(),
      parseSequences: vi.fn().mockResolvedValue({
        ok: true,
        data: {
          vessels: [
            {
              number: 1,
              name: 'Pep1',
              original_tokens: ['A'],
              reversed_tokens: ['A'],
              resin_mass_g: 0.1,
              substitution_mmol_g: 0.3
            }
          ]
        }
      })
    })
    const user = userEvent.setup()

    const { dispatch } = renderStep1()
    await user.click(screen.getByRole('button', { name: /browse for fasta file/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled())
    await user.click(screen.getByRole('button', { name: /continue/i }))

    expect(dispatch).toHaveBeenCalledWith({ type: 'SET_STEP', step: 2 })
  })
})
