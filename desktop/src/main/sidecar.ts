import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process'
import { createInterface } from 'node:readline'
import { existsSync } from 'node:fs'

// Known, fixed installation locations for python3.11 on the platforms this
// project currently targets (macOS Homebrew, common Linux/CI paths). Spawning
// by bare command name searches the inherited PATH, which is attacker-
// writable — preferring one of these fixed, unwriteable-by-a-normal-user
// paths closes that lookup window. Falls back to the bare command (searched
// via PATH) only if none of these exist, so non-standard dev installs still
// work. A later packaging phase will spawn a bundled, frozen executable by a
// fixed relative path instead, removing this PATH dependency entirely.
const PYTHON_CANDIDATES = [
  '/opt/homebrew/bin/python3.11',
  '/usr/local/bin/python3.11',
  '/usr/bin/python3.11'
]

export function resolvePythonCommand(): string {
  return PYTHON_CANDIDATES.find((path) => existsSync(path)) ?? 'python3.11'
}

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
    const child = spawn(resolvePythonCommand(), ['-m', 'spps_assistant.api'], {
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
