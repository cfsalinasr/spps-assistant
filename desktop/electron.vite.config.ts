import { randomBytes } from 'node:crypto'
import { resolve } from 'node:path'
import { defineConfig } from 'electron-vite'
import react from '@vitejs/plugin-react'
import type { Plugin } from 'vite'

// A fixed placeholder baked into the checked-in src/renderer/index.html's CSP
// (as 'nonce-__CSP_NONCE__') and into Vite's html.cspNonce option below. Vite
// bakes this same string into every <style>/<script>/<link> tag it emits —
// including ones injected by other plugins (e.g. @vitejs/plugin-react's Fast
// Refresh preamble) *after* all transformIndexHtml hooks have already run —
// so no transformIndexHtml hook can reliably see every occurrence. Only a
// raw HTTP response-body rewrite, after Vite has fully finished producing
// the page, can catch every one; see strictStyleCspForDev below.
const CSP_NONCE_PLACEHOLDER = '__CSP_NONCE__'

// The production build extracts CSS to a static .css file loaded via <link>
// and never inlines scripts or styles, so it never needs a nonce at all —
// strip the placeholder from the shipped HTML entirely (leaving html.cspNonce
// unset for prod, see below, so Vite never bakes it into any tag either).
function strictStyleCspForBuild(): Plugin {
  return {
    name: 'strict-style-csp-build',
    apply: 'build',
    transformIndexHtml(html) {
      return html.replace(" 'nonce-__CSP_NONCE__'", '')
    }
  }
}

// The dev server's own CSS-HMR client creates real inline <style> elements
// at runtime (see vite/dist/client/client.mjs), which needs a real nonce
// instead of 'unsafe-inline'. Vite's html.cspNonce mechanism only supports a
// single static config-time string — per its own type docs, the caller's
// server is responsible for substituting it with a real per-request random
// value. That substitution has to happen on the raw outgoing response body
// (not via transformIndexHtml), since Vite injects additional nonce="..."
// attributes on dynamically-added tags (Fast Refresh preamble, /@vite/client)
// after every transformIndexHtml hook — including 'post' ones — has already
// run.
function strictStyleCspForDev(): Plugin {
  return {
    name: 'strict-style-csp-dev',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((_req, res, next) => {
        const nonce = randomBytes(16).toString('base64')
        const originalEnd = res.end.bind(res)
        let buffered = ''

        res.write = ((chunk: unknown) => {
          buffered += typeof chunk === 'string' ? chunk : (chunk as Buffer)?.toString('utf8')
          return true
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
        }) as any

        res.end = ((chunk?: unknown, ...rest: unknown[]) => {
          if (chunk)
            buffered += typeof chunk === 'string' ? chunk : (chunk as Buffer)?.toString('utf8')

          const contentType = res.getHeader('content-type')
          const isHtml = typeof contentType === 'string' && contentType.includes('text/html')
          if (!isHtml || !buffered.includes(CSP_NONCE_PLACEHOLDER)) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            return originalEnd(buffered, ...(rest as any))
          }

          const finalHtml = buffered.replaceAll(CSP_NONCE_PLACEHOLDER, nonce)
          res.removeHeader('content-length')
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          return originalEnd(finalHtml, ...(rest as any))
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
        }) as any

        next()
      })
    }
  }
}

export default defineConfig(({ command }) => ({
  main: {},
  preload: {},
  renderer: {
    resolve: {
      alias: {
        '@renderer': resolve('src/renderer/src')
      }
    },
    html: command === 'serve' ? { cspNonce: CSP_NONCE_PLACEHOLDER } : undefined,
    plugins: [react(), strictStyleCspForBuild(), strictStyleCspForDev()]
  }
}))
