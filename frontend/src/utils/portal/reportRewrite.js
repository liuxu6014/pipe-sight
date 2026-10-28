const references = text => [...String(text).matchAll(/\[(?:\d+|(?:article|paper|file):\d+)\]/g)].map(item => item[0]).sort().join('|')

export function makeRewriteDraft(section, text) {
  const content = String(section?.content || '')
  text = String(text || '').trim()
  const start = content.indexOf(text)
  if (!text || text.length > 6000 || start < 0) throw new Error('请选择不超过 6000 字的正文片段')
  if (content.indexOf(text, start + 1) >= 0) throw new Error('所选内容在本章重复出现，请扩大选择范围以明确位置')
  return { sectionId: String(section.id), sectionTitle: section.title, content, original: text, start, end: start + text.length }
}

export function rewriteRequest(draft, report, mode) {
  return { sectionId: draft.sectionId, start: Array.from(draft.content.slice(0, draft.start)).length,
    end: Array.from(draft.content.slice(0, draft.end)).length, text: draft.original, mode,
    expectedVersion: report.versionNo, expectedRevision: report.revision }
}

export function applyRewriteDraft(sections, draft, replacement) {
  const section = sections.find(item => String(item.id) === draft.sectionId)
  if (!section || section.content !== draft.content) throw new Error('原章节已修改，请重新生成建议，当前正文未被替换')
  replacement = String(replacement || '').trim()
  if (!replacement || references(replacement) !== references(draft.original)) throw new Error('改写结果为空或引用标记发生变化，请检查后再应用')
  section.content = draft.content.slice(0, draft.start) + replacement + draft.content.slice(draft.end)
  section.words = section.content.length
  return section
}
