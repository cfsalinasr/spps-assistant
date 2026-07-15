import { dialog, shell, type IpcMain } from 'electron'

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
    shell.showItemInFolder(folderPath)
  })
}
