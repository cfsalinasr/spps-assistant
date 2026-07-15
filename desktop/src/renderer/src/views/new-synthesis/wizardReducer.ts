export interface ParsedVessel {
  number: number
  name: string
  original_tokens: string[]
  reversed_tokens: string[]
  resin_mass_g: number
  substitution_mmol_g: number
}

export interface ResidueMwEntry {
  token: string
  base_code: string
  protection: string
  fmoc_mw: number
  free_mw: number
  origin: 'db' | 'materials' | 'manual'
}

export interface ReagentsState {
  deprotectionReagent: string
  activator: string
  useOxyma: boolean
  base: string
  volumeMode: 'stoichiometry' | 'legacy'
  completenessTest: 'bromophenol' | 'kaiser' | 'none'
}

export interface ResinState {
  strategy: 'fixed' | 'target'
  substitutionMmolG: number
  fixedResinMassG: number
  targetYieldMg: number | null
}

export interface GenerateResult {
  status: 'idle' | 'generating' | 'success' | 'error'
  paths?: Record<string, string>
  error?: string
}

export interface WizardState {
  step: 1 | 2 | 3 | 4 | 5
  synthesisName: string
  fastaPath: string | null
  materialsPath: string | null
  vessels: ParsedVessel[]
  residueMap: Record<string, ResidueMwEntry>
  reagents: ReagentsState
  resin: ResinState
  outputDirectory: string
  generateResult: GenerateResult
}

export const initialWizardState: WizardState = {
  step: 1,
  synthesisName: 'MySynthesis',
  fastaPath: null,
  materialsPath: null,
  vessels: [],
  residueMap: {},
  reagents: {
    deprotectionReagent: 'Piperidine 20%',
    activator: 'HBTU',
    useOxyma: true,
    base: 'DIEA',
    volumeMode: 'stoichiometry',
    completenessTest: 'bromophenol'
  },
  resin: {
    strategy: 'fixed',
    substitutionMmolG: 0.3,
    fixedResinMassG: 0.1,
    targetYieldMg: null
  },
  outputDirectory: 'spps_output',
  generateResult: { status: 'idle' }
}

export type WizardAction =
  | { type: 'SET_STEP'; step: WizardState['step'] }
  | {
      type: 'SET_SEQUENCES'
      fastaPath: string
      materialsPath: string | null
      vessels: ParsedVessel[]
      residueMap: Record<string, ResidueMwEntry>
    }
  | { type: 'SET_RESIDUE_MAP'; residueMap: Record<string, ResidueMwEntry> }
  | { type: 'SET_RESIDUE'; token: string; entry: ResidueMwEntry }
  | { type: 'SET_REAGENTS'; reagents: Partial<ReagentsState> }
  | { type: 'SET_RESIN'; resin: Partial<ResinState> }
  | { type: 'SET_OUTPUT_DIRECTORY'; outputDirectory: string }
  | { type: 'SET_SYNTHESIS_NAME'; name: string }
  | { type: 'GENERATE_START' }
  | { type: 'GENERATE_SUCCESS'; paths: Record<string, string> }
  | { type: 'GENERATE_ERROR'; error: string }

export function wizardReducer(state: WizardState, action: WizardAction): WizardState {
  switch (action.type) {
    case 'SET_STEP':
      return { ...state, step: action.step }
    case 'SET_SEQUENCES':
      return {
        ...state,
        fastaPath: action.fastaPath,
        materialsPath: action.materialsPath,
        vessels: action.vessels,
        residueMap: action.residueMap
      }
    case 'SET_RESIDUE_MAP':
      return { ...state, residueMap: action.residueMap }
    case 'SET_RESIDUE':
      return {
        ...state,
        residueMap: { ...state.residueMap, [action.token]: action.entry }
      }
    case 'SET_REAGENTS':
      return { ...state, reagents: { ...state.reagents, ...action.reagents } }
    case 'SET_RESIN':
      return { ...state, resin: { ...state.resin, ...action.resin } }
    case 'SET_OUTPUT_DIRECTORY':
      return { ...state, outputDirectory: action.outputDirectory }
    case 'SET_SYNTHESIS_NAME':
      return { ...state, synthesisName: action.name }
    case 'GENERATE_START':
      return { ...state, generateResult: { status: 'generating' } }
    case 'GENERATE_SUCCESS':
      return { ...state, generateResult: { status: 'success', paths: action.paths } }
    case 'GENERATE_ERROR':
      return { ...state, generateResult: { status: 'error', error: action.error } }
    default:
      return state
  }
}
