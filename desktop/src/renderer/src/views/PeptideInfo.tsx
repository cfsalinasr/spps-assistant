import { Card, CardContent } from '../components/ui/card'

/**
 * Stub for the 5th planned view (per-peptide property sheets). Not a real
 * implementation yet — just makes the tab reachable with an honest status
 * message, per DESIGN_CONTEXT.md §10's empty-state pattern.
 */
export default function PeptideInfo(): React.JSX.Element {
  return (
    <div className="bg-bg p-5">
      <Card className="bg-bg2">
        <CardContent className="flex flex-col items-center justify-center py-10 text-center">
          <p className="text-text font-sans text-sm mb-1">Peptide information</p>
          <p className="text-text3 font-sans text-sm">Coming in a future release.</p>
        </CardContent>
      </Card>
    </div>
  )
}
