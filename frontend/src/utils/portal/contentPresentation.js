import { formatBusinessTime } from './businessTime.js'

export const ENTITY_LABELS = ['地点', '时间', '政策', '人物', '机构', '技术']
const entityAliases = { location: '地点', place: '地点', time: '时间', date: '时间', policy: '政策', person: '人物', people: '人物', 人: '人物', organization: '机构', organisation: '机构', institution: '机构', org: '机构', technology: '技术', tech: '技术' }

export function entityGroups(value) {
  const groups = ENTITY_LABELS.map(label => ({ label, values: [] }))
  for (const entity of Array.isArray(value) ? value : []) {
    if (!entity || typeof entity.name !== 'string' || typeof entity.type !== 'string') continue
    const label = entityAliases[entity.type.toLowerCase()] || entity.type
    const group = groups.find(group => group.label === label)
    const name = entity.name.trim()
    if (group && name && !group.values.includes(name)) group.values.push(name)
  }
  return groups
}

export function contentCategory(item = {}) {
  const name = item.categoryName || item.category_name || item.classification?.name || (typeof item.category === 'object' ? item.category?.name : '')
  if (typeof name === 'string' && name.trim()) return name.trim()
  const legacy = item.category
  return typeof legacy === 'string' && !/^(?:all|article|news|wechat|paper|material|document|内部资料|内部文献|上传资料|\d+)$/i.test(legacy) ? legacy.trim() : ''
}

export function collectionTime(item = {}) {
  return formatBusinessTime(item.collectedAt || item.collected_at || item.crawledAt || item.crawled_at || item.collectedTime || item.collected_time || '')
}

function paragraphs(value) {
  if (Array.isArray(value)) return value.filter(value => typeof value === 'string' && value.trim())
  return typeof value === 'string' ? value.split(/[\r\n]+/).map(value => value.trim()).filter(Boolean) : []
}

export function readingContent(item = {}) {
  const original = paragraphs(item.contentOriginal || item.content_original || item.originalContent || item.original_content || item.content || (item.contentZh || item.content_zh ? '' : item.body))
  const translated = paragraphs(item.contentZh || item.content_zh || '')
  return { original, translated, hasTranslation: translated.length > 0 }
}

function text(value) {
  if (Array.isArray(value)) return value.map(text).filter(Boolean).join('；')
  if (value && typeof value === 'object') return text(value.content || value.summary || value.description || value.text || '')
  return typeof value === 'string' ? value.trim() : ''
}

// Present stored interpretation only. Never manufacture conclusions from titles.
export function insightSections(item = {}, kind = 'news') {
  const raw = item.aiInsight || item.ai_insight || item.aiInterpretation || item.ai_interpretation || item.metadata?.aiInsight || item.metadata?.ai_insight || {}
  const entries = Array.isArray(raw) ? Object.fromEntries(raw.filter(value => value && typeof value === 'object').map(value => [value.title || value.label, text(value)])) : typeof raw === 'object' && raw ? raw : { summary: text(raw) }
  const fields = kind === 'paper' ? [
    ['研究机构与作者', ['institution', 'institutions', 'organization', '研究机构', '机构', '研究机构与作者']],
    ['研究工作', ['research', 'work', 'contribution', 'summary', '研究工作', '研究内容']],
    ['效果与证据', ['effect', 'effects', 'result', 'results', '效果', '研究效果', '效果与证据']],
    ['技术与应用场景', ['scenario', 'scenarios', 'application', 'technology', '应用场景', '技术与应用场景']]
  ] : [
    ['机构与人物', ['organization', 'institution', 'people', '机构与人物']],
    ['政策背景', ['policy', 'policy_background', '政策背景']],
    ['技术重点', ['technology', 'technical_points', 'technicalPoints', '技术重点']],
    ['政策重点', ['policy_focus', 'policyFocus', '政策重点']],
    ['应用场景', ['scenario', 'application', '应用场景']]
  ]
  const sections = fields.map(([label, keys]) => ({
    label,
    content: [...new Set(keys.map(key => text(entries[key]) || (key !== 'summary' ? text(item[key]) : '')).filter(Boolean))].join('；')
  }))
  // Preserve additional, actually stored interpretation without dropping evidence.
  for (const [label, value] of Object.entries(entries)) {
    if (!fields.some(([, keys]) => keys.includes(label)) && text(value)) sections.push({ label, content: text(value) })
  }
  return sections
}

// Join saved passages for reading, without generating missing facts or using the abstract.
export function paperInsightParagraph(item = {}) {
  const passages = [...new Set(insightSections(item, 'paper')
    .map(section => section.content.replace(/\s+/g, ' ').trim())
    .filter(Boolean))]
  return passages.map((passage, index) => {
    if (/[。！？.!?；;：:][”’"']?$/.test(passage)) return passage
    return `${passage}${index === passages.length - 1 ? '。' : '；'}`
  }).join(' ')
}
