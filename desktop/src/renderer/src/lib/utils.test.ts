import { describe, expect, it } from 'vitest'
import { cn } from './utils'

describe('cn', () => {
  it('joins plain class name strings', () => {
    expect(cn('a', 'b')).toBe('a b')
  })

  it('drops falsy values', () => {
    const hidden = false
    expect(cn('a', hidden && 'b', undefined, null, 'c')).toBe('a c')
  })

  it('merges conflicting Tailwind utility classes, keeping the last one', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4')
  })
})
