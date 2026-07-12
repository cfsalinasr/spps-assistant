// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { SppsApi } from './index.d'

function setContextIsolated(value: boolean): void {
  Object.defineProperty(process, 'contextIsolated', { value, configurable: true })
}

function getSppsFromWindow(): SppsApi {
  return (window as unknown as { spps: SppsApi }).spps
}

describe('preload', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  afterEach(() => {
    delete (process as unknown as Record<string, unknown>).contextIsolated
  })

  it('exposes electron/spps via contextBridge when context isolation is enabled', async () => {
    const exposeInMainWorld = vi.fn()
    vi.doMock('electron', () => ({
      contextBridge: { exposeInMainWorld },
      ipcRenderer: { invoke: vi.fn() }
    }))
    vi.doMock('@electron-toolkit/preload', () => ({ electronAPI: { marker: true } }))
    setContextIsolated(true)

    await import('./index')

    expect(exposeInMainWorld).toHaveBeenCalledWith('electron', { marker: true })
    expect(exposeInMainWorld).toHaveBeenCalledWith(
      'spps',
      expect.objectContaining({ getConfig: expect.any(Function), setConfig: expect.any(Function) })
    )
    expect(exposeInMainWorld).not.toHaveBeenCalledWith('api', expect.anything())
  })

  it('falls back to assigning window globals when context isolation is disabled', async () => {
    vi.doMock('electron', () => ({
      contextBridge: { exposeInMainWorld: vi.fn() },
      ipcRenderer: { invoke: vi.fn() }
    }))
    vi.doMock('@electron-toolkit/preload', () => ({ electronAPI: {} }))
    setContextIsolated(false)

    await import('./index')

    expect(typeof getSppsFromWindow().getConfig).toBe('function')
    expect(typeof getSppsFromWindow().setConfig).toBe('function')
  })

  it('spps.getConfig/setConfig delegate to ipcRenderer.invoke with the right channel and args', async () => {
    const invoke = vi.fn()
    vi.doMock('electron', () => ({
      contextBridge: { exposeInMainWorld: vi.fn() },
      ipcRenderer: { invoke }
    }))
    vi.doMock('@electron-toolkit/preload', () => ({ electronAPI: {} }))
    setContextIsolated(false)

    await import('./index')

    getSppsFromWindow().getConfig()
    expect(invoke).toHaveBeenCalledWith('spps:getConfig')

    getSppsFromWindow().setConfig({ activator: 'HBTU' })
    expect(invoke).toHaveBeenCalledWith('spps:setConfig', { activator: 'HBTU' })
  })
})
