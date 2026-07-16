import { useEffect, useState } from 'react'
import { Button } from '../components/ui/button'
import { Card, CardContent } from '../components/ui/card'
import SynthesisEmptyState from '../components/SynthesisEmptyState'
import { useExportFile } from '../hooks/useExportFile'
import type { MaterialsViewData } from '../../../preload/index.d'

type MaterialsState =
  | { status: 'loading' }
  | { status: 'none' }
  | { status: 'error' }
  | { status: 'loaded'; materials: MaterialsViewData; outputPaths: Record<string, string> }

interface MaterialsProps {
  onNewSynthesis: () => void
}

export default function Materials({ onNewSynthesis }: Readonly<MaterialsProps>): React.JSX.Element {
  const [state, setState] = useState<MaterialsState>({ status: 'loading' })
  const { exportError, handleExport } = useExportFile()

  useEffect(() => {
    let cancelled = false
    window.spps
      .getLastSynthesis()
      .then((envelope) => {
        if (cancelled) return
        if (envelope.ok && envelope.data?.materials) {
          setState({
            status: 'loaded',
            materials: envelope.data.materials,
            outputPaths: envelope.data.output_paths ?? {}
          })
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

  if (state.status === 'loading') {
    return <p className="text-text3 font-sans text-sm p-5">Loading…</p>
  }

  if (state.status === 'error' || state.status === 'none') {
    return (
      <SynthesisEmptyState
        status={state.status}
        errorMessage="Couldn't load materials. Is the sidecar running?"
        onNewSynthesis={onNewSynthesis}
      />
    )
  }

  const { materials } = state
  const xlsxPath = state.outputPaths.materials_xlsx
  const pdfPath = state.outputPaths.materials_pdf

  return (
    <div className="bg-bg p-5">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-text font-sans text-base font-medium">Materials explosion</h1>
          <p className="text-text3 font-mono text-xs">{materials.synthesis_name}</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <div className="flex gap-2">
            {xlsxPath && (
              <Button onClick={() => handleExport(xlsxPath)} className="bg-bg3">
                ⬇ Export XLSX
              </Button>
            )}
            {pdfPath && (
              <Button onClick={() => handleExport(pdfPath)} className="bg-bg3">
                ⬇ Export PDF
              </Button>
            )}
          </div>
          {exportError && <p className="text-red-500 font-sans text-xs">{exportError}</p>}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <Card className="bg-bg2">
          <CardContent className="py-4">
            <div className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">
              Total residue types
            </div>
            <div className="text-teal font-mono text-2xl font-light">{materials.total_residue_types}</div>
          </CardContent>
        </Card>
        <Card className="bg-bg2">
          <CardContent className="py-4">
            <div className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">
              Total Fmoc-AA mass
            </div>
            <div className="text-teal font-mono text-2xl font-light">
              {materials.total_mass_mg.toFixed(1)} <span className="text-sm text-text3">mg</span>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-bg2">
          <CardContent className="py-4">
            <div className="text-text3 font-sans text-xs uppercase tracking-wide mb-1">
              Total reagent volume
            </div>
            <div className="text-teal font-mono text-2xl font-light">
              {materials.total_volume_ml.toFixed(2)} <span className="text-sm text-text3">mL</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <h2 className="text-text2 font-sans text-xs uppercase tracking-wide mb-2">Amino acid requirements</h2>
      <Card className="bg-bg2 mb-4">
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-text3 font-sans text-xs uppercase">
                <th className="text-left p-2">Residue</th>
                <th className="text-left p-2">Fmoc-MW</th>
                <th className="text-left p-2">mmol</th>
                <th className="text-left p-2">Mass to weigh</th>
                <th className="text-left p-2">Volume</th>
              </tr>
            </thead>
            <tbody>
              {materials.rows.map((row) => (
                <tr key={row.token} className="border-t border-[color:var(--border)]">
                  <td className="p-2 text-text font-mono">
                    {row.token}
                    {row.protection && <span className="text-text3">({row.protection})</span>}
                  </td>
                  <td className="p-2 text-text2 font-mono">{row.fmoc_mw.toFixed(1)}</td>
                  <td className="p-2 text-text2 font-mono">{row.mmol_needed.toFixed(2)}</td>
                  <td className="p-2 text-teal font-mono">
                    {row.volume_ul !== null ? `${row.volume_ul.toFixed(1)} µL` : `${row.mass_mg.toFixed(1)} mg`}
                  </td>
                  <td className="p-2 text-text2 font-mono">{row.volume_ml.toFixed(2)} mL</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <h2 className="text-text2 font-sans text-xs uppercase tracking-wide mb-2">Calculation basis</h2>
      <Card className="bg-bg2">
        <CardContent className="py-3">
          {Object.entries(materials.config_summary).map(([key, value]) => (
            <div key={key} className="flex justify-between text-xs font-sans py-1">
              <span className="text-text3">{key}</span>
              <span className="text-text2 font-mono">{value}</span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
