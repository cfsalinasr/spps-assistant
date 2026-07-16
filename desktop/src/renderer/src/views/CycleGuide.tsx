import { useEffect, useState } from 'react'
import { Button } from '../components/ui/button'
import { Card, CardContent } from '../components/ui/card'
import type { CycleGuideData, CyclePageData } from '../../../preload/index.d'

type CycleGuideState =
  | { status: 'loading' }
  | { status: 'none' }
  | { status: 'error' }
  | { status: 'loaded'; guide: CycleGuideData; outputPaths: Record<string, string> }

interface CycleGuideProps {
  onNewSynthesis: () => void
}

export default function CycleGuide({ onNewSynthesis }: Readonly<CycleGuideProps>): React.JSX.Element {
  const [state, setState] = useState<CycleGuideState>({ status: 'loading' })
  const [cycleIndex, setCycleIndex] = useState(0)
  const [exportError, setExportError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    window.spps
      .getLastSynthesis()
      .then((envelope) => {
        if (cancelled) return
        if (envelope.ok && envelope.data?.cycle_guide && envelope.data.cycle_guide.cycles.length > 0) {
          const guide = envelope.data.cycle_guide
          setState({ status: 'loaded', guide, outputPaths: envelope.data.output_paths ?? {} })
          const seeded = (envelope.data.current_cycle ?? 1) - 1
          setCycleIndex(Math.min(Math.max(seeded, 0), guide.cycles.length - 1))
        } else {
          setState({ status: 'none' })
        }
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'error' })
      })
    return () => {
      cancelled = true
    }
  }, [])

  function goTo(index: number, guide: CycleGuideData): void {
    const clamped = Math.min(Math.max(index, 0), guide.cycles.length - 1)
    setCycleIndex(clamped)
    window.spps.setCyclePosition(clamped + 1).catch(() => {
      // Non-fatal: this is a convenience position marker, not part of the
      // GMP audit trail. Keep the locally-navigated cycle either way.
    })
  }

  async function handleExport(path: string): Promise<void> {
    setExportError(null)
    const result = await window.spps.openFile(path)
    if (result) {
      setExportError(result)
    }
  }

  if (state.status === 'loading') {
    return <p className="text-text3 font-sans text-sm p-5">Loading…</p>
  }

  if (state.status === 'error' || state.status === 'none') {
    return (
      <div className="bg-bg p-5">
        <Card className="bg-bg2">
          <CardContent className="flex flex-col items-center justify-center py-10 text-center">
            <p className="text-text2 font-sans text-sm mb-4">
              {state.status === 'error'
                ? "Couldn't load the cycle guide. Is the sidecar running?"
                : 'No active synthesis yet.'}
            </p>
            <Button onClick={onNewSynthesis} className="bg-teal text-bg hover:bg-teal/90">
              + New synthesis
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  const cycle: CyclePageData = state.guide.cycles[cycleIndex]
  const pdfPath = state.outputPaths.cycle_guide_pdf
  const docxPath = state.outputPaths.cycle_guide_docx

  return (
    <div className="bg-bg p-5">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-text font-sans text-base font-medium">Coupling cycle guide</h1>
          <p className="text-text3 font-mono text-xs">{state.guide.synthesis_name}</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <div className="flex gap-2">
            {pdfPath && (
              <Button onClick={() => handleExport(pdfPath)} className="bg-bg3">
                ⬇ Export PDF
              </Button>
            )}
            {docxPath && (
              <Button onClick={() => handleExport(docxPath)} className="bg-bg3">
                ⬇ Export DOCX
              </Button>
            )}
          </div>
          {exportError && <p className="text-red-500 font-sans text-xs">{exportError}</p>}
        </div>
      </div>

      <Card className="bg-bg2 mb-4">
        <CardContent className="flex items-center justify-between py-4">
          <div>
            <div className="text-teal font-mono text-2xl font-light">{cycle.cycle_number}</div>
            <div className="text-text3 font-mono text-xs">of {cycle.total_cycles} total cycles</div>
          </div>
          <div className="flex gap-2">
            <Button disabled={cycleIndex === 0} onClick={() => goTo(cycleIndex - 1, state.guide)} className="bg-bg3">
              ◀ Prev
            </Button>
            <Button
              disabled={cycleIndex === state.guide.cycles.length - 1}
              onClick={() => goTo(cycleIndex + 1, state.guide)}
              className="bg-bg3"
            >
              Next ▶
            </Button>
          </div>
          <div className="text-right">
            <div className="text-text3 font-sans text-xs">Date</div>
            <div className="text-text2 font-sans text-sm border-b border-[color:var(--border)] min-w-[120px]">
              ________________
            </div>
          </div>
          <div className="text-right">
            <div className="text-text3 font-sans text-xs">Operator</div>
            <div className="text-text2 font-sans text-sm border-b border-[color:var(--border)] min-w-[120px]">
              ________________
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <h2 className="text-text2 font-sans text-xs uppercase tracking-wide mb-2">Amino acid dispatch</h2>
          <Card className="bg-bg2 mb-4">
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-text3 font-sans text-xs uppercase">
                    <th className="text-left p-2">Residue</th>
                    <th className="text-left p-2">Volume</th>
                    <th className="text-left p-2">Vessels</th>
                  </tr>
                </thead>
                <tbody>
                  {cycle.dispatch_rows.map((row, idx) => (
                    <tr key={`${row.residue_3letter}-${idx}`} className="border-t border-[color:var(--border)]">
                      <td className="p-2 text-text font-mono">{row.residue_3letter}</td>
                      <td className="p-2 text-teal font-mono">{row.volume_ml.toFixed(2)} mL</td>
                      <td className="p-2">
                        {row.vessel_numbers.map((vn) => (
                          <span key={vn} className="text-text2 font-mono text-xs mr-1">
                            V{vn}
                          </span>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <h2 className="text-text2 font-sans text-xs uppercase tracking-wide mb-2">Vessel assignment</h2>
          <Card className="bg-bg2">
            <CardContent className="py-3">
              {cycle.vessel_assignments.map((va) => (
                <div key={va.vessel_number} className="text-text2 font-mono text-xs mb-1">
                  V{va.vessel_number} <span className="text-text3">[{va.vessel_name}]</span> →{' '}
                  {va.residue_3letter ? (
                    <span className="text-teal">{va.residue_3letter}</span>
                  ) : (
                    <span className="text-text3">OUT</span>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <div>
          <h2 className="text-text2 font-sans text-xs uppercase tracking-wide mb-2">Deprotection record</h2>
          <Card className="bg-bg2 mb-4">
            <CardContent className="p-0">
              {cycle.deprotection_steps.map((step, idx) => (
                <div
                  key={`${step.label}-${idx}`}
                  className="flex items-center gap-3 p-2 border-b border-[color:var(--border)] last:border-b-0"
                >
                  <div className="flex gap-1">
                    {Array.from({ length: step.n_checkboxes }).map((_, i) => (
                      <div
                        key={`${step.label}-checkbox-${i}`}
                        className="w-3 h-3 border border-[color:var(--border2)]"
                      />
                    ))}
                  </div>
                  <div className="flex-1 text-text font-sans text-xs">{step.label}</div>
                  <div className="text-text3 font-sans text-xs">{step.duration}</div>
                </div>
              ))}
            </CardContent>
          </Card>

          <h2 className="text-text2 font-sans text-xs uppercase tracking-wide mb-2">Coupling record</h2>
          <Card className="bg-bg2">
            <CardContent className="p-0">
              {cycle.coupling_steps.map((step, idx) => (
                <div
                  key={`${step.label}-${idx}`}
                  className="flex items-center gap-3 p-2 border-b border-[color:var(--border)] last:border-b-0"
                >
                  {step.n_checkboxes > 0 && <div className="w-3 h-3 border border-[color:var(--border2)]" />}
                  <div className="flex-1">
                    <div className="text-text font-sans text-xs">{step.label}</div>
                    <div className="text-text3 font-sans text-xs">{step.detail}</div>
                  </div>
                  <div className="text-text3 font-sans text-xs">{step.duration}</div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
