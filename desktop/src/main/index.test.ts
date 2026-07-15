import { beforeEach, describe, expect, it, vi } from 'vitest'

const startSidecarMock = vi.fn()
const stopSidecarMock = vi.fn()
const registerConfigHandlersMock = vi.fn()
const registerSynthesisHandlersMock = vi.fn()

vi.mock('./sidecar', () => ({
  startSidecar: (...args: unknown[]) => startSidecarMock(...args),
  stopSidecar: (...args: unknown[]) => stopSidecarMock(...args)
}))
vi.mock('./api-bridge', () => ({
  registerConfigHandlers: (...args: unknown[]) => registerConfigHandlersMock(...args),
  registerSynthesisHandlers: (...args: unknown[]) => registerSynthesisHandlersMock(...args)
}))
vi.mock('../../resources/icon.png?asset', () => ({ default: 'icon.png' }))
const isMock = { dev: false }
vi.mock('@electron-toolkit/utils', () => ({
  electronApp: { setAppUserModelId: vi.fn() },
  optimizer: { watchWindowShortcuts: vi.fn() },
  is: isMock
}))

interface MockApp {
  whenReady: () => Promise<void>
  on: (event: string, handler: (...args: unknown[]) => void) => void
  quit: () => void
  emit: (event: string, ...args: unknown[]) => void
  quitCalls: number
}

let mockApp: MockApp
let whenReadyResult: Promise<void>

function createMockApp(): MockApp {
  const listeners: Record<string, Array<(...args: unknown[]) => void>> = {}
  const self: MockApp = {
    whenReady: () => whenReadyResult,
    on: vi.fn((event: string, handler: (...args: unknown[]) => void) => {
      ;(listeners[event] ??= []).push(handler)
    }),
    quit: vi.fn(() => {
      self.quitCalls += 1
    }),
    emit: (event: string, ...args: unknown[]) => {
      for (const handler of listeners[event] ?? []) handler(...args)
    },
    quitCalls: 0
  }
  return self
}

interface MockWindow {
  on: (event: string, handler: (...args: unknown[]) => void) => void
  webContents: { setWindowOpenHandler: (handler: (details: { url: string }) => unknown) => void }
  loadURL: (url: string) => void
  loadFile: (path: string) => void
  show: () => void
  _readyToShow?: () => void
  _windowOpenHandler?: (details: { url: string }) => unknown
}

let mockWindows: MockWindow[]
const shellMock = { openExternal: vi.fn() }
const ipcMainMock = { on: vi.fn(), handle: vi.fn() }

vi.mock('electron', () => ({
  get app() {
    return mockApp
  },
  BrowserWindow: Object.assign(
    vi.fn().mockImplementation(function (this: MockWindow) {
      this.show = vi.fn()
      this.on = vi.fn((event: string, handler: () => void) => {
        if (event === 'ready-to-show') this._readyToShow = handler
      })
      this.webContents = {
        setWindowOpenHandler: vi.fn((handler: (details: { url: string }) => unknown) => {
          this._windowOpenHandler = handler
        })
      }
      this.loadURL = vi.fn()
      this.loadFile = vi.fn()
      mockWindows.push(this)
    }),
    { getAllWindows: vi.fn(() => []) }
  ),
  get shell() {
    return shellMock
  },
  get ipcMain() {
    return ipcMainMock
  }
}))

async function flushMicrotasks(): Promise<void> {
  for (let i = 0; i < 5; i++) {
    await Promise.resolve()
  }
}

