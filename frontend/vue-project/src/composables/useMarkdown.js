/**
 * Minimal markdown-to-HTML renderer for project docs.
 * Handles: headings, fenced code, tables, lists, HR, bold, inline code, links, paragraphs.
 */

function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function inline(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code class="md-inline">$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
}

function parseTable(tableLines) {
  const isSep = (l) => /^\|[\s\-:|]+\|$/.test(l)
  const header = tableLines[0]
  const body = tableLines.filter((l, i) => i > 0 && !isSep(l))
  const parseRow = (l) => l.split('|').slice(1, -1).map(c => c.trim())
  const ths = parseRow(header).map(c => `<th>${inline(c)}</th>`).join('')
  const trs = body.map(l =>
    `<tr>${parseRow(l).map(c => `<td>${inline(c)}</td>`).join('')}</tr>`
  ).join('')
  return `<table class="md-table"><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`
}

export function renderMarkdown(markdown) {
  if (!markdown) return ''
  const parts = []
  const lines = markdown.split('\n')
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // Fenced code block
    if (line.startsWith('```')) {
      const lang = line.slice(3).trim() || 'text'
      const codeLines = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      i++ // skip closing ```
      parts.push(
        `<pre class="md-pre"><code class="md-code lang-${lang}">${esc(codeLines.join('\n'))}</code></pre>`
      )
      continue
    }

    // Table
    if (line.startsWith('|')) {
      const tableLines = []
      while (i < lines.length && lines[i].startsWith('|')) {
        tableLines.push(lines[i])
        i++
      }
      parts.push(parseTable(tableLines))
      continue
    }

    // Heading
    const hm = line.match(/^(#{1,6})\s+(.+)$/)
    if (hm) {
      const lvl = hm[1].length
      const id = hm[2].toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-')
      parts.push(`<h${lvl} class="md-h${lvl}" id="${id}">${inline(hm[2])}</h${lvl}>`)
      i++
      continue
    }

    // Horizontal rule
    if (/^---+\s*$/.test(line)) {
      parts.push('<hr class="md-hr">')
      i++
      continue
    }

    // Unordered list
    if (/^\s*[-*]\s/.test(line)) {
      const baseIndent = line.match(/^(\s*)/)[1].length
      const items = []
      while (
        i < lines.length &&
        /^\s*[-*]\s/.test(lines[i]) &&
        lines[i].match(/^(\s*)/)[1].length === baseIndent
      ) {
        items.push(`<li>${inline(lines[i].replace(/^\s*[-*]\s+/, ''))}</li>`)
        i++
      }
      parts.push(`<ul class="md-ul">${items.join('')}</ul>`)
      continue
    }

    // Blank line
    if (line.trim() === '') {
      i++
      continue
    }

    // Paragraph
    const paraLines = []
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !lines[i].startsWith('#') &&
      !lines[i].startsWith('```') &&
      !lines[i].startsWith('|') &&
      !/^\s*[-*]\s/.test(lines[i]) &&
      !/^---+\s*$/.test(lines[i])
    ) {
      paraLines.push(lines[i])
      i++
    }
    if (paraLines.length > 0) {
      parts.push(`<p class="md-p">${inline(paraLines.join(' '))}</p>`)
    }
  }

  return parts.join('\n')
}
