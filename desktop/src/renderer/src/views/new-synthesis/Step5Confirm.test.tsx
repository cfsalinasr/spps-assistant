// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor, type RenderResult } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Step5Confirm from './Step5Confirm'
import {
  initialWizardState,
  wizardReducer,
  type WizardAction,
  type WizardState
} from './wizardReducer'

const READY_STATE: WizardState = {
  ...initialWizardState,
  fastaPath: '/tmp/seqs.fasta',
  outputDirectory: '/tmp/output',
  vessels: [
    {
      number: 1,
      name: 'Pep1',
      original_tokens: ['A'],
      reversed_tokens: ['A'],
      resin_mass_g: 0.1,
      substitution_mmol_g: 0.3
    }
  ],
  residueMap: {
    A: { token: 'A', base_code: 'A', protection: '', fmoc_mw: 311.3, free_mw: 71.08, origin: 'db' }
  }
}

function renderStep5(
  state: WizardState,
  onDone = vi.fn(),
  onViewCycleGuide = vi.fn(),
  onViewMaterials = vi.fn()
): Omit<RenderResult, 'rerender'> & {
  dispatch: ReturnType<typeof vi.fn>
  onDone: ReturnType<typeof vi.fn>
  onViewCycleGuide: ReturnType<typeof vi.fn>
  onViewMaterials: ReturnType<typeof vi.fn>
  rerender: (ui: React.ReactElement) => void
  getState: () => WizardState
} {
  let currentState = state
  const dispatch = vi.fn()
  const { rerender, ...utils } = render(
    <Step5Confirm
      state={currentState}
      dispatch={dispatch}
      onDone={onDone}
      onViewCycleGuide={onViewCycleGuide}
      onViewMaterials={onViewMaterials}
    />
  )

  dispatch.mockImplementation((action: WizardAction) => {
    currentState = wizardReducer(currentState, action)
    rerender(
      <Step5Confirm
        state={currentState}
        dispatch={dispatch}
        onDone={onDone}
        onViewCycleGuide={onViewCycleGuide}
        onViewMaterials={onViewMaterials}
      />
    )
  })

  return { ...utils, dispatch, onDone, onViewCycleGuide, onViewMaterials, rerender, getState: () => currentState }
}

