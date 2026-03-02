/**
 * Trigger a browser file download from in-memory content.
 *
 * @param {string} content  – file body (text)
 * @param {string} filename – suggested file name (e.g. "ml_projection_D1.csv")
 * @param {string} mimeType – MIME type (e.g. "text/csv;charset=utf-8")
 */
export function downloadFile(content, filename, mimeType) {
  const normalised = content.replace(/\r\n/g, '\n')
  const blob = new Blob([normalised], { type: mimeType })
  const url = URL.createObjectURL(blob)

  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()

  // cleanup
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

export const MIME = {
  csv: 'text/csv;charset=utf-8',
  json: 'application/json;charset=utf-8',
  txt: 'text/plain;charset=utf-8',
}

/**
 * Build a safe filename slug from arbitrary text.
 * Replaces non-alphanumeric chars with underscores and collapses duplicates.
 */
export function sanitise(str) {
  return String(str || '')
    .replace(/[^a-zA-Z0-9._-]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_|_$/g, '')
}
