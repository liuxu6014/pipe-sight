import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { displayId, decimalId, ID_UPGRADE_NOTICE } from './businessId.js'

export const DIGEST_SELECTION_LIMIT = 50

export async function mapEvidence(items, action, concurrency = 4) {
  const results = new Array(items.length)
  let next = 0
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, async () => {
    while (next < items.length) {
      const index = next++
      results[index] = await action(items[index], index)
    }
  }))
  return results
}

export function selectionReferences(items = []) {
  return items.map(item => (typeof item === 'string' || typeof item === 'number') ? { id: item } : item)
    .filter(item => item?.id || item?.itemId || item?.item_id)
    .map(item => ({ id: displayId(item.id || item.itemId || item.item_id), type: item.itemType || item.item_type || item.type || item.category }))
}

function referenceType(value) {
  if (['paper', '论文'].includes(value)) return 'paper'
  if (['article', 'news', 'wechat', '科技资讯', '资讯'].includes(value)) return 'article'
  if (['file', 'material', 'document', '内部资料', '内部文献', '英文报告', '历史项目', '模板', '其他'].includes(value)) return 'material'
  if (value === 'report') return 'report'
  return ''
}

export function materialParseLabel(detail = {}) {
  return ({ queued: '解析中', parsing: '解析中', failed: '解析失败', 等待解析: '解析中', 待解析: '解析中', 解析中: '解析中', 解析失败: '解析失败' })[detail.parseStatus || detail.parse_status || detail.status] || ''
}

export function researchEvidenceRow(detail, kind, { catalog = false } = {}) {
  const material = kind === 'material'
  const paper = !material && (detail.category === 'paper' || detail.source_type === 'paper')
  let reason = ''
  if (material) {
    if ((detail.scanStatus ?? detail.scan_status) && (detail.scanStatus ?? detail.scan_status) !== 'clean') reason = '尚未通过安全检查'
    else if (!['ready', 'indexed', '已解析'].includes(detail.parseStatus || detail.parse_status || detail.status)) reason = materialParseLabel(detail) || '资料尚未解析就绪'
    else if ((detail.allowAiUse ?? detail.allow_ai_use) === false) reason = '未取得允许 AI 使用的授权'
    else if (!String(detail.editedText ?? detail.edited_text ?? detail.extractedText ?? detail.extracted_text ?? detail.parsedText ?? detail.content ?? detail.summary ?? '').trim()) reason = '没有可用的解析正文或摘要'
  } else {
    if (detail.allowAiUse === false || detail.allow_ai_use === false) reason = '未允许用于 AI'
    else if (paper && !String(detail.abstractZh || detail.abstract_zh || detail.abstract || detail.summary || '').trim()) reason = '论文未提供可用摘要；全文链接不能替代证据正文'
    else if (!paper && !String(detail.contentZh || detail.content_zh || detail.content || detail.summary || '').trim()) reason = '资讯没有可用正文或摘要'
  }
  return {
    id: String(detail.id), title: detail.name || detail.title || '题名未提供',
    itemType: material ? 'material' : paper ? 'paper' : 'article',
    type: material ? '内部资料' : paper ? '论文' : '科技资讯',
    meta: material ? `${detail.owner || '所有者未提供'} · ${detail.status || detail.parseStatus}`
      : paper ? `${detail.journal || detail.source || '来源未提供'} · 仅使用论文摘要`
        : `${detail.source || '来源未提供'} · ${detail.publish_time || detail.publishTime || '日期未提供'}`,
    ready: catalog && !material ? false : !reason,
    reason: catalog && !material ? '选择后核验' : reason,
    state: catalog && !material ? 'unchecked' : reason ? 'unavailable' : 'verified', detail
  }
}

export async function verifyEvidence(reference, { getIntelligence, getMaterial }) {
  const id = displayId(reference.id)
  const hinted = referenceType(reference.type)
  const unavailable = reason => ({ id, title: `选材 ${id}`, type: '待核验资料', ready: false, state: 'unavailable', reason, meta: reason })
  if (!decimalId(id)) return unavailable(ID_UPGRADE_NOTICE)
  if (hinted === 'report') return unavailable('当前生成接口不支持将报告作为证据，请移除或另选原始资料')
  // Legacy snapshots may label an internal paper as "论文", or save an article
  // as "material". A hint chooses the first endpoint, never proves the type.
  const endpoints = hinted === 'material' ? [[getMaterial, 'material'], [getIntelligence, 'article']]
    : [[getIntelligence, hinted || 'article'], [getMaterial, 'material']]
  let failure
  for (const [get, kind] of endpoints) {
    if (typeof get !== 'function') continue
    try {
      const response = await get(id)
      const detail = response?.data
      if (!detail || String(detail.id) !== id) throw new Error('详情返回的资料标识不匹配')
      return researchEvidenceRow(detail, kind)
    } catch (error) { failure = error }
  }
  return unavailable(failure?.msg || failure?.message || '资料不存在、已失权或服务不可用，请重新核验')
}

