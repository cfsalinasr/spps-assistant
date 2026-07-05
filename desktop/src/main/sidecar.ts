import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process'
import { createInterface } from 'node:readline'

export interface SidecarInfo {
  port: number
  token: string
}

export interface SidecarHandle {
  info: SidecarInfo
  process: ChildProcessWithoutNullStreams
}

const READY_LINE_PATTERN = /^SPPS_SIDECAR_READY (\d+) (\S+)$/

/**
 * Spawn the Python API sidecar (spps_assistant.api) and resolve once it
 * announces its port and auth token on stdout.
 *
 * repoRoot must be the spps-assistant Python package root (the directory
 * containing pyproject.toml) — the sidecar is run as
 * `python3.11 -m spps_assistant.api` from there. Only python3.11 is used,
 * matching every other place this project runs Python (system python3 is
 * too old for spps_assistant). In dev mode this spawns the
 * already-installed package directly; a later packaging phase will spawn
 * a frozen executable instead and this function's contract (resolves with
 * a SidecarHandle) stays the same for callers.
 */
export function startSidecar(repoRoot: string, timeoutMs = 10000): Promise<SidecarHandle> {
  return new Promise((resolvePromise, reject) => {
    const child = spawn('python3.11', ['-m', 'spps_assistant.api'], {
      cwd: repoRoot,
      env: { ...process.env, SPPS_API_PORT: '0' }
    })

    let settled = false

    const timeout = setTimeout(() => {
      if (settled) return
      settled = true
      rl.close()
      child.kill()
      reject(new Error('Sidecar did not announce readiness within timeout'))
    }, timeoutMs)

    const rl = createInterface({ input: child.stdout })
    rl.on('line', (line) => {
      if (settled) return
      const match = READY_LINE_PATTERN.exec(line)
      if (match) {
        settled = true
        clearTimeout(timeout)
        rl.close()
        resolvePromise({
          info: { port: Number(match[1]), token: match[2] },
          process: child
        })
      }
    })

    child.on('error', (err) => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      reject(err)
    })

    child.on('exit', (code) => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      reject(new Error(`Sidecar process exited with code ${code} before announcing readiness`))
    })
  })
}

/** Terminate a running sidecar process. */
export function stopSidecar(handle: SidecarHandle): void {
  handle.process.kill()
}
