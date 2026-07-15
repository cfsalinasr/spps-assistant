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
  pickFastaFile: () => Promise<string | null>
  pickMaterialsFile: () => Promise<string | null>
  pickOutputDirectory: () => Promise<string | null>
  openFolder: (path: string) => Promise<void>
}

declare global {
  interface Window {
    electron: ElectronAPI
    spps: SppsApi
  }
}
