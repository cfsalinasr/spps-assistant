// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import PeptideInfo from './PeptideInfo'

describe('PeptideInfo', () => {
  it('renders a "coming in a future release" status message', () => {
    render(<PeptideInfo />)
    expect(screen.getByText('Peptide information')).toBeInTheDocument()
    expect(screen.getByText('Coming in a future release.')).toBeInTheDocument()
  })
})
