// Locate the sentence attached to a citation, whether the marker is before or after punctuation.
export function citationSentenceBounds(text, markerStart, markerEnd) {
  const prefix = text.slice(0, markerStart).replace(/(?:\s|\[\d+\]|[。！？；.!?;”’"'])+$/g, '')
  let start = 0
  for (const match of prefix.matchAll(/[。！？；\n]|[.!?;](?=\s|$)/g)) start = match.index + match[0].length
  while (/\s/.test(text[start] || '') && start < markerStart) start++
  let end = markerEnd
  const suffix = text.slice(end).match(/^(?:\[\d+\]|[。！？；.!?;”’"'])*/)
  end += suffix?.[0].length || 0
  return { start, end }
}

export function citationSentenceRange(paragraph, marker) {
  const doc = paragraph.ownerDocument
  const before = doc.createRange()
  before.selectNodeContents(paragraph)
  before.setEndBefore(marker)
  const startOffset = before.toString().length
  const bounds = citationSentenceBounds(paragraph.textContent, startOffset, startOffset + marker.textContent.length)
  const walker = doc.createTreeWalker(paragraph, 4)
  const range = doc.createRange()
  let offset = 0, node, started = false
  while ((node = walker.nextNode())) {
    const next = offset + node.length
    if (!started && bounds.start <= next) { range.setStart(node, bounds.start - offset); started = true }
    if (started && bounds.end <= next) { range.setEnd(node, bounds.end - offset); return range }
    offset = next
  }
  return null
}
