import { existsSync } from 'node:fs'
import { extname } from 'node:path'
import { dialog, shell, type IpcMain } from 'electron'

const OPENABLE_FILE_EXTENSIONS = new Set(['.pdf', '.docx'])

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
    if (!OPENABLE_FILE_EXTENSIONS.has(extname(filePath).toLowerCase())) {
      console.warn('spps:openFile rejected path with disallowed extension:', filePath)
      return 'Only PDF and DOCX files can be opened.'
    }
    if (!existsSync(filePath)) {
      console.warn('spps:openFile rejected path that does not exist:', filePath)
      return 'File not found.'
    }
    return shell.openPath(filePath)
  })
}
