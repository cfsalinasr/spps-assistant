import { ElectronAPI } from '@electron-toolkit/preload'

export interface SppsConfig {
  [key: string]: unknown
}

export interface SppsEnvelope {
  ok: boolean
  data?: SppsConfig
  error?: { code: string; message: string }
}

export interface ParsedVessel {
  number: number
  name: string
  original_tokens: string[]
  reversed_tokens: string[]
  resin_mass_g: number
  substitution_mmol_g: number
}

export interface ResidueRecord {
  token: string
  base_code: string
  protection: string
  fmoc_mw: number
  free_mw: number
}

export interface ParseSequencesEnvelope {
  ok: boolean
  data?: { vessels: ParsedVessel[]; materials_residue_map?: Record<string, ResidueRecord> }
  error?: { code: string; message: string }
}

export interface ResiduesEnvelope {
  ok: boolean
  data?: ResidueRecord[]
  error?: { code: string; message: string }
}

export interface GenerateEnvelope {
  ok: boolean
  data?: Record<string, string>
  error?: { code: string; message: string }
}

export interface LastSynthesisEnvelope {
  ok: boolean
  data?: {
    name: string
    output_directory: string
    generated_at: string
    vessel_count: number
  } | null
  error?: { code: string; message: string }
}

export interface SppsApi {
  getConfig: () => Promise<SppsEnvelope>
  setConfig: (data: Record<string, unknown>) => Promise<SppsEnvelope>
  pickFastaFile: () => Promise<string | null>
  pickMaterialsFile: () => Promise<string | null>
  pickOutputDirectory: () => Promise<string | null>
  openFolder: (path: string) => Promise<void>
  parseSequences: (
    fastaPath: string,
    materialsPath: string | null
  ) => Promise<ParseSequencesEnvelope>
  getResidues: () => Promise<ResiduesEnvelope>
  saveResidue: (residue: ResidueRecord) => Promise<SppsEnvelope>
  generateSynthesis: (payload: {
    vessels: ParsedVessel[]
    residue_info_map: Record<string, ResidueRecord>
    config_overrides: Record<string, unknown>
  }) => Promise<GenerateEnvelope>
  getLastSynthesis: () => Promise<LastSynthesisEnvelope>
}

declare global {
  interface Window {
    electron: ElectronAPI
    spps: SppsApi
  }
}
