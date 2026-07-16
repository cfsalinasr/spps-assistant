import type { SidecarInfo } from './sidecar'
import { recordOutputPaths } from './knownOutputPaths'

const AUTH_HEADER = 'X-SPPS-Sidecar-Token'
const FETCH_TIMEOUT_MS = 5 * 60 * 1000 // 5 minutes

/**
 * Makes an authenticated request to the running sidecar and parses the
 * JSON response. This is the only place in the main process that ever
 * builds a URL containing the sidecar's port, or attaches its token —
 * IPC handlers call this, the renderer never does.
 *
 * Includes a generous timeout (5 minutes) to allow for long-running
 * operations like PDF/DOCX generation while still recovering from
 * hangs or sidecar crashes.
 */
export async function fetchFromSidecar(
  info: SidecarInfo,
  path: string,
  options: RequestInit = {}
): Promise<unknown> {
  const response = await fetch(`http://127.0.0.1:${info.port}${path}`, {
    ...options,
    headers: { ...options.headers, [AUTH_HEADER]: info.token },
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS)
  })
  return response.json()
}

/** Pulls output_paths out of a sidecar envelope, tolerating any shape. */
function outputPathsFrom(envelope: unknown): unknown {
  if (!envelope || typeof envelope !== 'object') return undefined
  const data = (envelope as { data?: unknown }).data
  if (!data || typeof data !== 'object') return undefined
  return (data as { output_paths?: unknown }).output_paths
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

/**
 * Registers the IPC handlers for the synthesis wizard and Cycle Guide
 * routes: window.spps.parseSequences(), .getResidues(), .saveResidue(),
 * .generateSynthesis(), .getLastSynthesis(), .setCyclePosition(). Each
 * delegates to fetchFromSidecar to reach the corresponding backend route.
 */
export function registerSynthesisHandlers(
  ipcMain: Electron.IpcMain,
  getSidecarInfo: () => SidecarInfo
): void {
  ipcMain.handle('spps:parseSequences', (_event, fastaPath: string, materialsPath: string | null) =>
    fetchFromSidecar(getSidecarInfo(), '/sequences/parse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fasta_path: fastaPath, materials_path: materialsPath })
    })
  )

  ipcMain.handle('spps:getResidues', () => fetchFromSidecar(getSidecarInfo(), '/residues'))

  ipcMain.handle('spps:saveResidue', (_event, residue: Record<string, unknown>) =>
    fetchFromSidecar(getSidecarInfo(), '/residues', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(residue)
    })
  )

  ipcMain.handle('spps:generateSynthesis', async (_event, payload: Record<string, unknown>) => {
    const envelope = await fetchFromSidecar(getSidecarInfo(), '/synthesis/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    recordOutputPaths(outputPathsFrom(envelope))
    return envelope
  })

  ipcMain.handle('spps:getLastSynthesis', async () => {
    const envelope = await fetchFromSidecar(getSidecarInfo(), '/synthesis/last')
    recordOutputPaths(outputPathsFrom(envelope))
    return envelope
  })

  ipcMain.handle('spps:setCyclePosition', (_event, cycleNumber: number) =>
    fetchFromSidecar(getSidecarInfo(), '/synthesis/cycle-position', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cycle_number: cycleNumber })
    })
  )
}
