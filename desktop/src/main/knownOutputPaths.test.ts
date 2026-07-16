import { describe, expect, it } from 'vitest'
import { isKnownOutputPath, recordOutputPaths, resolveKnownOutputPath } from './knownOutputPaths'

describe('knownOutputPaths', () => {
  it('a path is unknown before it has ever been recorded', () => {
    expect(isKnownOutputPath('/tmp/never-recorded.pdf')).toBe(false)
  })

  it('recordOutputPaths adds every string value from the given object', () => {
    recordOutputPaths({
      cycle_guide_pdf: '/tmp/out/known1.pdf',
      cycle_guide_docx: '/tmp/out/known1.docx'
    })
    expect(isKnownOutputPath('/tmp/out/known1.pdf')).toBe(true)
    expect(isKnownOutputPath('/tmp/out/known1.docx')).toBe(true)
  })

  it('ignores non-string values without throwing', () => {
    expect(() =>
      recordOutputPaths({ a: 123, b: null, c: undefined, d: { nested: true } })
    ).not.toThrow()
  })

  it('ignores an empty string value', () => {
    recordOutputPaths({ empty: '' })
    expect(isKnownOutputPath('')).toBe(false)
  })

  it('tolerates null, undefined, and non-object input', () => {
    expect(() => recordOutputPaths(null)).not.toThrow()
    expect(() => recordOutputPaths(undefined)).not.toThrow()
    expect(() => recordOutputPaths('not-an-object')).not.toThrow()
    expect(() => recordOutputPaths(42)).not.toThrow()
  })

  it('a path recorded for one key is not confused with an unrelated path', () => {
    recordOutputPaths({ some_path: '/tmp/out/known2.pdf' })
    expect(isKnownOutputPath('/tmp/out/unrelated.pdf')).toBe(false)
  })

  it('resolveKnownOutputPath returns undefined for a path that was never recorded', () => {
    expect(resolveKnownOutputPath('/tmp/never-recorded-2.pdf')).toBeUndefined()
  })

  it('resolveKnownOutputPath returns the matching stored value for a recorded path', () => {
    recordOutputPaths({ cycle_guide_pdf: '/tmp/out/known3.pdf' })
    expect(resolveKnownOutputPath('/tmp/out/known3.pdf')).toBe('/tmp/out/known3.pdf')
  })
})
