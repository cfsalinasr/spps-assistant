// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Dashboard from './Dashboard'

describe('Dashboard', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows a loading state, then the fetched config values once loaded', async () => {
    vi.stubGlobal('spps', {
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
        }),
      setConfig: () => Promise.resolve({ ok: true, data: {} })
    })

    render(<Dashboard />)

    expect(screen.getByText(/loading/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('HBTU')).toBeInTheDocument()
    })
    expect(screen.getByText('DIEA')).toBeInTheDocument()
    expect(screen.getByText('Piperidine 20%')).toBeInTheDocument()
    expect(screen.getByText('Teabag')).toBeInTheDocument()
  })

  it('shows an error state if the sidecar call fails', async () => {
    vi.stubGlobal('spps', {
      getConfig: () => Promise.reject(new Error('sidecar unreachable')),
      setConfig: () => Promise.resolve({ ok: true, data: {} })
    })

    render(<Dashboard />)

    await waitFor(() => {
      expect(screen.getByText(/couldn.t load configuration/i)).toBeInTheDocument()
    })
  })

  it('shows an empty state for active syntheses, with a New Synthesis call to action', async () => {
    vi.stubGlobal('spps', {
      getConfig: () => Promise.resolve({ ok: true, data: { activator: 'HBTU' } }),
      setConfig: () => Promise.resolve({ ok: true, data: {} })
    })

    render(<Dashboard />)

    await waitFor(() => {
      expect(screen.getByText(/no active synthes/i)).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /new synthesis/i })).toBeInTheDocument()
  })
})
