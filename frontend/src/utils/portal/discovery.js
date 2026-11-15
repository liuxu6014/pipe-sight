import { formatBusinessTime } from './businessTime.js'

export function cleanSummary(value = '') {
  return String(value).replace(/^导读摘要（据公开资料整理）\s*[:：]\s*/, '')
}
export function newsDate(value) {
  const text = formatBusinessTime(value)
  return text ? text.replace(/ 00:00:00$/, '') : ''
}
export function cleanSource(value = '') {
  return String(value).replace(/\s*[（(][^（）()]*(?:官网|核验|核实|验证|转载)[^（）()]*[）)]/g, '').trim()
}
export function cleanResultMeta(value = '') {
  return cleanSource(value).replace(/\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?/g, value => newsDate(value)).replace(/\s*·\s*$/, '')
}
export function combineLatest(news = [], papers = []) {
  return [
    ...news.map(item => ({ ...item, kind: 'news', kindLabel: item.source_type === 'wechat' ? '公众号' : '资讯', path: `/portal/news/${item.id}`, date: newsDate(item.publish_time), dateKey: formatBusinessTime(item.publish_time), source: cleanSource(item.source), summary: cleanSummary(item.summary) })),
    ...papers.map(item => ({ ...item, kind: 'paper', kindLabel: '论文', path: `/portal/papers/${item.id}`, date: newsDate(item.publish_time || item.publication_year), dateKey: formatBusinessTime(item.publish_time || item.publication_year), source: cleanSource(item.journal || item.source), summary: cleanSummary(item.summary) }))
  ].sort((a, b) => b.dateKey.localeCompare(a.dateKey) || String(a.id).localeCompare(String(b.id)))
}
export function resultPath(item) {
  if (item.type === 'report' && ['daily', 'weekly', 'monthly'].includes(item.report_type)) return `/portal/digests/${item.id}`
  return typeof item.path === 'string' && item.path.startsWith('/portal/') && !item.path.includes('://') ? item.path : ''
}
