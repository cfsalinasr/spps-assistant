import { describe, expect, it } from 'vitest'
import { initialWizardState, wizardReducer, type ResidueMwEntry } from './wizardReducer'

describe('wizardReducer', () => {
  it('SET_STEP updates the current step', () => {
    const next = wizardReducer(initialWizardState, { type: 'SET_STEP', step: 3 })
    expect(next.step).toBe(3)
  })

  it('SET_SEQUENCES stores parsed vessels and the seeded residue map', () => {
    const residueMap: Record<string, ResidueMwEntry> = {
      A: {
        token: 'A',
        base_code: 'A',
        protection: '',
        fmoc_mw: 311.3,
        free_mw: 71.08,
        origin: 'materials'
      }
    }
    const next = wizardReducer(initialWizardState, {
      type: 'SET_SEQUENCES',
      fastaPath: '/tmp/seqs.fasta',
      materialsPath: '/tmp/mats.csv',
      vessels: [
        {
          number: 1,
          name: 'Pep1',
          original_tokens: ['A'],
          reversed_tokens: ['A'],
          resin_mass_g: 0.1,
          substitution_mmol_g: 0.3
        }
      ],
      residueMap
    })
    expect(next.fastaPath).toBe('/tmp/seqs.fasta')
    expect(next.materialsPath).toBe('/tmp/mats.csv')
    expect(next.vessels).toHaveLength(1)
    expect(next.residueMap).toEqual(residueMap)
  })

  it('SET_RESIDUE_MAP replaces the whole residue map', () => {
    const residueMap: Record<string, ResidueMwEntry> = {
      A: {
        token: 'A',
        base_code: 'A',
        protection: '',
        fmoc_mw: 311.3,
        free_mw: 71.08,
        origin: 'db'
      },
      G: {
        token: 'G',
        base_code: 'G',
        protection: '',
        fmoc_mw: 297.3,
        free_mw: 57.05,
        origin: 'db'
      }
    }
    const next = wizardReducer(initialWizardState, { type: 'SET_RESIDUE_MAP', residueMap })
    expect(next.residueMap).toEqual(residueMap)
  })

  it('SET_RESIDUE merges a single edited residue into the existing map without dropping others', () => {
    const withOne = wizardReducer(initialWizardState, {
      type: 'SET_RESIDUE_MAP',
      residueMap: {
        A: {
          token: 'A',
          base_code: 'A',
          protection: '',
          fmoc_mw: 311.3,
          free_mw: 71.08,
          origin: 'db'
        }
      }
    })
    const next = wizardReducer(withOne, {
      type: 'SET_RESIDUE',
      token: 'G',
      entry: {
        token: 'G',
        base_code: 'G',
        protection: '',
        fmoc_mw: 297.3,
        free_mw: 57.05,
        origin: 'manual'
      }
    })
    expect(Object.keys(next.residueMap)).toEqual(['A', 'G'])
    expect(next.residueMap.G.origin).toBe('manual')
  })

  it('SET_REAGENTS shallow-merges partial reagent updates', () => {
    const next = wizardReducer(initialWizardState, {
      type: 'SET_REAGENTS',
      reagents: { activator: 'DIC', base: 'None (DIC/DCC)' }
    })
    expect(next.reagents.activator).toBe('DIC')
    expect(next.reagents.base).toBe('None (DIC/DCC)')
    expect(next.reagents.deprotectionReagent).toBe('Piperidine 20%')
  })

  it('SET_RESIN shallow-merges partial resin updates', () => {
    const next = wizardReducer(initialWizardState, {
      type: 'SET_RESIN',
      resin: { strategy: 'target', targetYieldMg: 50 }
    })
    expect(next.resin.strategy).toBe('target')
    expect(next.resin.targetYieldMg).toBe(50)
    expect(next.resin.substitutionMmolG).toBe(0.3)
  })

  it('SET_OUTPUT_DIRECTORY updates the output directory', () => {
    const next = wizardReducer(initialWizardState, {
      type: 'SET_OUTPUT_DIRECTORY',
      outputDirectory: '/Users/me/output'
    })
    expect(next.outputDirectory).toBe('/Users/me/output')
  })

  it('SET_SYNTHESIS_NAME updates the synthesis name', () => {
    const next = wizardReducer(initialWizardState, { type: 'SET_SYNTHESIS_NAME', name: 'BatchA' })
    expect(next.synthesisName).toBe('BatchA')
  })

  it('GENERATE_START sets status to generating', () => {
    const next = wizardReducer(initialWizardState, { type: 'GENERATE_START' })
    expect(next.generateResult).toEqual({ status: 'generating' })
  })

  it('GENERATE_SUCCESS sets status to success with paths', () => {
    const next = wizardReducer(initialWizardState, {
      type: 'GENERATE_SUCCESS',
      paths: { cycle_guide_pdf: '/out/x.pdf' }
    })
    expect(next.generateResult).toEqual({
      status: 'success',
      paths: { cycle_guide_pdf: '/out/x.pdf' }
    })
  })

  it('GENERATE_ERROR sets status to error with a message', () => {
    const next = wizardReducer(initialWizardState, { type: 'GENERATE_ERROR', error: 'boom' })
    expect(next.generateResult).toEqual({ status: 'error', error: 'boom' })
  })
})
