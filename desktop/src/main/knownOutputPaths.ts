/**
 * Tracks file paths the main process has itself learned about from sidecar
 * responses (synthesis generation / last-synthesis lookups). spps:openFile
 * only ever opens a path present in this set — the renderer's IPC argument
 * alone is never trusted as a filesystem sink input, since a compromised
 * renderer could otherwise ask the main process to open an arbitrary path
 * on disk.
 */
const knownOutputPaths = new Set<string>()

export function recordOutputPaths(outputPaths: unknown): void {
  if (!outputPaths || typeof outputPaths !== 'object') return
  for (const value of Object.values(outputPaths as Record<string, unknown>)) {
    if (typeof value === 'string' && value.length > 0) {
      knownOutputPaths.add(value)
    }
  }
}

export function isKnownOutputPath(path: string): boolean {
  return knownOutputPaths.has(path)
}
