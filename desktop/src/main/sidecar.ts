import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process'
import { createInterface } from 'node:readline'
import { existsSync } from 'node:fs'
import { join } from 'node:path'

// Known, fixed installation locations for python3.11 on the platforms this
// project currently targets (macOS Homebrew, common Linux/CI paths). Spawning
// by bare command name searches the inherited PATH, which is attacker-
// writable — preferring one of these fixed, unwriteable-by-a-normal-user
// paths closes that lookup window. Falls back to the bare command (searched
// via PATH) only if none of these exist, so non-standard dev installs still
// work. Only used in dev mode — a packaged build spawns the bundled, frozen
// sidecar executable by a fixed relative path instead (see startSidecar's
// `packaged` option), which has no PATH dependency at all.
const PYTHON_CANDIDATES = [
  '/opt/homebrew/bin/python3.11',
  '/usr/local/bin/python3.11',
  '/usr/bin/python3.11'
]

export function resolvePythonCommand(): string {
  return PYTHON_CANDIDATES.find((path) => existsSync(path)) ?? 'python3.11'
}

/** PyInstaller names the frozen executable with a .exe suffix on Windows. */
export function frozenSidecarExecutableName(platform: NodeJS.Platform = process.platform): string {
  return platform === 'win32' ? 'spps-sidecar.exe' : 'spps-sidecar'
}

export interface SidecarInfo {
  port: number
  token: string
}

export interface SidecarHandle {
  info: SidecarInfo
  process: ChildProcessWithoutNullStreams
}

export interface SidecarSpawnOptions {
  /** How long to wait for the readiness line before rejecting. */
  timeoutMs?: number
  /**
   * True in a packaged build (Electron's `app.isPackaged`). When true,
   * spawns the frozen sidecar executable from `resourcesPath` instead of
   * `python3.11 -m spps_assistant.api` — the packaged app has no Python
   * interpreter or the spps_assistant package installed on the host at
   * all, only the PyInstaller-frozen binary bundled into the app.
   */
  packaged?: boolean
  /** Electron's `process.resourcesPath`. Required when `packaged` is true. */
  resourcesPath?: string
}

const READY_LINE_PATTERN = /^SPPS_SIDECAR_READY (\d+) (\S+)$/

/**
 * Spawn the Python API sidecar and resolve once it announces its port and
 * auth token on stdout.
 *
 * In dev mode (default), runs `python3.11 -m spps_assistant.api` from
 * repoRoot (the spps-assistant Python package root, containing
 * pyproject.toml) — only python3.11 is used, matching every other place
 * this project runs Python (system python3 is too old for spps_assistant).
 *
 * In a packaged build (`options.packaged: true`), spawns the frozen
 * sidecar executable bundled at
 * `<resourcesPath>/sidecar/<frozenSidecarExecutableName()>` (built by
 * `packaging/build_sidecar.sh` via PyInstaller and copied in by
 * electron-builder's `extraResources` config) — no Python interpreter or
 * PATH lookup involved at all. repoRoot/resolvePythonCommand() are unused
 * in this path.
 */
export function startSidecar(
  repoRoot: string,
  options: SidecarSpawnOptions = {}
): Promise<SidecarHandle> {
  const { timeoutMs = 10000, packaged = false, resourcesPath = '' } = options
  return new Promise((resolvePromise, reject) => {
    const child = packaged
      ? spawn(join(resourcesPath, 'sidecar', frozenSidecarExecutableName()), [], {
          env: { ...process.env, SPPS_API_PORT: '0' }
        })
      : spawn(resolvePythonCommand(), ['-m', 'spps_assistant.api'], {
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
