// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CycleGuide from './CycleGuide'
import type { CycleGuideData } from '../../../preload/index.d'

function makeGuide(): CycleGuideData {
  return {
    synthesis_name: 'TestRun',
    date_str: '2026-01-01',
    cycles: [
      {
        cycle_number: 1,
        total_cycles: 2,
        dispatch_rows: [
          {
            residue_3letter: 'Ala',
            fmoc_mw: 311.3,
            mmol: 0.09,
            volume_ml: 0.6,
            formula_shown: 'V = ...',
            vessel_numbers: [1]
          }
        ],
        deprotection_steps: [
          { label: '1. Deprotection', detail: 'Piperidine 20% in DMF', n_checkboxes: 2, duration: '2 × 10 min' }
        ],
        coupling_steps: [
          { label: '1st coupling', detail: 'Ala + HBTU + Oxyma + DIEA', n_checkboxes: 1, duration: '30 min' },
          { label: 'Post-coupling wash', detail: 'DMF, DCM', n_checkboxes: 0, duration: '5 min' }
        ],
        vessel_assignments: [{ vessel_number: 1, vessel_name: 'Pep1', residue_3letter: 'Ala' }],
        secondary_coupling_rows: null
      },
      {
        cycle_number: 2,
        total_cycles: 2,
        dispatch_rows: [],
        deprotection_steps: [],
        coupling_steps: [],
        vessel_assignments: [{ vessel_number: 1, vessel_name: 'Pep1', residue_3letter: null }],
        secondary_coupling_rows: null
      }
    ]
  }
}

function stubSpps(overrides: Record<string, unknown> = {}): void {
  vi.stubGlobal('spps', {
    getLastSynthesis: () =>
      Promise.resolve({
        ok: true,
        data: {
          name: 'TestRun',
          output_directory: '/tmp/out',
          generated_at: '2026-01-01T00:00:00+00:00',
          vessel_count: 1,
          output_paths: { cycle_guide_pdf: '/tmp/out/guide.pdf', cycle_guide_docx: '/tmp/out/guide.docx' },
          current_cycle: 1,
          cycle_guide: makeGuide()
        }
      }),
    setCyclePosition: vi.fn().mockResolvedValue({ ok: true, data: { current_cycle: 1 } }),
    openFile: vi.fn().mockResolvedValue(''),
    ...overrides
  })
}

describe('CycleGuide', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the seeded current cycle', async () => {
    stubSpps()
    render(<CycleGuide onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('of 2 total cycles')).toBeInTheDocument()
    // 'Ala' legitimately appears twice (dispatch row + vessel assignment for
    // this fixture), so scope to the dispatch table to disambiguate.
    expect(within(screen.getByRole('table')).getByText('Ala')).toBeInTheDocument()
  })

  it('Prev is disabled on the first cycle, Next is enabled', async () => {
    stubSpps()
    render(<CycleGuide onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /prev/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /next/i })).not.toBeDisabled()
  })

  it('clicking Next advances the cycle and saves the position', async () => {
    stubSpps()
    const user = userEvent.setup()
    render(<CycleGuide onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /next/i }))

    await waitFor(() => expect(screen.getByText('of 2 total cycles')).toBeInTheDocument())
    expect(window.spps.setCyclePosition).toHaveBeenCalledWith(2)
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled()
  })

  it('clicking Export PDF opens the real generated file', async () => {
    stubSpps()
    const user = userEvent.setup()
    render(<CycleGuide onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /export pdf/i }))

    expect(window.spps.openFile).toHaveBeenCalledWith('/tmp/out/guide.pdf')
  })

  it('shows an error message when opening the exported file fails', async () => {
    stubSpps({
      openFile: vi.fn().mockResolvedValue('No application is set to open this file.')
    })
    const user = userEvent.setup()
    render(<CycleGuide onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /export pdf/i }))

    await waitFor(() =>
      expect(screen.getByText(/no application is set/i)).toBeInTheDocument()
    )
  })

  it('shows an empty state and a New synthesis button when no synthesis exists', async () => {
    stubSpps({ getLastSynthesis: () => Promise.resolve({ ok: true, data: null }) })
    const onNewSynthesis = vi.fn()
    const user = userEvent.setup()
    render(<CycleGuide onNewSynthesis={onNewSynthesis} />)

    await waitFor(() => expect(screen.getByText(/no active synthesis/i)).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /new synthesis/i }))
    expect(onNewSynthesis).toHaveBeenCalled()
  })

  it('shows an empty state instead of crashing when cycle_guide has zero cycles', async () => {
    stubSpps({
      getLastSynthesis: () =>
        Promise.resolve({
          ok: true,
          data: {
            name: 'TestRun',
            output_directory: '/tmp/out',
            generated_at: '2026-01-01T00:00:00+00:00',
            vessel_count: 1,
            output_paths: {},
            current_cycle: 1,
            cycle_guide: { synthesis_name: 'TestRun', date_str: '2026-01-01', cycles: [] }
          }
        })
    })
    render(<CycleGuide onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText(/no active synthesis/i)).toBeInTheDocument())
  })
})
