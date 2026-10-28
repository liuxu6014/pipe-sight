import { decimalId, displayId, ID_UPGRADE_NOTICE } from './businessId.js'
import { getCitationPath } from './citationRouting.js'
import { materialBasketReason } from './listQuery.js'

export function buildLibraryItems(basket = [], documents = [], papers = [], news = []) {
  const rows = new Map()
  const paperCatalog = new Map(papers.map(item => [String(item.id), item]))
  const newsCatalog = new Map(news.map(item => [String(item.id), item]))
  const contentKeys = new Map()
  for (const document of documents) {
    const id = displayId(document.id)
    if (!id) continue
    const hash = document.fileHash || document.file_hash
    const contentKey = /^[a-f0-9]{64}$/i.test(hash || '') ? `${document.ownerId ?? document.owner_id ?? ''}:${hash.toLowerCase()}:${document.editHash || document.edit_hash || 'original'}` : `id:${id}`
    const key = contentKeys.get(contentKey) || `document:${id}`
    const item = { ...document, id, kind: 'document', type: 'material', name: document.name || document.title || '未命名资料', duplicateIds: [id] }
    const previous = rows.get(key)
    if (previous) {
      const ids = [...new Set([...previous.duplicateIds, id])].sort((a, b) => a.length - b.length || a.localeCompare(b))
      const ready = value => ['已解析', 'indexed'].includes(value.status)
      const preferNew = ready(item) !== ready(previous) ? ready(item) : ids[0] === id
      rows.set(key, { ...(preferNew ? item : previous), duplicateIds: ids })
    } else {
      contentKeys.set(contentKey, key)
      rows.set(key, item)
    }
  }
  for (const item of basket) {
    const id = decimalId(item.id)
    if (!id) continue
    const path = getCitationPath({ sourceId: id, type: item.type })
    const kind = path?.startsWith('/portal/papers/') ? 'paper' : path?.startsWith('/portal/news/') ? 'news' : null
    // Uploaded materials use the live, permission-filtered document collection.
    // A stale saved snapshot must not resurrect a deleted or inaccessible file.
    if (!kind || rows.has(`${kind}:${id}`)) continue
    const row = { ...item, ...(kind === 'paper' ? paperCatalog : newsCatalog).get(id) }
    rows.set(`${kind}:${id}`, { ...row, id, kind, type: kind === 'paper' ? 'paper' : 'article',
      name: row.titleZh || row.title || row.name || '未命名资料',
      summary: row.summary || row.abstract || '', format: kind === 'paper' ? '论文' : '新闻', status: '可用于生成' })
  }
  return [...rows.values()]
}

export function libraryItemPath(item) { return getCitationPath({ sourceId: item.id, type: item.type || item.kind }) }
export function libraryItemReason(item) {
  if (!decimalId(item.id)) return ID_UPGRADE_NOTICE
  return item.kind === 'document' ? materialBasketReason(item) : ''
}

export async function prepareLibrarySelection(items, persist, isActive = () => true) {
  if (!items.length) throw new Error('请先勾选资料')
  if (items.length > 50) throw new Error('每次生成最多选择 50 条资料，请减少勾选；已选资料不会被截断')
  for (const item of items) {
    const reason = libraryItemReason(item)
    if (reason) throw new Error(`${item.name || '所选资料'}：${reason}`)
  }
  const ids = []
  for (const item of items) {
    if (!isActive()) throw new Error('资料保存已中止，请重新选择')
    const outcome = await persist(item, item.kind === 'document' ? 'material' : item.kind === 'paper' ? 'paper' : 'article')
    if (!isActive() || !['saved', 'exists'].includes(outcome)) throw new Error('资料保存未完成，请重试；已选资料不会被截断')
    ids.push(item.id)
  }
  return ids
}