describe('Step5Confirm', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a raw-selection summary of Steps 1-4', () => {
    vi.stubGlobal('spps', {
      generateSynthesis: vi.fn(),
      pickOutputDirectory: vi.fn(),
      openFolder: vi.fn()
    })

    renderStep5(READY_STATE)

    expect(screen.getByText(/1 vessel/i)).toBeInTheDocument()
    expect(screen.getByText(/1 unique token/i)).toBeInTheDocument()
    expect(screen.getByText(/HBTU \/ DIEA \/ Piperidine 20%/)).toBeInTheDocument()
  })

  it('Generate calls generateSynthesis with the accumulated wizard state and shows a success state', async () => {
    const generateSynthesis = vi.fn().mockResolvedValue({
      ok: true,
      data: { cycle_guide_pdf: '/tmp/output/Test_cycle_guide.pdf' }
    })
    vi.stubGlobal('spps', { generateSynthesis, pickOutputDirectory: vi.fn(), openFolder: vi.fn() })
    const user = userEvent.setup()

    renderStep5(READY_STATE)
    await user.type(screen.getByLabelText(/synthesis name/i), 'X')
    await user.click(screen.getByRole('button', { name: /generate/i }))

    await waitFor(() => expect(screen.getByText(/generated successfully/i)).toBeInTheDocument())
    expect(generateSynthesis).toHaveBeenCalledTimes(1)
    const payload = generateSynthesis.mock.calls[0][0]
    expect(payload.vessels).toHaveLength(1)
    expect(payload.residue_info_map.A.fmoc_mw).toBe(311.3)
    expect(payload.config_overrides.output_directory).toBe('/tmp/output')
  })

  it('shows an error banner if generation fails, without losing the entered data', async () => {
    const generateSynthesis = vi.fn().mockResolvedValue({
      ok: false,
      error: { code: 'generate_failed', message: 'Disk full' }
    })
    vi.stubGlobal('spps', { generateSynthesis, pickOutputDirectory: vi.fn(), openFolder: vi.fn() })
    const user = userEvent.setup()

    renderStep5(READY_STATE)
    await user.click(screen.getByRole('button', { name: /generate/i }))

    await waitFor(() => expect(screen.getByText('Disk full')).toBeInTheDocument())
    expect(screen.getByText(/1 vessel/i)).toBeInTheDocument()
  })

  it('clicking Done after a successful generate calls onDone', async () => {
    const generateSynthesis = vi.fn().mockResolvedValue({
      ok: true,
      data: { cycle_guide_pdf: '/tmp/output/Test_cycle_guide.pdf' }
    })
    vi.stubGlobal('spps', { generateSynthesis, pickOutputDirectory: vi.fn(), openFolder: vi.fn() })
    const user = userEvent.setup()

    const { onDone } = renderStep5(READY_STATE)
    await user.click(screen.getByRole('button', { name: /generate/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /^done$/i })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /^done$/i }))

    expect(onDone).toHaveBeenCalledTimes(1)
  })

  it('clicking Open folder calls window.spps.openFolder with a generated path', async () => {
    const openFolder = vi.fn().mockResolvedValue(undefined)
    const generateSynthesis = vi.fn().mockResolvedValue({
      ok: true,
      data: { cycle_guide_pdf: '/tmp/output/Test_cycle_guide.pdf' }
    })
    vi.stubGlobal('spps', { generateSynthesis, pickOutputDirectory: vi.fn(), openFolder })
    const user = userEvent.setup()

    renderStep5(READY_STATE)
    await user.click(screen.getByRole('button', { name: /generate/i }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /open folder/i })).toBeInTheDocument()
    )
    await user.click(screen.getByRole('button', { name: /open folder/i }))

    expect(openFolder).toHaveBeenCalledWith('/tmp/output/Test_cycle_guide.pdf')
  })

  it('shows an error if generateSynthesis rejects with an exception', async () => {
    const generateSynthesis = vi.fn().mockRejectedValue(new Error('sidecar crashed'))
    vi.stubGlobal('spps', { generateSynthesis, pickOutputDirectory: vi.fn(), openFolder: vi.fn() })
    const user = userEvent.setup()

    renderStep5(READY_STATE)
    await user.click(screen.getByRole('button', { name: /generate/i }))

    await waitFor(() => expect(screen.getByText(/sidecar crashed/i)).toBeInTheDocument())
    // Generate button should be re-enabled
    expect(screen.getByRole('button', { name: /generate/i })).not.toBeDisabled()
  })

  it('clicking "View cycle guide" calls onViewCycleGuide', async () => {
    const generateSynthesis = vi.fn().mockResolvedValue({
      ok: true,
      data: { cycle_guide_pdf: '/tmp/output/Test_cycle_guide.pdf' }
    })
    vi.stubGlobal('spps', { generateSynthesis, pickOutputDirectory: vi.fn(), openFolder: vi.fn() })
    const user = userEvent.setup()

    const { onViewCycleGuide } = renderStep5(READY_STATE)
    await user.click(screen.getByRole('button', { name: /generate/i }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /view cycle guide/i })).toBeInTheDocument()
    )
    await user.click(screen.getByRole('button', { name: /view cycle guide/i }))

    expect(onViewCycleGuide).toHaveBeenCalledTimes(1)
  })

  it('clicking "View materials" calls onViewMaterials', async () => {
    const generateSynthesis = vi.fn().mockResolvedValue({
      ok: true,
      data: { materials_xlsx: '/tmp/output/Test_materials.xlsx' }
    })
    vi.stubGlobal('spps', { generateSynthesis, pickOutputDirectory: vi.fn(), openFolder: vi.fn() })
    const user = userEvent.setup()

    const { onViewMaterials } = renderStep5(READY_STATE)
    await user.click(screen.getByRole('button', { name: /generate/i }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /view materials/i })).toBeInTheDocument()
    )
    await user.click(screen.getByRole('button', { name: /view materials/i }))

    expect(onViewMaterials).toHaveBeenCalledTimes(1)
  })
})
