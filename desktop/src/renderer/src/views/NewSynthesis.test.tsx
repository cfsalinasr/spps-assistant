// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import NewSynthesis from './NewSynthesis'

function stubSpps(): void {
  vi.stubGlobal('spps', {
    pickFastaFile: vi.fn().mockResolvedValue('/tmp/seqs.fasta'),
    pickMaterialsFile: vi.fn().mockResolvedValue(null),
    pickOutputDirectory: vi.fn().mockResolvedValue('/tmp/output'),
    openFolder: vi.fn().mockResolvedValue(undefined),
    parseSequences: vi.fn().mockResolvedValue({
      ok: true,
      data: {
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
    }),
    getResidues: vi.fn().mockResolvedValue({
      ok: true,
      data: [
        { token: 'A', base_code: 'A', protection: '', fmoc_mw: 311.3, free_mw: 71.08 },
        { token: 'G', base_code: 'G', protection: '', fmoc_mw: 297.3, free_mw: 57.05 }
      ]
    }),
    saveResidue: vi.fn().mockResolvedValue({ ok: true, data: {} }),
    generateSynthesis: vi.fn().mockResolvedValue({
      ok: true,
      data: { cycle_guide_pdf: '/tmp/output/Test_cycle_guide.pdf' }
    }),
    getLastSynthesis: vi.fn().mockResolvedValue({ ok: true, data: null })
  })
}

describe('NewSynthesis wizard', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('drives all 5 steps end-to-end to a successful generate', async () => {
    stubSpps()
    const user = userEvent.setup()
    const onDone = vi.fn()

    render(<NewSynthesis onDone={onDone} onViewCycleGuide={vi.fn()} onViewMaterials={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: /browse for fasta file/i }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled()
    )
    await user.click(screen.getByRole('button', { name: /continue/i }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled()
    )
    await user.click(screen.getByRole('button', { name: /continue/i }))

    await user.click(screen.getByRole('button', { name: /continue/i }))
    await user.click(screen.getByRole('button', { name: /continue/i }))

    await user.type(screen.getByLabelText(/synthesis name/i), 'IntegrationTest')
    await user.click(screen.getByRole('button', { name: /generate/i }))

    await waitFor(() => expect(screen.getByText(/generated successfully/i)).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /^done$/i }))
    expect(onDone).toHaveBeenCalledTimes(1)
  })
})
