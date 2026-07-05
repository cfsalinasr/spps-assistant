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
      // Asserting structure, not an exact value: this test spawns the real
      // sidecar, which reads the real ~/.spps_assistant/spps_config.yaml on
      // whatever machine runs it — a value like 'activator' could genuinely
      // differ between machines/dev histories. What this test needs to prove
      // is that the real HTTP round-trip (with the auth header) actually
      // works end-to-end, which a structural check does just as well as an
      // exact-value check, without being coupled to ambient filesystem state.
      expect(result.ok).toBe(true)
      expect(typeof result.data.activator).toBe('string')
      expect((result.data.activator as string).length).toBeGreaterThan(0)
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
