import { existsSync } from 'node:fs'
import { extname } from 'node:path'
import { dialog, shell, type IpcMain } from 'electron'
import { resolveKnownOutputPath } from './knownOutputPaths'

const OPENABLE_FILE_EXTENSIONS = new Set(['.pdf', '.docx', '.xlsx'])

/**
 * Registers native file/folder picker IPC handlers used by the New Synthesis
 * wizard. These are the only place in the app that ever calls Electron's
 * dialog/shell APIs — the renderer only ever sees resolved path strings (or
 * null if the user cancels) through the typed window.spps.* preload bridge.
 */
export function registerDialogHandlers(ipcMain: IpcMain): void {
  ipcMain.handle('spps:pickFastaFile', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openFile'],
      filters: [{ name: 'FASTA', extensions: ['fasta', 'fa', 'txt'] }]
    })
    return result.canceled ? null : result.filePaths[0]
  })

  ipcMain.handle('spps:pickMaterialsFile', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openFile'],
      filters: [{ name: 'Materials', extensions: ['csv', 'xlsx'] }]
    })
    return result.canceled ? null : result.filePaths[0]
  })

  ipcMain.handle('spps:pickOutputDirectory', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openDirectory', 'createDirectory']
    })
    return result.canceled ? null : result.filePaths[0]
  })

  ipcMain.handle('spps:openFolder', (_event, folderPath: string) => {
    if (typeof folderPath !== 'string' || folderPath.length === 0) {
      console.warn('spps:openFolder received invalid path:', folderPath)
      return
    }
    shell.showItemInFolder(folderPath)
  })

  ipcMain.handle('spps:openFile', (_event, filePath: string) => {
    if (typeof filePath !== 'string' || filePath.length === 0) {
      console.warn('spps:openFile received invalid path:', filePath)
      return 'Invalid file path.'
    }
    // The renderer's argument is never trusted on its own, and its string
    // value never reaches shell.openPath directly — it must match a path
    // the main process itself already learned about from a sidecar
    // response (see knownOutputPaths.ts), and the sink is fed that trusted
    // stored value, not the caller's own argument.
    const resolvedPath = resolveKnownOutputPath(filePath)
    if (resolvedPath === undefined) {
      console.warn('spps:openFile rejected path outside the known output paths:', filePath)
      return 'File not found.'
    }
    if (!OPENABLE_FILE_EXTENSIONS.has(extname(resolvedPath).toLowerCase())) {
      console.warn('spps:openFile rejected path with disallowed extension:', resolvedPath)
      return 'Only PDF, DOCX, and XLSX files can be opened.'
    }
    if (!existsSync(resolvedPath)) {
      console.warn('spps:openFile rejected path that does not exist:', resolvedPath)
      return 'File not found.'
    }
    return shell.openPath(resolvedPath)
  })
}
