// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

function stubSpps(): void {
  vi.stubGlobal('spps', {
    getConfig: () => Promise.resolve({ ok: true, data: {} }),
    setConfig: () => Promise.resolve({ ok: true, data: {} }),
    getLastSynthesis: () => Promise.resolve({ ok: true, data: null }),
    pickFastaFile: vi.fn().mockResolvedValue(null)
  })
}

describe('App', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders all 5 tabs with only Dashboard, New synthesis, and Peptide info enabled', async () => {
    stubSpps()

    const { container } = render(<App />)
    const nav = within(container.querySelector('nav')!)

    const dashboardTab = nav.getByText('Dashboard')
    expect(dashboardTab.className).toContain('text-teal')

    for (const label of ['New synthesis', 'Peptide info']) {
      const tab = nav.getByText(label)
      expect(tab.className).not.toContain('cursor-not-allowed')
    }

    for (const label of ['Cycle guide', 'Materials']) {
      const tab = nav.getByText(label)
      expect(tab.className).toContain('cursor-not-allowed')
    }

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    )
  })

  it('clicking the Peptide info tab shows the stub view', async () => {
    stubSpps()
    const user = userEvent.setup()

    render(<App />)
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    )

    await user.click(screen.getByText('Peptide info'))

    expect(screen.getByText('Coming in a future release.')).toBeInTheDocument()
  })

  it('clicking the New synthesis tab switches to the wizard', async () => {
    stubSpps()
    const user = userEvent.setup()

    render(<App />)
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    )

    await user.click(screen.getByText('New synthesis'))

    expect(screen.getByRole('heading', { name: 'New synthesis' })).toBeInTheDocument()
  })

  it('clicking Dashboard\'s "+ New synthesis" button also switches to the wizard', async () => {
    stubSpps()
    const user = userEvent.setup()

    render(<App />)
    await waitFor(() =>
      expect(screen.getAllByRole('button', { name: /new synthesis/i })[0]).toBeInTheDocument()
    )

    await user.click(screen.getAllByRole('button', { name: /new synthesis/i })[0])

    expect(screen.getByRole('heading', { name: 'New synthesis' })).toBeInTheDocument()
  })

  it('enables the Cycle guide tab once a synthesis exists', async () => {
    vi.stubGlobal('spps', {
      getConfig: () => Promise.resolve({ ok: true, data: {} }),
      setConfig: () => Promise.resolve({ ok: true, data: {} }),
      getLastSynthesis: () =>
        Promise.resolve({
          ok: true,
          data: {
            name: 'TestRun',
            output_directory: '/tmp/out',
            generated_at: '2026-01-01T00:00:00+00:00',
            vessel_count: 1,
            cycle_guide: { synthesis_name: 'TestRun', date_str: '2026-01-01', cycles: [] },
            current_cycle: 1
          }
        }),
      pickFastaFile: vi.fn().mockResolvedValue(null)
    })

    const { container } = render(<App />)
    const nav = within(container.querySelector('nav')!)

    await waitFor(() => {
      const tab = nav.getByText('Cycle guide')
      expect(tab.className).not.toContain('cursor-not-allowed')
    })
  })

  it('enables the Materials tab once a synthesis with materials data exists', async () => {
    vi.stubGlobal('spps', {
      getConfig: () => Promise.resolve({ ok: true, data: {} }),
      setConfig: () => Promise.resolve({ ok: true, data: {} }),
      getLastSynthesis: () =>
        Promise.resolve({
          ok: true,
          data: {
            name: 'TestRun',
            output_directory: '/tmp/out',
            generated_at: '2026-01-01T00:00:00+00:00',
            vessel_count: 1,
            materials: { synthesis_name: 'TestRun', rows: [], total_residue_types: 0, total_mass_mg: 0, total_volume_ml: 0, config_summary: {} }
          }
        }),
      pickFastaFile: vi.fn().mockResolvedValue(null)
    })

    const { container } = render(<App />)
    const nav = within(container.querySelector('nav')!)

    await waitFor(() => {
      const tab = nav.getByText('Materials')
      expect(tab.className).not.toContain('cursor-not-allowed')
    })
  })

  it('enables the Cycle guide tab after viewing it from Dashboard mid-session, even with no synthesis at mount', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('spps', {
      getConfig: () => Promise.resolve({ ok: true, data: {} }),
      setConfig: () => Promise.resolve({ ok: true, data: {} }),
      getLastSynthesis: () =>
        Promise.resolve({
          ok: true,
          data: {
            name: 'TestRun',
            output_directory: '/tmp/out',
            generated_at: '2026-01-01T00:00:00+00:00',
            vessel_count: 1,
            current_cycle: 1
          }
        }),
      pickFastaFile: vi.fn().mockResolvedValue(null)
    })

    const { container } = render(<App />)
    const nav = within(container.querySelector('nav')!)

    await waitFor(() => {
      expect(nav.getByText('Cycle guide').className).toContain('cursor-not-allowed')
    })

    await user.click(await screen.findByRole('button', { name: /view cycle guide/i }))

    await waitFor(() => {
      expect(nav.getByText('Cycle guide').className).not.toContain('cursor-not-allowed')
    })
  })
})
