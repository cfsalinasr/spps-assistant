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

export interface DispatchRow {
  residue_3letter: string
  fmoc_mw: number
  mmol: number
  volume_ml: number
  formula_shown: string
  vessel_numbers: number[]
}

export interface GmpStep {
  label: string
  detail: string
  n_checkboxes: number
  duration: string
}

export interface VesselAssignment {
  vessel_number: number
  vessel_name: string
  residue_3letter: string | null
}

export interface SecondaryCouplingRow {
  vessel_number: number
  vessel_name: string
  residue_3letter: string
}

export interface CyclePageData {
  cycle_number: number
  total_cycles: number
  dispatch_rows: DispatchRow[]
  deprotection_steps: GmpStep[]
  coupling_steps: GmpStep[]
  vessel_assignments: VesselAssignment[]
  secondary_coupling_rows: SecondaryCouplingRow[] | null
}

export interface CycleGuideData {
  synthesis_name: string
  date_str: string
  cycles: CyclePageData[]
}

export interface CyclePositionEnvelope {
  ok: boolean
  data?: { current_cycle: number }
  error?: { code: string; message: string }
}

export interface LastSynthesisEnvelope {
  ok: boolean
  data?: {
    name: string
    output_directory: string
    generated_at: string
    vessel_count: number
    output_paths?: Record<string, string>
    current_cycle?: number
    cycle_guide?: CycleGuideData
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
  openFile: (path: string) => Promise<void>
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
  setCyclePosition: (cycleNumber: number) => Promise<CyclePositionEnvelope>
}

declare global {
  interface Window {
    electron: ElectronAPI
    spps: SppsApi
  }
}
