import { decimalId } from './businessId.js'

export function getCitationPath(source) {
  // A citation's own id is a local reference number, not a source record ID.
  const id = decimalId(source?.sourceId ?? source?.source_id)
  if (!id) return null
  const type = String(source?.type || '').trim().toLowerCase()
  if (type === 'paper' || /论文/.test(type)) return `/portal/papers/${id}`
  if (['article', 'news', 'website', 'wechat'].includes(type) || /资讯|新闻|公众号/.test(type)) return `/portal/news/${id}`
  if (['file', 'document', 'knowledge', 'material'].includes(type) || /内部资料|上传资料/.test(type)) return `/portal/knowledge/${id}`
  return null
}
