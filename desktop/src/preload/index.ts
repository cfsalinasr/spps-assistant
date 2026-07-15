import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

// SPPS sidecar API — bridges the renderer to the main process's
// registerConfigHandlers and registerSynthesisHandlers IPC handlers
// (see src/main/api-bridge.ts).
const spps = {
  getConfig: () => ipcRenderer.invoke('spps:getConfig'),
  setConfig: (data: Record<string, unknown>) => ipcRenderer.invoke('spps:setConfig', data),
  pickFastaFile: () => ipcRenderer.invoke('spps:pickFastaFile'),
  pickMaterialsFile: () => ipcRenderer.invoke('spps:pickMaterialsFile'),
  pickOutputDirectory: () => ipcRenderer.invoke('spps:pickOutputDirectory'),
  openFolder: (path: string) => ipcRenderer.invoke('spps:openFolder', path),
  parseSequences: (fastaPath: string, materialsPath: string | null) =>
    ipcRenderer.invoke('spps:parseSequences', fastaPath, materialsPath),
  getResidues: () => ipcRenderer.invoke('spps:getResidues'),
  saveResidue: (residue: Record<string, unknown>) => ipcRenderer.invoke('spps:saveResidue', residue),
  generateSynthesis: (payload: Record<string, unknown>) =>
    ipcRenderer.invoke('spps:generateSynthesis', payload),
  getLastSynthesis: () => ipcRenderer.invoke('spps:getLastSynthesis')
}

// Use `contextBridge` APIs to expose Electron APIs to
// renderer only if context isolation is enabled, otherwise
// just add to the DOM global.
if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('spps', spps)
  } catch (error) {
    console.error(error)
  }
} else {
  // @ts-ignore (define in dts)
  window.electron = electronAPI
  // @ts-ignore (define in dts)
  window.spps = spps
}
