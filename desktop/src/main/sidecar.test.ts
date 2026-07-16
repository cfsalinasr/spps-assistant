import { describe, expect, it, vi } from 'vitest'
import { resolve } from 'node:path'
import { EventEmitter } from 'node:events'
import { Readable } from 'node:stream'
import {
  startSidecar,
  stopSidecar,
  resolvePythonCommand,
  frozenSidecarExecutableName
} from './sidecar'

const REPO_ROOT = resolve(__dirname, '../../..')

describe('resolvePythonCommand', () => {
  it('returns a fixed absolute path when one of the known candidates exists', async () => {
    vi.resetModules()
    vi.doMock('node:fs', () => ({
      existsSync: (path: string) => path === '/usr/local/bin/python3.11'
    }))
    const { resolvePythonCommand: resolveWithMock } = await import('./sidecar')
    expect(resolveWithMock()).toBe('/usr/local/bin/python3.11')
    vi.doUnmock('node:fs')
  })

  it('falls back to the bare command name when no fixed candidate exists', async () => {
    vi.resetModules()
    vi.doMock('node:fs', () => ({ existsSync: () => false }))
    const { resolvePythonCommand: resolveWithMock } = await import('./sidecar')
    expect(resolveWithMock()).toBe('python3.11')
    vi.doUnmock('node:fs')
  })

  it('returns some usable python3.11 command on this real machine', () => {
    expect(resolvePythonCommand().length).toBeGreaterThan(0)
  })
})

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
    await expect(startSidecar('/nonexistent/path', { timeoutMs: 3000 })).rejects.toThrow()
  }, 5000)

  it('rejects if the sidecar does not announce readiness before the timeout elapses', async () => {
    // REPO_ROOT is valid and the sidecar genuinely starts (no ENOENT) —
    // but Python interpreter startup + importing Flask always takes more
    // than 1ms, so this timeout fires before the process can print
    // anything, exercising the actual setTimeout branch in startSidecar
    // (distinct from the spawn-failure test above).
    await expect(startSidecar(REPO_ROOT, { timeoutMs: 1 })).rejects.toThrow(
      'Sidecar did not announce readiness within timeout'
    )
  }, 5000)

  it('spawns the frozen sidecar executable by resourcesPath when packaged is true', async () => {
    vi.resetModules()
    const spawnMock = vi.fn(() => {
      const fake = new EventEmitter() as EventEmitter & { stdout: Readable; kill: () => void }
      fake.stdout = new Readable({ read: () => {} })
      fake.kill = vi.fn()
      return fake
    })
    vi.doMock('node:child_process', () => ({ spawn: spawnMock }))
    const { startSidecar: startSidecarWithMock } = await import('./sidecar')

    // The mocked child never emits a ready line, so this rejects on the
    // timeout — a short one, so the test doesn't linger. We only care
    // about the spawn() call args, captured synchronously before that.
    const pending = startSidecarWithMock('/unused/repo/root', {
      timeoutMs: 5,
      packaged: true,
      resourcesPath: '/Applications/SPPS Assistant.app/Contents/Resources'
    })

    expect(spawnMock).toHaveBeenCalledWith(
      `/Applications/SPPS Assistant.app/Contents/Resources/sidecar/${frozenSidecarExecutableName()}`,
      [],
      expect.objectContaining({ env: expect.any(Object) })
    )

    await expect(pending).rejects.toThrow('Sidecar did not announce readiness within timeout')
    vi.doUnmock('node:child_process')
  })
})

describe('frozenSidecarExecutableName', () => {
  it('appends .exe on Windows', () => {
    expect(frozenSidecarExecutableName('win32')).toBe('spps-sidecar.exe')
  })

  it('has no extension on macOS', () => {
    expect(frozenSidecarExecutableName('darwin')).toBe('spps-sidecar')
  })

  it('has no extension on Linux', () => {
    expect(frozenSidecarExecutableName('linux')).toBe('spps-sidecar')
  })
})
