import { ElectronAPI } from '@electron-toolkit/preload'

export interface SppsConfig {
  [key: string]: unknown
}

export interface SppsEnvelope {
  ok: boolean
  data?: SppsConfig
  error?: { code: string; message: string }
}

export interface SppsApi {
  getConfig: () => Promise<SppsEnvelope>
  setConfig: (data: Record<string, unknown>) => Promise<SppsEnvelope>
}

declare global {
  interface Window {
    electron: ElectronAPI
    api: unknown
    spps: SppsApi
  }
}
