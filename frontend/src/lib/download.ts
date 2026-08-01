export function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export function downloadTextFile(filename: string, content: string, mime: string) {
  downloadBlob(filename, new Blob([content], { type: mime }))
}

function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback
  const match = /filename="([^"]+)"/.exec(header)
  return match?.[1] ?? fallback
}

export async function downloadFromResponse(response: Response, fallbackFilename: string) {
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    if (
      typeof payload === 'object' &&
      payload !== null &&
      'error' in payload &&
      typeof (payload as { error?: { message?: string } }).error?.message === 'string'
    ) {
      throw new Error((payload as { error: { message: string } }).error.message)
    }
    throw new Error(response.statusText || 'Download failed')
  }
  const blob = await response.blob()
  const filename = filenameFromDisposition(
    response.headers.get('Content-Disposition'),
    fallbackFilename,
  )
  downloadBlob(filename, blob)
  return filename
}
