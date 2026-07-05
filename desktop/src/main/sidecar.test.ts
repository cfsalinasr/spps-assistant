import { describe, expect, it } from 'vitest'
import { resolve } from 'node:path'
import { startSidecar, stopSidecar } from './sidecar'

const REPO_ROOT = resolve(__dirname, '../../..')

describe('startSidecar', () => {
  it('spawns the real Python sidecar and resolves with its port and token', async () => {
    const handle = await startSidecar(REPO_ROOT)
    try {
      expect(handle.info.port).toBeGreaterThan(0)
      expect(handle.info.token.length).toBeGreaterThan(0)

      const response = await fetch(`http://127.0.0.1:${handle.info.port}/health`, {
        headers: { 'X-SPPS-Sidecar-Token': handle.info.token }
      })
      expect(response.status).toBe(200)
      const body = await response.json()
      expect(body.ok).toBe(true)
      expect(body.data.status).toBe('ok')
    } finally {
      stopSidecar(handle)
    }
  }, 15000)

  it('rejects if the sidecar does not announce readiness within the timeout', async () => {
    // A nonexistent repo root means `python3.11 -m spps_assistant.api` will
    // fail to import the module and exit quickly without ever printing a
    // ready line — startSidecar must reject rather than hang.
    await expect(startSidecar('/nonexistent/path', 3000)).rejects.toThrow()
  }, 5000)
})