describe('main/index bootstrap', () => {
  beforeEach(() => {
    vi.resetModules()
    startSidecarMock.mockReset()
    stopSidecarMock.mockReset()
    registerConfigHandlersMock.mockReset()
    registerSynthesisHandlersMock.mockReset()
    shellMock.openExternal.mockReset()
    ipcMainMock.on.mockReset()
    ipcMainMock.handle.mockReset()
    isMock.dev = false
    mockApp = createMockApp()
    mockWindows = []
  })

  it('starts the sidecar with the repo root and wires up config IPC handlers before creating a window', async () => {
    startSidecarMock.mockResolvedValue({ info: { port: 4321, token: 'tok' } })
    whenReadyResult = Promise.resolve()

    await import('./index')
    await flushMicrotasks()

    expect(startSidecarMock).toHaveBeenCalledTimes(1)
    expect(typeof startSidecarMock.mock.calls[0][0]).toBe('string')
    expect(registerConfigHandlersMock).toHaveBeenCalledTimes(1)

    const getSidecarInfo = registerConfigHandlersMock.mock.calls[0][1] as () => unknown
    expect(getSidecarInfo()).toEqual({ port: 4321, token: 'tok' })
  })

  it('quits the app if the sidecar fails to start instead of leaving an unhandled rejection', async () => {
    startSidecarMock.mockRejectedValue(new Error('sidecar spawn failed'))
    whenReadyResult = Promise.resolve()

    await import('./index')
    await flushMicrotasks()

    expect(mockApp.quitCalls).toBe(1)
  })

  it('stops the sidecar when all windows close', async () => {
    startSidecarMock.mockResolvedValue({ info: { port: 1, token: 't' } })
    whenReadyResult = Promise.resolve()

    await import('./index')
    await flushMicrotasks()

    mockApp.emit('window-all-closed')
    expect(stopSidecarMock).toHaveBeenCalledTimes(1)
  })

  it('stops the sidecar on before-quit (covers macOS, where window-all-closed alone does not fire)', async () => {
    startSidecarMock.mockResolvedValue({ info: { port: 1, token: 't' } })
    whenReadyResult = Promise.resolve()

    await import('./index')
    await flushMicrotasks()

    mockApp.emit('before-quit')
    expect(stopSidecarMock).toHaveBeenCalledTimes(1)
  })

  it('quits on window-all-closed for non-macOS platforms, but not for darwin', async () => {
    startSidecarMock.mockResolvedValue({ info: { port: 1, token: 't' } })
    whenReadyResult = Promise.resolve()
    const originalPlatform = process.platform

    await import('./index')
    await flushMicrotasks()

    Object.defineProperty(process, 'platform', { value: 'win32' })
    mockApp.emit('window-all-closed')
    expect(mockApp.quitCalls).toBe(1)

    Object.defineProperty(process, 'platform', { value: originalPlatform })
  })

  it('does not quit on window-all-closed for darwin', async () => {
    startSidecarMock.mockResolvedValue({ info: { port: 1, token: 't' } })
    whenReadyResult = Promise.resolve()
    const originalPlatform = process.platform

    await import('./index')
    await flushMicrotasks()

    Object.defineProperty(process, 'platform', { value: 'darwin' })
    mockApp.emit('window-all-closed')
    expect(mockApp.quitCalls).toBe(0)

    Object.defineProperty(process, 'platform', { value: originalPlatform })
  })

  it('shows the window once ready and denies+forwards external link opens to the shell', async () => {
    startSidecarMock.mockResolvedValue({ info: { port: 1, token: 't' } })
    whenReadyResult = Promise.resolve()

    await import('./index')
    await flushMicrotasks()

    const [win] = mockWindows
    win._readyToShow?.()
    expect(win.show).toHaveBeenCalledTimes(1)

    const result = win._windowOpenHandler?.({ url: 'https://example.com' })
    expect(shellMock.openExternal).toHaveBeenCalledWith('https://example.com')
    expect(result).toEqual({ action: 'deny' })
  })

  it('loads the dev server URL when running under electron-vite dev, otherwise the built file', async () => {
    startSidecarMock.mockResolvedValue({ info: { port: 1, token: 't' } })
    whenReadyResult = Promise.resolve()
    isMock.dev = true
    vi.stubEnv('ELECTRON_RENDERER_URL', 'http://localhost:5173')

    await import('./index')
    await flushMicrotasks()

    expect(mockWindows[0].loadURL).toHaveBeenCalledWith('http://localhost:5173')
    expect(mockWindows[0].loadFile).not.toHaveBeenCalled()

    vi.unstubAllEnvs()
  })

  it('logs "pong" in response to the ping IPC test channel', async () => {
    startSidecarMock.mockResolvedValue({ info: { port: 1, token: 't' } })
    whenReadyResult = Promise.resolve()
    const consoleLog = vi.spyOn(console, 'log').mockImplementation(() => {})

    await import('./index')
    await flushMicrotasks()

    const pingHandler = ipcMainMock.on.mock.calls.find(
      ([event]) => event === 'ping'
    )?.[1] as () => void
    pingHandler()
    expect(consoleLog).toHaveBeenCalledWith('pong')

    consoleLog.mockRestore()
  })

  it('creates a new window on activate if none are open', async () => {
    startSidecarMock.mockResolvedValue({ info: { port: 1, token: 't' } })
    whenReadyResult = Promise.resolve()

    await import('./index')
    await flushMicrotasks()

    expect(mockWindows).toHaveLength(1)
    mockApp.emit('activate')
    expect(mockWindows).toHaveLength(2)
  })
})