export function useEvidenceSelection(api, epoch = () => 0) {
  const selectedIds = ref([])
  const checks = ref({})
  const hints = new Map()
  const tokens = new Map()
  const pending = new Map()
  let stopped = false
  async function check(id, force = false, background = false) {
    id = displayId(id)
    if (stopped || !selectedIds.value.includes(id)) return
    if (!force && pending.has(id)) return pending.get(id)
    if (!force && checks.value[id]) return
    const token = (tokens.get(id) || 0) + 1
    const session = epoch()
    tokens.set(id, token)
    if (!background || !checks.value[id]) checks.value = { ...checks.value, [id]: { id, title: `选材 ${id}`, ready: false, state: 'checking', reason: '正在核验授权详情', meta: '正在核验授权详情' } }
    const request = verifyEvidence({ id, type: hints.get(id) }, api).then(row => {
      if (!stopped && tokens.get(id) === token && session === epoch() && selectedIds.value.includes(id) && (!background || row.detail)) checks.value = { ...checks.value, [id]: row }
      return row
    }).finally(() => { if (pending.get(id) === request) pending.delete(id) })
    pending.set(id, request)
    return await request
  }
  async function verifySelected(force = false) {
    const ids = [...selectedIds.value]
    await mapEvidence(ids, id => check(id, force))
    return ids.length > 0 && ids.every(id => checks.value[id]?.ready)
  }
  function setSelection(references) {
    const rows = selectionReferences(references)
    rows.forEach(row => { if (row.type) hints.set(row.id, row.type) })
    selectedIds.value = [...new Set(rows.map(row => row.id))]
  }
  function setHint(id, type) { hints.set(String(id), type) }
  watch(selectedIds, (ids, oldIds = []) => {
    const normalized = [...new Set(ids.map(displayId))]
    if (JSON.stringify(ids) !== JSON.stringify(normalized)) { selectedIds.value = normalized; return }
    for (const id of oldIds.filter(id => !ids.includes(id))) {
      tokens.set(id, (tokens.get(id) || 0) + 1)
      pending.delete(id)
      const next = { ...checks.value }; delete next[id]; checks.value = next
    }
    void verifySelected()
  }, { deep: true, flush: 'sync' })
  watch(epoch, () => {
    tokens.clear(); pending.clear()
    checks.value = Object.fromEntries(selectedIds.value.map(id => [id, { id, title: `选材 ${id}`, ready: false, state: 'unavailable', reason: '账号已变化，请重新核验', meta: '账号已变化，请重新核验' }]))
  }, { flush: 'sync' })
  onBeforeUnmount(() => { stopped = true; tokens.clear() })
  const selectedMaterials = computed(() => selectedIds.value.map(id => checks.value[id] || { id, title: `选材 ${id}`, ready: false, state: 'checking', reason: '等待核验', meta: '等待核验' }))
  const verifying = computed(() => selectedMaterials.value.some(item => item.state === 'checking'))
  const problems = computed(() => selectedMaterials.value.filter(item => !item.ready))
  return { selectedIds, selectedMaterials, checks, verifying, problems, setHint, setSelection, verifySelected, refreshEvidence: id => check(id, true, true) }
}

// Require an actual calendar date, never turn a bare publication year into Jan 1.
export function preciseDate(value) {
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})(?:$|[T ])/)
  if (!match) return ''
  const [, year, month, day] = match
  const date = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)))
  if (date.getUTCFullYear() !== Number(year) || date.getUTCMonth() + 1 !== Number(month) || date.getUTCDate() !== Number(day)) return ''
  if (/[T ].*(?:Z|[+-]\d{2}:?\d{2})$/.test(value)) {
    const instant = new Date(value)
    if (Number.isNaN(instant.getTime())) return ''
    return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).format(instant)
  }
  return `${year}-${month}-${day}`
}

export function digestCandidate(detail, scope) {
  if (detail.category === 'paper' || detail.source_type === 'paper') return false
  const date = preciseDate(detail.publishedAt || detail.published_at || detail.publish_time || detail.publishTime || detail.time)
  if (!date || date < scope.period[0] || date > scope.period.at(-1)) return false
  const source = ({ website: '新闻网站', news: '新闻网站', wechat: '微信公众号' })[detail.source_type || detail.sourceType]
  return scope.sources.includes(source)
}

export async function fetchDigestPage(scope, api, pageNum, pageSize = 20) {
  if (!scope.period.length || scope.period.some(value => !preciseDate(value)) || scope.period[0] > scope.period.at(-1)) throw new Error('请选择有效且完整的报告周期')
  if (!scope.sources.length) throw new Error('请至少选择一个资讯来源')
  const keywords = [...new Set(scope.keywords.map(value => String(value).trim()).filter(Boolean))]
  const page = await api.search({ period: scope.period, sources: scope.sources, directions: scope.directions, keywords, pageNum, pageSize })
  if (!Array.isArray(page.data?.rows) || !Number.isSafeInteger(Number(page.data?.total)) || Number(page.data.total) < 0 || page.data.rows.length > pageSize) throw new Error('候选查询返回的分页数据无效，请重试')
  const raw = [...new Map(page.data.rows.map(row => [String(row.id), row])).values()]
  const rows = await mapEvidence(raw, row => verifyEvidence({ id: row.id, type: 'article' }, api))
  const failed = rows.filter(row => !row.ready)
  if (failed.length) throw new Error(`本页有 ${failed.length} 条授权详情核验失败：${failed.map(row => `${row.id}（${row.reason}）`).join('；')}。请重试，本页未计入已核对范围。`)
  const total = Number(page.data.total)
  return { rows: rows.filter(row => digestCandidate(row.detail, scope)), inspected: raw.length, total, pageCount: Math.max(1, Math.ceil(total / pageSize)), truncated: false }
}
