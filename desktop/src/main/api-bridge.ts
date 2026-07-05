import type { SidecarInfo } from './sidecar'

const AUTH_HEADER = 'X-SPPS-Sidecar-Token'

/**
 * Makes an authenticated request to the running sidecar and parses the
 * JSON response. This is the only place in the main process that ever
 * builds a URL containing the sidecar's port, or attaches its token —
 * IPC handlers call this, the renderer never does.
 */
export async function fetchFromSidecar(
  info: SidecarInfo,
  path: string,
  options: RequestInit = {}
): Promise<unknown> {
  const response = await fetch(`http://127.0.0.1:${info.port}${path}`, {
    ...options,
    headers: { ...options.headers, [AUTH_HEADER]: info.token }
  })
  return response.json()
}

/**
 * Registers the IPC handlers the preload script's window.spps.getConfig()/
 * setConfig() calls invoke. getSidecarInfo is a callback (not a fixed
 * value) because the sidecar's info isn't known yet when this is called
 * during app startup wiring — by the time a handler actually runs, the
 * sidecar is guaranteed to be up.
 */
export function registerConfigHandlers(
  ipcMain: Electron.IpcMain,
  getSidecarInfo: () => SidecarInfo
): void {
  ipcMain.handle('spps:getConfig', () => fetchFromSidecar(getSidecarInfo(), '/config'))
  ipcMain.handle('spps:setConfig', (_event, data: Record<string, unknown>) =>
    fetchFromSidecar(getSidecarInfo(), '/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
  )
}
