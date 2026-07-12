// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

describe('App', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders all 5 tabs with only Dashboard active', async () => {
    vi.stubGlobal('spps', {
      getConfig: () => Promise.resolve({ ok: true, data: {} }),
      setConfig: () => Promise.resolve({ ok: true, data: {} })
    })

    const { container } = render(<App />)
    const nav = within(container.querySelector('nav')!)

    const dashboardTab = nav.getByText('Dashboard')
    expect(dashboardTab.className).toContain('text-teal')
    expect(dashboardTab.className).not.toContain('cursor-not-allowed')

    for (const label of ['New synthesis', 'Cycle guide', 'Materials', 'Peptide info']) {
      const tab = nav.getByText(label)
      expect(tab.className).toContain('cursor-not-allowed')
    }

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    )
  })

  it('renders the Dashboard view content', async () => {
    vi.stubGlobal('spps', {
      getConfig: () => Promise.resolve({ ok: true, data: {} }),
      setConfig: () => Promise.resolve({ ok: true, data: {} })
    })

    render(<App />)

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    )
  })
})
