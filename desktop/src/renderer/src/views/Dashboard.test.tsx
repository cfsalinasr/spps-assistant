// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Dashboard from './Dashboard'

function baseStub(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    getConfig: () => Promise.resolve({ ok: true, data: {} }),
    setConfig: () => Promise.resolve({ ok: true, data: {} }),
    getLastSynthesis: () => Promise.resolve({ ok: true, data: null }),
    ...overrides
  }
}

describe('Dashboard', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a loading state, then the fetched config values once loaded', async () => {
    vi.stubGlobal(
      'spps',
      baseStub({
        getConfig: () =>
          Promise.resolve({
            ok: true,
            data: {
              activator: 'HBTU',
              base: 'DIEA',
              deprotection_reagent: 'Piperidine 20%',
              aa_equivalents: 3.0,
              vessel_method: 'Teabag'
            }
          })
      })
    )

    render(<Dashboard onNewSynthesis={() => {}} />)

    expect(screen.getByText(/loading/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('HBTU')).toBeInTheDocument()
    })
    expect(screen.getByText('DIEA')).toBeInTheDocument()
    expect(screen.getByText('Piperidine 20%')).toBeInTheDocument()
    expect(screen.getByText('Teabag')).toBeInTheDocument()
  })

  it('shows an error state if the sidecar call fails', async () => {
    vi.stubGlobal('spps', baseStub({ getConfig: () => Promise.reject(new Error('sidecar unreachable')) }))

    render(<Dashboard onNewSynthesis={() => {}} />)

    await waitFor(() => {
      expect(screen.getByText(/couldn.t load configuration/i)).toBeInTheDocument()
    })
  })

  it('shows an empty state with a New Synthesis call to action when none has been generated', async () => {
    vi.stubGlobal(
      'spps',
      baseStub({ getConfig: () => Promise.resolve({ ok: true, data: { activator: 'HBTU' } }) })
    )

    render(<Dashboard onNewSynthesis={() => {}} />)

    await waitFor(() => {
      expect(screen.getByText(/no active synthes/i)).toBeInTheDocument()
    })
    // Two "+ New synthesis" buttons are expected by design: one always-visible
    // in the page header, one contextual inside the empty-state card.
    const newSynthesisButtons = screen.getAllByRole('button', { name: /new synthesis/i })
    expect(newSynthesisButtons).toHaveLength(2)
  })

  it('shows the last generated synthesis instead of the empty state when one exists', async () => {
    vi.stubGlobal(
      'spps',
      baseStub({
        getConfig: () => Promise.resolve({ ok: true, data: {} }),
        getLastSynthesis: () =>
          Promise.resolve({
            ok: true,
            data: {
              name: 'BatchA',
              output_directory: '/tmp/out',
              generated_at: '2026-07-13T00:00:00',
              vessel_count: 2
            }
          })
      })
    )

    render(<Dashboard onNewSynthesis={() => {}} />)

    await waitFor(() => {
      expect(screen.getByText('BatchA')).toBeInTheDocument()
    })
    expect(screen.queryByText(/no active synthes/i)).not.toBeInTheDocument()
  })
})
