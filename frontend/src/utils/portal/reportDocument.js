// Heading numbering belongs to presentation, not the saved section title.
function sectionTitle(value) {
  return String(value || '').replace(/^(?:(?:\d+\.)+\s+)+/, '').trim()
}

function isReferenceSection(title) {
  return ['参考资料', '参考文献', 'references'].includes(sectionTitle(title).toLowerCase())
}

export function cleanReportCitationNotes(content, title = '') {
  const text = String(content || '')
  if (isReferenceSection(title)) return text
  let referenceLevel = null
  let fence = null
  return text.split('\n').map(line => {
    const marker = line.match(/^\s*(`{3,}|~{3,})/)
    if (marker) {
      if (fence === null) fence = marker[1]
      else if (marker[1][0] === fence[0] && marker[1].length >= fence.length) fence = null
      return line
    }
    if (fence !== null) return line
    const heading = line.match(/^(#{1,6})\s+(.+?)\s*#*$/)
    if (heading) {
      if (referenceLevel !== null && heading[1].length <= referenceLevel) referenceLevel = null
      if (isReferenceSection(heading[2])) referenceLevel = heading[1].length
      return line
    }
    if (referenceLevel !== null) return line
    const protectedText = []
    const protect = value => {
      protectedText.push(value)
      return `\ue000${protectedText.length - 1}\ue001`
    }
    const shielded = line.replace(/`+[^`\n]*`+/g, protect)
    const cleaned = shielded.replace(/(\[\d+\])[ \t]*[（(](?:新闻正文|论文摘要|文献信息|用户资料|内部资料)[^()（）\n]*[）)]/g, '$1')
      .replace(/\[[^\]\n]*\]\([^\n)]*\)/g, protect)
    const positioned = cleaned.replace(/[^。！？；\n]+/g, clause => {
      const markers = [...new Set(clause.match(/\[[1-9]\d*\](?!\()/g) || [])]
      if (!markers.length) return clause
      const joined = clause.replace(/\[[1-9]\d*\](?:(?:和|及|与|、)\[[1-9]\d*\])+/g, (group, offset) =>
        !clause.slice(0, offset).trim() || /^[ \t]*(?:[，,：:]|$)/.test(clause.slice(offset + group.length))
          ? group.match(/\[[1-9]\d*\]/g).join('') : group)
      const body = joined.replace(/\[[1-9]\d*\](?!\()/g, '')
      const trimmed = body.replace(/[ \t]+$/, '')
      return trimmed + markers.join('') + body.slice(trimmed.length)
    })
    return positioned.replace(/\ue000(\d+)\ue001/g, (_match, index) => protectedText[Number(index)])
  }).join('\n')
}

export function reportCitationParts(paragraph, title, citationCount) {
  const text = cleanReportCitationNotes(paragraph, title).trimStart()
  if (isReferenceSection(title)) return [{ text, citation: false }]
  const parts = []
  let offset = 0
  for (const match of text.matchAll(/\[([1-9]\d*)\](?!\()/g)) {
    if (Number(match[1]) > citationCount) continue
    if (match.index > offset) parts.push({ text: text.slice(offset, match.index), citation: false })
    parts.push({ text: match[0], citation: true })
    offset = match.index + match[0].length
  }
  if (offset < text.length) parts.push({ text: text.slice(offset), citation: false })
  return parts
}

function sourceText(value) {
  if (typeof value === 'string') return value.trim()
  if (!value || typeof value !== 'object') return ''
  return [...new Set(['name', 'title', 'sourceName', 'publisher', 'journal', 'filename', 'doi', 'url']
    .map(key => value[key]).filter(item => typeof item === 'string' && item.trim()).map(item => item.trim()))].join('，')
}

function numberedCitations(content, citations) {
  const aliases = new Map()
  citations.forEach((item, index) => {
    const identity = String(item.sourceId ?? item.id ?? '')
    for (const token of [`资料${identity}`, ...(item.type ? [`${item.type}:${identity}`] : [])]) {
      aliases.set(token, [...(aliases.get(token) || []), index + 1])
    }
  })
  const numbered = String(content || '').replace(/\[([^\]\n]+)\]/g, (original, value) => {
    const tokens = value.match(/资料\d+|(?:article|paper|file):\d+/g) || []
    if (!tokens.length || tokens.some(token => aliases.get(token)?.length !== 1)) return original
    const numbers = [...new Set(tokens.map(token => aliases.get(token)[0]))]
    const note = value.replace(/资料\d+|(?:article|paper|file):\d+/g, '').replace(/^[；;,，、 ]+|[；;,，、 ]+$/g, '')
    return numbers.map(number => `[${number}]`).join('') + (note ? `（${note}）` : '')
  })
  return numbered.replace(/\[[^\]\n]+\]|资料\d+(?:[、，,]\d+)*/g, value => {
    if (value.startsWith('[')) return value
    const tokens = value.match(/\d+/g).map(identity => `资料${identity}`)
    if (tokens.some(token => aliases.get(token)?.length !== 1)) return value
    return tokens.map(token => `[${aliases.get(token)[0]}]`).join('、')
  })
}

function referenceLines(citations) {
  return citations.map((item, index) => {
    const label = index + 1
    const details = [sourceText(item.source) || sourceText(item.type), sourceText(item.location)].filter(Boolean)
    return `[${label}] ${item.title || '未命名来源'}${details.length ? `（${details.join('，')}）` : ''}`
  })
}

export function buildReportMarkdown({ title = '', sections = [], citations = [] } = {}) {
  const references = referenceLines(citations).join('\n')
  const hasReferences = sections.some(section => isReferenceSection(section.title))
  const blocks = sections.map(section => {
    const heading = sectionTitle(section.title)
    // An authored reference section is authoritative; never append a second copy.
    const content = isReferenceSection(heading) && !String(section.content || '').trim() ? references : cleanReportCitationNotes(numberedCitations(section.content, citations), heading)
    return `## ${heading}\n\n${content}`
  })
  if (!hasReferences && references) blocks.push(`## 参考资料\n\n${references}`)
  return [`# ${title}`, ...blocks].join('\n\n')
}
