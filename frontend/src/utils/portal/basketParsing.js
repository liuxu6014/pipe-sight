import { computed, onScopeDispose, ref, watch } from 'vue'

const pendingStates = new Set(['queued', 'parsing', '等待解析', '解析中', '待解析'])
const statusOf = doc => doc?.parseStatus || doc?.status

export function useBasketParsing(store, active, api, timers = globalThis) {
  const error = ref('')
  const retrying = ref([])
  const checkedMissing = ref(new Set())
  let timer, running = false, stopped = false, generation = 0
  const documents = computed(() => {
    const rows = new Map()
    for (const doc of store.liveDocuments) {
      for (const id of [doc.id, ...(doc.duplicateIds || [])]) rows.set(String(id), doc)
    }
    return rows
  })
  const pending = computed(() => store.basket.some(item => ['file', 'material'].includes(item.type) && pendingStates.has(statusOf(documents.value.get(String(item.id))))))
  const files = computed(() => store.basket.filter(item => ['file', 'material'].includes(item.type)))
  const needsRefresh = computed(() => pending.value || files.value.some(item => !documents.value.has(String(item.id)) && !checkedMissing.value.has(String(item.id))) || Boolean(files.value.length && (error.value || store.sectionErrors?.documents)))
  function label(id) {
    if (checkedMissing.value.has(String(id))) return '资料不存在或无权访问'
    const status = statusOf(documents.value.get(String(id)))
    if (!status && checkedMissing.value.has(String(id))) return '资料不存在或无权访问'
    if (pendingStates.has(status)) return '解析中'
    if (['ready', 'indexed', '已解析'].includes(status)) return '已解析，可用于生成'
    return ['failed', '解析失败'].includes(status) ? '解析失败' : ''
  }
  function clear() { if (timer !== undefined) timers.clearTimeout(timer); timer = undefined }
  function schedule() {
    if (!stopped && active() && needsRefresh.value && timer === undefined) timer = timers.setTimeout(async () => {
      timer = undefined
      await refresh()
    }, 3000)
  }
  async function refresh() {
    if (running || stopped || !active()) { schedule(); return }
    running = true
    const epoch = store.workspaceEpoch, token = generation
    try {
      let response, missing = []
      if (api.get) {
        // A paginated/deduplicated upload page is not proof that a saved file
        // was deleted. Resolve the actual authorized references in bounded batches.
        const ids = [...new Set(files.value.map(item => String(item.id)))]
        const rows = []
        for (let offset = 0; offset < ids.length; offset += 10) {
          const batch = ids.slice(offset, offset + 10)
          const results = await Promise.allSettled(batch.map(id => api.get(id)))
          if (stopped || token !== generation || epoch !== store.workspaceEpoch) return
          for (const [index, result] of results.entries()) {
            if (result.status === 'fulfilled' && result.value?.data?.id) rows.push(result.value.data)
            else if (result.status === 'rejected' && /不存在|无权访问|not found/i.test(result.reason?.msg || result.reason?.message || '')) missing.push(batch[index])
            else throw new Error('资料状态暂不可用')
          }
        }
        const freshIds = new Set(rows.map(doc => String(doc.id)))
        response = { data: { rows: [...store.liveDocuments.filter(doc => !freshIds.has(String(doc.id))), ...rows] } }
      } else response = await api.list()
      if (stopped || token !== generation || epoch !== store.workspaceEpoch) return
      if (!Array.isArray(response?.data?.rows)) throw new Error('无效资料状态')
      store.liveDocuments = response.data.rows
      const returnedIds = new Set(response.data.rows.map(row => String(row.id)))
      checkedMissing.value = new Set(api.get ? missing : files.value.filter(item => !returnedIds.has(String(item.id))).map(item => String(item.id)))
      if (store.sectionErrors) store.sectionErrors.documents = ''
      error.value = ''
    } catch {
      if (!stopped && token === generation && epoch === store.workspaceEpoch) error.value = '资料状态更新失败，正在自动重试'
    } finally { running = false; schedule() }
  }
  async function retry(id) {
    id = String(id)
    if (retrying.value.includes(id) || stopped) return
    const epoch = store.workspaceEpoch, token = generation
    retrying.value = [...retrying.value, id]
    try {
      await api.retry(id)
      if (stopped || token !== generation || epoch !== store.workspaceEpoch) return
      // Mark as queued immediately, even if the following status refresh fails.
      store.liveDocuments = store.liveDocuments.map(doc => String(doc.id) === id || doc.duplicateIds?.map(String).includes(id) ? { ...doc, parseStatus: 'queued' } : doc)
      await refresh()
    } catch {
      if (!stopped && token === generation && epoch === store.workspaceEpoch) error.value = '重新解析提交失败，请重试'
    } finally {
      if (token === generation) retrying.value = retrying.value.filter(value => value !== id)
      schedule()
    }
  }
  watch([needsRefresh, active], ([needed, enabled]) => { if (needed && enabled) schedule(); else clear() }, { immediate: true })
  watch(() => store.workspaceEpoch, () => { generation++; clear(); checkedMissing.value = new Set(); retrying.value = []; error.value = ''; schedule() }, { flush: 'sync' })
  onScopeDispose(() => { stopped = true; generation++; clear() })
  return { label, error, retrying, retry }
}
