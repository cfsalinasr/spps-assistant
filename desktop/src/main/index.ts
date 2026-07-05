import { app, shell, BrowserWindow, ipcMain } from 'electron'
import { join, resolve } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'
import { startSidecar, stopSidecar, type SidecarHandle } from './sidecar'
import { registerConfigHandlers } from './api-bridge'

let sidecarHandle: SidecarHandle | null = null

function shutdownSidecar(): void {
  if (sidecarHandle) {
    stopSidecar(sidecarHandle)
    sidecarHandle = null
  }
}

function createWindow(): void {
  // Create the browser window.
  const mainWindow = new BrowserWindow({
    width: 900,
    height: 670,
    show: false,
    autoHideMenuBar: true,
    ...(process.platform === 'linux' ? { icon } : {}),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  // HMR for renderer base on electron-vite cli.
  // Load the remote URL for development or the local html file for production.
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(async () => {
  // Set app user model id for windows
  electronApp.setAppUserModelId('com.electron')

  // Default open or close DevTools by F12 in development
  // and ignore CommandOrControl + R in production.
  // see https://github.com/alex8088/electron-toolkit/tree/master/packages/utils
  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  // IPC test
  ipcMain.on('ping', () => console.log('pong'))

  // Start the Python API sidecar and wire up the config IPC handlers before
  // creating the window, so window.spps.getConfig()/setConfig() are ready
  // as soon as the renderer loads. repoRoot: npm run dev / electron-vite dev
  // runs with cwd set to desktop/, so going one directory up reaches the
  // spps-assistant repo root where pyproject.toml lives.
  const repoRoot = resolve(process.cwd(), '..')
  sidecarHandle = await startSidecar(repoRoot)
  registerConfigHandlers(ipcMain, () => {
    if (!sidecarHandle) throw new Error('Sidecar is not running')
    return sidecarHandle.info
  })

  createWindow()

  app.on('activate', function () {
    // On macOS it's common to re-create a window in the app when the
    // dock icon is clicked and there are no other windows open.
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
}).catch((error: unknown) => {
  // If the sidecar fails to start (timeout, spawn error, early exit), fail
  // loudly and quit rather than leaving an unhandled promise rejection —
  // there's no usable app without it. A friendlier error dialog can replace
  // this console message once the app is packaged for non-technical users.
  console.error('Failed to start SPPS Assistant:', error)
  app.quit()
})

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
  shutdownSidecar()
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// window-all-closed alone doesn't cover macOS quitting the app fully (e.g.
// Cmd+Q) since darwin keeps running after all windows close — this ensures
// the sidecar is always stopped when the app actually quits.
app.on('before-quit', () => {
  shutdownSidecar()
})

// In this file you can include the rest of your app's specific main process
// code. You can also put them in separate files and require them here.
