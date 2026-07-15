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

  it('renders all 5 tabs with only Dashboard and New synthesis enabled', async () => {
    stubSpps()

    const { container } = render(<App />)
    const nav = within(container.querySelector('nav')!)

    const dashboardTab = nav.getByText('Dashboard')
    expect(dashboardTab.className).toContain('text-teal')

    const newSynthesisTab = nav.getByText('New synthesis')
    expect(newSynthesisTab.className).not.toContain('cursor-not-allowed')

    for (const label of ['Cycle guide', 'Materials', 'Peptide info']) {
      const tab = nav.getByText(label)
      expect(tab.className).toContain('cursor-not-allowed')
    }

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument())
  })

  it('clicking the New synthesis tab switches to the wizard', async () => {
    stubSpps()
    const user = userEvent.setup()

    render(<App />)
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument())

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
})
