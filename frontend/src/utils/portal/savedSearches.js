import { decimalId } from './businessId.js'

const DEFAULTS = {
  news: { q: '', source: '全部', tag: [] },
  paper: { q: '', year: 'all', years: [], journals: [] },
  search: { q: '', mode: 'keyword', type: 'all', date: 'all', source: 'all', directions: [] },
  knowledge: { q: '', status: 'all' },
}
const ENUMS = {
  news: { source: ['全部', '新闻网站', '微信公众号'] },
  search: { mode: ['keyword'], type: ['all', 'news', 'paper', 'document', 'report'], date: ['all', 'week', 'year'], source: ['all', 'public', 'internal'] },
  knowledge: { status: ['all', '已解析', '解析中', '待解析', '解析失败', '待安全扫描', '已隔离', '扫描失败'] },
}

export function normalizeSearchFilters(kind, input = {}) {
  const defaults = DEFAULTS[kind]
  if (!defaults) throw new Error('不支持的检索页面')
  if (kind === 'search' && input.mode === 'semantic') throw new Error('语义检索尚未接入，不能保存为可执行条件')
  const result = {}
  for (const [key, fallback] of Object.entries(defaults)) {
    const value = input[key] ?? fallback
    if (Array.isArray(fallback)) {
      if (!Array.isArray(value) || value.length > 20 || value.some(item => typeof item !== 'string' || item.length > 200)) throw new Error('筛选项最多 20 个，每项不超过 200 字')
      result[key] = [...new Set(value.map(item => item.trim()).filter(Boolean))].sort()
    } else {
      if (typeof value !== 'string' || value.length > 200) throw new Error('关键词或筛选值最多 200 字')
      result[key] = value.trim()
      if (ENUMS[kind]?.[key] && !ENUMS[kind][key].includes(result[key])) throw new Error('保存的筛选值已不可用，请重新设置')
    }
  }
  if (kind === 'paper') {
    if (result.year !== 'all' && !/^\d{4}$/.test(result.year)) throw new Error('年份格式无效')
    if (result.years.length && (result.years.length !== 2 || result.years.some(value => !/^\d{4}$/.test(value)))) throw new Error('年份范围无效')
    if (result.year !== 'all') result.years = []
  }
  return result
}

export function searchFilterChips(kind, input) {
  const filters = normalizeSearchFilters(kind, input)
  const labels = { q: '关键词', tag: '标签', year: '年份', years: '年份范围', journals: '期刊', type: '内容', date: '时间', source: '来源', directions: '类别', status: '状态' }
  const values = { type: { news: '新闻资讯', paper: '论文', document: '内部资料', report: '我的报告' }, date: { week: '近一周', year: '近一年' }, source: { public: '公开来源', internal: '内部资料' } }
  return Object.entries(filters).flatMap(([field, value]) => {
    if (JSON.stringify(value) === JSON.stringify(DEFAULTS[kind][field]) || field === 'mode') return []
    const items = field === 'years' ? [value.join('—')] : Array.isArray(value) ? value : [value]
    return items.map(item => ({ field, value: item, label: `${labels[field]}：${values[field]?.[item] || item}` }))
  })
}

export function withoutSearchFilter(kind, input, chip) {
  const filters = normalizeSearchFilters(kind, input)
  filters[chip.field] = Array.isArray(filters[chip.field]) && chip.field !== 'years'
    ? filters[chip.field].filter(value => value !== chip.value) : DEFAULTS[kind][chip.field]
  return filters
}

export function applySavedSearchQuery(query, filters, kind) {
  const before = JSON.stringify(query)
  Object.assign(query, normalizeSearchFilters(kind, filters), { page: 1 })
  if (kind === 'news') query.category = '全部'
  return JSON.stringify(query) !== before
}

export function createSavedSearchRepository(storage, userId, kind) {
  const identity = decimalId(userId)
  if (!identity) throw new Error('请登录后保存常用条件')
  normalizeSearchFilters(kind)
  const key = `pipesight:saved-searches:v1:${identity}:${kind}`
  function list() {
    try {
      const raw = storage.getItem(key)
      if (!raw) return []
      const data = JSON.parse(raw)
      if (data.version !== 1 || !Array.isArray(data.rows) || data.rows.length > 12) throw new Error('invalid')
      const ids = new Set()
      return data.rows.map(row => {
        if (!row || typeof row.name !== 'string' || !row.name.trim() || row.name.length > 50 || typeof row.id !== 'string' || !/^[\w-]{1,100}$/.test(row.id) || ids.has(row.id)) throw new Error('invalid')
        ids.add(row.id)
        return { id: row.id, name: row.name.trim(), filters: normalizeSearchFilters(kind, row.filters) }
      })
    } catch { throw new Error('本浏览器保存的条件无法读取，原数据未被覆盖') }
  }
  function write(rows) {
    try { storage.setItem(key, JSON.stringify({ version: 1, rows })) }
    catch { throw new Error('无法保存到当前浏览器，请检查存储权限或空间；原列表未更新') }
    return rows
  }
  return {
    key, list,
    save(name, input) {
      name = String(name || '').trim()
      if (!name || name.length > 50) throw new Error('请输入 1—50 字的条件名称')
      const filters = normalizeSearchFilters(kind, input)
      if (!searchFilterChips(kind, filters).length) throw new Error('请先设置关键词或筛选条件')
      const rows = list()
      const existing = rows.find(row => JSON.stringify(row.filters) === JSON.stringify(filters))
      if (existing) existing.name = name
      else {
        if (rows.length >= 12) throw new Error('本页最多保存 12 组条件，请先移除不再使用的条件')
        rows.push({ id: `s-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`, name, filters })
      }
      return write(rows)
    },
    remove(id) { return write(list().filter(row => row.id !== id)) },
  }
}
