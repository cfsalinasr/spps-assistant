// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Materials from './Materials'
import type { MaterialsViewData } from '../../../preload/index.d'

function makeMaterials(): MaterialsViewData {
  return {
    synthesis_name: 'TestRun',
    rows: [
      {
        token: 'A',
        protection: '',
        fmoc_mw: 311.3,
        mmol_needed: 0.18,
        mass_mg: 105.4,
        stock_conc: 0.5,
        volume_ml: 0.36,
        notes: 'Fmoc-Ala-OH',
        formula: 'V = ...',
        volume_ul: null
      },
      {
        token: 'G',
        protection: '',
        fmoc_mw: 297.3,
        mmol_needed: 0.24,
        mass_mg: 71.4,
        stock_conc: 0.5,
        volume_ml: 0.48,
        notes: 'Fmoc-Gly-OH',
        formula: 'V = ...',
        volume_ul: null
      }
    ],
    total_residue_types: 2,
    total_mass_mg: 176.8,
    total_volume_ml: 0.84,
    config_summary: { Activator: 'HBTU', 'AA Equivalents': '3.0', 'Volume Mode': 'stoichiometry', Base: 'DIEA' }
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
          output_paths: { materials_xlsx: '/tmp/out/mats.xlsx', materials_pdf: '/tmp/out/mats.pdf' },
          materials: makeMaterials()
        }
      }),
    openFile: vi.fn().mockResolvedValue(''),
    ...overrides
  })
}

describe('Materials', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the synthesis name and stat cards', async () => {
    stubSpps()
    render(<Materials onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    expect(screen.getByText('2')).toBeInTheDocument() // total_residue_types
    expect(screen.getByText(/176.8/)).toBeInTheDocument() // total_mass_mg
    expect(screen.getByText(/0.84/)).toBeInTheDocument() // total_volume_ml
  })

  it('renders one requirements row per residue', async () => {
    stubSpps()
    render(<Materials onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    expect(screen.getByText('A')).toBeInTheDocument()
    expect(screen.getByText('G')).toBeInTheDocument()
  })

  it('renders the calculation-basis config summary', async () => {
    stubSpps()
    render(<Materials onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    expect(screen.getByText('HBTU')).toBeInTheDocument()
    expect(screen.getByText('DIEA')).toBeInTheDocument()
  })

  it('clicking Export XLSX opens the real generated file', async () => {
    const openFile = vi.fn().mockResolvedValue('')
    stubSpps({ openFile })
    const user = userEvent.setup()
    render(<Materials onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /export xlsx/i }))
    expect(openFile).toHaveBeenCalledWith('/tmp/out/mats.xlsx')
  })

  it('shows an error message when opening the exported file fails', async () => {
    const openFile = vi.fn().mockResolvedValue('File not found.')
    stubSpps({ openFile })
    const user = userEvent.setup()
    render(<Materials onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText('TestRun')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /export pdf/i }))
    await waitFor(() => expect(screen.getByText('File not found.')).toBeInTheDocument())
  })

  it('shows an empty state and a New synthesis button when no synthesis exists', async () => {
    stubSpps()
    vi.stubGlobal('spps', {
      getLastSynthesis: () => Promise.resolve({ ok: true, data: null }),
      openFile: vi.fn()
    })
    const onNewSynthesis = vi.fn()
    render(<Materials onNewSynthesis={onNewSynthesis} />)

    await waitFor(() => expect(screen.getByText(/no active synthesis/i)).toBeInTheDocument())
    await userEvent.setup().click(screen.getByRole('button', { name: /new synthesis/i }))
    expect(onNewSynthesis).toHaveBeenCalled()
  })

  it('shows an error state instead of crashing when getLastSynthesis rejects', async () => {
    vi.stubGlobal('spps', {
      getLastSynthesis: () => Promise.reject(new Error('sidecar down')),
      openFile: vi.fn()
    })
    render(<Materials onNewSynthesis={() => {}} />)

    await waitFor(() => expect(screen.getByText(/sidecar running/i)).toBeInTheDocument())
  })
})
