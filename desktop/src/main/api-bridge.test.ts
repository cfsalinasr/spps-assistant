import { describe, expect, it } from 'vitest'
import { resolve } from 'node:path'
import { startSidecar, stopSidecar } from './sidecar'
import { fetchFromSidecar } from './api-bridge'

const REPO_ROOT = resolve(__dirname, '../../..')

describe('fetchFromSidecar', () => {
  it('fetches real config data from a running sidecar with the auth header attached', async () => {
    const handle = await startSidecar(REPO_ROOT)
    try {
      const result = (await fetchFromSidecar(handle.info, '/config')) as {
        ok: boolean
        data: Record<string, unknown>
      }
      expect(result.ok).toBe(true)
      expect(result.data.activator).toBe('HBTU')
    } finally {
      stopSidecar(handle)
    }
  }, 15000)

  it('rejects requests without a valid token by construction (wrong token fails)', async () => {
    const handle = await startSidecar(REPO_ROOT)
    try {
      const badInfo = { ...handle.info, token: 'wrong-token' }
      const result = (await fetchFromSidecar(badInfo, '/config')) as {
        ok: boolean
        error?: { code: string }
      }
      expect(result.ok).toBe(false)
      expect(result.error?.code).toBe('unauthorized')
    } finally {
      stopSidecar(handle)
    }
  }, 15000)
})
