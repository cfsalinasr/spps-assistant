import { beforeEach, describe, expect, it, vi } from 'vitest'

const showOpenDialogMock = vi.fn()
const showItemInFolderMock = vi.fn()
const openPathMock = vi.fn()
const existsSyncMock = vi.fn()
const ipcMainHandlers: Record<string, (...args: unknown[]) => unknown> = {}

vi.mock('electron', () => ({
  dialog: { showOpenDialog: (...args: unknown[]) => showOpenDialogMock(...args) },
  shell: {
    showItemInFolder: (...args: unknown[]) => showItemInFolderMock(...args),
    openPath: (...args: unknown[]) => openPathMock(...args)
  },
  ipcMain: {
    handle: (channel: string, handler: (...args: unknown[]) => unknown) => {
      ipcMainHandlers[channel] = handler
    }
  }
}))

vi.mock('node:fs', () => ({
  existsSync: (...args: unknown[]) => existsSyncMock(...args)
}))

import { ipcMain } from 'electron'
import { registerDialogHandlers } from './dialogs'

describe('registerDialogHandlers', () => {
  beforeEach(() => {
    showOpenDialogMock.mockReset()
    showItemInFolderMock.mockReset()
    openPathMock.mockReset()
    existsSyncMock.mockReset()
    existsSyncMock.mockReturnValue(true)
    for (const key of Object.keys(ipcMainHandlers)) delete ipcMainHandlers[key]
    registerDialogHandlers(ipcMain)
  })

  it('spps:pickFastaFile returns the chosen path', async () => {
    showOpenDialogMock.mockResolvedValue({ canceled: false, filePaths: ['/tmp/seqs.fasta'] })
    const result = await ipcMainHandlers['spps:pickFastaFile']()
    expect(result).toBe('/tmp/seqs.fasta')
    expect(showOpenDialogMock).toHaveBeenCalledWith(
      expect.objectContaining({ filters: [{ name: 'FASTA', extensions: ['fasta', 'fa', 'txt'] }] })
    )
  })

  it('spps:pickFastaFile returns null when the user cancels', async () => {
    showOpenDialogMock.mockResolvedValue({ canceled: true, filePaths: [] })
    const result = await ipcMainHandlers['spps:pickFastaFile']()
    expect(result).toBeNull()
  })

  it('spps:pickMaterialsFile returns the chosen path', async () => {
    showOpenDialogMock.mockResolvedValue({ canceled: false, filePaths: ['/tmp/mats.csv'] })
    const result = await ipcMainHandlers['spps:pickMaterialsFile']()
    expect(result).toBe('/tmp/mats.csv')
  })

  it('spps:pickOutputDirectory returns the chosen directory', async () => {
    showOpenDialogMock.mockResolvedValue({ canceled: false, filePaths: ['/tmp/out'] })
    const result = await ipcMainHandlers['spps:pickOutputDirectory']()
    expect(result).toBe('/tmp/out')
    expect(showOpenDialogMock).toHaveBeenCalledWith(
      expect.objectContaining({ properties: ['openDirectory', 'createDirectory'] })
    )
  })

  it('spps:openFolder calls shell.showItemInFolder with the given path', () => {
    ipcMainHandlers['spps:openFolder'](null, '/tmp/out/file.pdf')
    expect(showItemInFolderMock).toHaveBeenCalledWith('/tmp/out/file.pdf')
  })

  it('spps:openFolder does not call shell.showItemInFolder with a non-string argument', () => {
    ipcMainHandlers['spps:openFolder'](null, 123)
    expect(showItemInFolderMock).not.toHaveBeenCalled()
  })

  it('spps:openFolder does not call shell.showItemInFolder with an empty string', () => {
    ipcMainHandlers['spps:openFolder'](null, '')
    expect(showItemInFolderMock).not.toHaveBeenCalled()
  })

  it('spps:openFile calls shell.openPath with the given path', async () => {
    openPathMock.mockResolvedValue('')
    await ipcMainHandlers['spps:openFile'](null, '/tmp/out/guide.pdf')
    expect(openPathMock).toHaveBeenCalledWith('/tmp/out/guide.pdf')
  })

  it('spps:openFile does not call shell.openPath with a non-string argument', async () => {
    await ipcMainHandlers['spps:openFile'](null, 123)
    expect(openPathMock).not.toHaveBeenCalled()
  })

  it('spps:openFile does not call shell.openPath with an empty string', async () => {
    await ipcMainHandlers['spps:openFile'](null, '')
    expect(openPathMock).not.toHaveBeenCalled()
  })

  it('spps:openFile rejects a path that does not end in .pdf or .docx', async () => {
    existsSyncMock.mockReturnValue(true)
    const result = await ipcMainHandlers['spps:openFile'](null, '/tmp/out/guide.txt')
    expect(result).toBe('')
    expect(openPathMock).not.toHaveBeenCalled()
  })

  it('spps:openFile rejects a .pdf path that does not exist on disk', async () => {
    existsSyncMock.mockReturnValue(false)
    const result = await ipcMainHandlers['spps:openFile'](null, '/tmp/out/missing.pdf')
    expect(result).toBe('')
    expect(openPathMock).not.toHaveBeenCalled()
  })
})
