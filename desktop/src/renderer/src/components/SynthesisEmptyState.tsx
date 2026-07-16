import { Button } from './ui/button'
import { Card, CardContent } from './ui/card'

interface SynthesisEmptyStateProps {
  status: 'error' | 'none'
  errorMessage: string
  onNewSynthesis: () => void
}

/**
 * Shared "no active synthesis yet" / "couldn't load" state for read-only
 * synthesis views (Cycle Guide, Materials) — the only difference between
 * views is the error message text.
 */
export default function SynthesisEmptyState({
  status,
  errorMessage,
  onNewSynthesis
}: Readonly<SynthesisEmptyStateProps>): React.JSX.Element {
  return (
    <div className="bg-bg p-5">
      <Card className="bg-bg2">
        <CardContent className="flex flex-col items-center justify-center py-10 text-center">
          <p className="text-text2 font-sans text-sm mb-4">
            {status === 'error' ? errorMessage : 'No active synthesis yet.'}
          </p>
          <Button onClick={onNewSynthesis} className="bg-teal text-bg hover:bg-teal/90">
            + New synthesis
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
