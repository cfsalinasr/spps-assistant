import { beforeEach, describe, expect, it, vi } from 'vitest'

const fetchMock = vi.fn()
const ipcMainHandlers: Record<string, (...args: unknown[]) => unknown> = {}
const ipcMain = {
  handle: (channel: string, handler: (...args: unknown[]) => unknown) => {
    ipcMainHandlers[channel] = handler
  }
} as unknown as Electron.IpcMain

vi.stubGlobal('fetch', fetchMock)

import { registerSynthesisHandlers } from './api-bridge'
import { isKnownOutputPath } from './knownOutputPaths'

function jsonResponse(body: unknown): Response {
  return { json: () => Promise.resolve(body) } as Response
}

describe('registerSynthesisHandlers records sidecar-reported output paths', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    for (const key of Object.keys(ipcMainHandlers)) delete ipcMainHandlers[key]
    registerSynthesisHandlers(ipcMain, () => ({ port: 1234, token: 'test-token' }))
  })

  it('spps:generateSynthesis records every output path from a successful envelope', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        ok: true,
        data: {
          output_paths: {
            cycle_guide_pdf: '/tmp/out/gen-a.pdf',
            cycle_guide_docx: '/tmp/out/gen-a.docx'
          }
        }
      })
    )
    await ipcMainHandlers['spps:generateSynthesis'](null, {})
    expect(isKnownOutputPath('/tmp/out/gen-a.pdf')).toBe(true)
    expect(isKnownOutputPath('/tmp/out/gen-a.docx')).toBe(true)
  })

  it('spps:getLastSynthesis records output paths from its envelope', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ ok: true, data: { output_paths: { cycle_guide_pdf: '/tmp/out/last-b.pdf' } } })
    )
    await ipcMainHandlers['spps:getLastSynthesis']()
    expect(isKnownOutputPath('/tmp/out/last-b.pdf')).toBe(true)
  })

  it('spps:getLastSynthesis with a null data payload (no prior synthesis) does not throw', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true, data: null }))
    await expect(ipcMainHandlers['spps:getLastSynthesis']()).resolves.toBeDefined()
  })

  it('an unrelated path is still not known after recording an unrelated envelope', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ ok: true, data: { output_paths: { cycle_guide_pdf: '/tmp/out/gen-c.pdf' } } })
    )
    await ipcMainHandlers['spps:generateSynthesis'](null, {})
    expect(isKnownOutputPath('/tmp/out/never-seen.pdf')).toBe(false)
  })
})
