import { resolve } from 'path'
import { defineConfig } from 'vitest/config'

// electron-vite's own config (electron.vite.config.ts) exports a
// { main, preload, renderer } shape that vitest doesn't understand directly,
// so renderer-side tests need their own minimal vite config here — in
// particular the `@renderer` alias used throughout src/renderer/src.
export default defineConfig({
  resolve: {
    alias: {
      '@renderer': resolve(__dirname, 'src/renderer/src')
    }
  },
  test: {
    // @testing-library/react's automatic cleanup between tests only
    // registers itself against a *global* afterEach (jest-compatible
    // behavior), which vitest only provides when `globals: true`.
    // Without this, DOM from one test's render() leaks into the next.
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      reportsDirectory: './coverage'
    }
  }
})
