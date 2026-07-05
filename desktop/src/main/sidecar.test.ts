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

  it('rejects if the sidecar process fails to spawn (invalid repo root)', async () => {
    // A nonexistent directory means child_process.spawn cannot chdir into
    // it, so Node emits an 'error' event (ENOENT) before the process ever
    // starts — this is a spawn failure, not a timeout. (A merely-empty-but-
    // real directory would NOT fail this way, since spps_assistant is
    // pip-installed and resolvable regardless of cwd — only a directory
    // that doesn't exist on disk at all triggers this path.)
    await expect(startSidecar('/nonexistent/path', 3000)).rejects.toThrow()
  }, 5000)

  it('rejects if the sidecar does not announce readiness before the timeout elapses', async () => {
    // REPO_ROOT is valid and the sidecar genuinely starts (no ENOENT) —
    // but Python interpreter startup + importing Flask always takes more
    // than 1ms, so this timeout fires before the process can print
    // anything, exercising the actual setTimeout branch in startSidecar
    // (distinct from the spawn-failure test above).
    await expect(startSidecar(REPO_ROOT, 1)).rejects.toThrow(
      'Sidecar did not announce readiness within timeout'
    )
  }, 5000)
})
