// TEMP (Task 2 verification) — replaced by Task 6's real App shell
import { Button } from './components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from './components/ui/card'

function App(): React.JSX.Element {
  return (
    <div className="min-h-screen bg-bg p-8">
      <Card className="bg-bg2 border-[color:var(--border)] max-w-sm">
        <CardHeader>
          <CardTitle className="text-text font-sans">Design token check</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-text2 font-mono text-sm mb-4">585.7 g/mol</p>
          <Button className="bg-teal text-bg hover:bg-teal/90">Primary action</Button>
        </CardContent>
      </Card>
    </div>
  )
}

export default App
