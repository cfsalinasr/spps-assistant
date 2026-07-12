import { resolve } from 'node:path'
import { defineConfig } from 'electron-vite'
import react from '@vitejs/plugin-react'
import type { Plugin } from 'vite'

// The dev server injects CSS via runtime <style> tags for HMR, which needs
// style-src 'unsafe-inline'. The production build extracts CSS to a static
// .css file loaded via <link>, so the built app never needs it — strip it
// there for a stricter shipped CSP. ctx.server is only set during `vite dev`.
function stripUnsafeInlineInProduction(): Plugin {
  return {
    name: 'strip-unsafe-inline-style-src-in-production',
    transformIndexHtml(html, ctx) {
      if (ctx.server) return html
      return html.replace(
        " 'unsafe-inline' https://fonts.googleapis.com",
        ' https://fonts.googleapis.com'
      )
    }
  }
}

export default defineConfig({
  main: {},
  preload: {},
  renderer: {
    resolve: {
      alias: {
        '@renderer': resolve('src/renderer/src')
      }
    },
    plugins: [react(), stripUnsafeInlineInProduction()]
  }
})
