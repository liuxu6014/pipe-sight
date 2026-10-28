import { reactive, ref } from 'vue'
import { decimalId } from './businessId.js'

export function createDigestCandidateSearch(list) {
  const query = reactive({ keyword: '', source: '', page: 1, size: 10 })
  const rows = ref([]), total = ref(0), loading = ref(false), error = ref('')
  let context = {}, generation = 0, stopped = false
  async function load() {
    if (stopped || !context.enabled) return
    const token = ++generation
    const params = { category: 'article', keyword: query.keyword.trim() || undefined,
      source_type: ['', 'news', 'wechat'].includes(query.source) ? query.source || undefined : undefined,
      sortBy: 'publication', pageNum: query.page, pageSize: query.size }
    // Keep the last total until the response arrives: a transient zero makes
    // Element Plus clamp a controlled page back to page one while fetching.
    loading.value = true; error.value = ''; rows.value = []
    try {
      const response = await list(params)
      if (stopped || token !== generation) return
      const data = response?.data, count = data?.total
      if (!Array.isArray(data?.rows) || !Number.isSafeInteger(count) || count < 0 || data.rows.length > query.size || count < data.rows.length || data.rows.some(row => !row || !decimalId(row.id) || row.category === 'paper')) throw new Error('候选资讯返回格式无效，请重试')
      const lastPage = Math.max(1, Math.ceil(count / query.size))
      if (query.page > lastPage) { query.page = lastPage; return load() }
      rows.value = data.rows.map(row => ({ ...row, id: decimalId(row.id) }))
      total.value = count
    } catch (reason) {
      if (!stopped && token === generation) error.value = reason?.msg || reason?.message || '候选资讯加载失败，请重试'
    } finally { if (!stopped && token === generation) loading.value = false }
  }
  function search() { query.page = 1; return load() }
  function setPage(value) { query.page = Number.isSafeInteger(Number(value)) && Number(value) > 0 ? Number(value) : 1; return load() }
  function setSize(value) { query.size = [10, 20, 50].includes(Number(value)) ? Number(value) : 10; return search() }
  function configure(next) {
    generation++
    if (context.epoch !== next.epoch) Object.assign(query, { keyword: '', source: '', page: 1, size: 10 })
    context = { ...next }; rows.value = []; total.value = 0; loading.value = false; error.value = ''
    if (!stopped && context.enabled) return load()
  }
  function dispose() { stopped = true; generation++; rows.value = []; total.value = 0; error.value = ''; loading.value = false; context = {} }
  return { query, rows, total, loading, error, search, reload: load, setPage, setSize, configure, dispose }
}

export function candidateSourceLabel(item) {
  return (typeof item.source === 'string' ? item.source : item.source?.name || item.source?.title) || '来源未记录'
}
