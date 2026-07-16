import { useState } from 'react'

/**
 * Shared export-button behavior for read-only synthesis views (Cycle Guide,
 * Materials): opens a real generated file via the main process's openFile
 * IPC handler, surfacing any failure message it returns.
 */
export function useExportFile(): {
  exportError: string | null
  handleExport: (path: string) => Promise<void>
} {
  const [exportError, setExportError] = useState<string | null>(null)

  async function handleExport(path: string): Promise<void> {
    setExportError(null)
    const result = await window.spps.openFile(path)
    if (result) {
      setExportError(result)
    }
  }

  return { exportError, handleExport }
}
