import { decimalId } from './businessId.js'

const activeStatuses = new Set(['queued', 'running'])
const terminalStatuses = new Set(['completed', 'failed', 'cancelled'])

// Lives with the portal shell, so changing the current page never stops tracking.
export function createGenerationMonitor({ listJobs, getJob, updateTasks, onCompleted, onError, storage, interval = 5000 }) {
  let owner = ''
  let epoch = 0
  let timer
  let inflight
  let pending = new Set()
  let notified = new Set()
  let initialized = false
  let knownIds = new Set()

  function read() {
    try {
      const state = JSON.parse(storage?.getItem(`ps-generation-notices-${owner}`) || '{}')
      return {
        pending: Array.isArray(state.pending) ? state.pending.filter(decimalId) : [],
        notified: Array.isArray(state.notified) ? state.notified.filter(value => typeof value === 'string') : []
      }
    } catch { return { pending: [], notified: [] } }
  }
  function persist() {
    try {
      storage?.setItem(`ps-generation-notices-${owner}`, JSON.stringify({ pending: [...pending], notified: [...notified].slice(-200) }))
    } catch { /* Tracking still works for the current session when storage is unavailable. */ }
  }
  function observe(tasks, submittedIds = []) {
    if (!owner) return
    for (const id of submittedIds) if (decimalId(id)) pending.add(String(id))
    for (const task of tasks) {
      if (task.ownerId != null && String(task.ownerId) !== owner) continue
      const id = decimalId(task.jobId || task.id)
      if (!id) continue
      if (activeStatuses.has(task.status)) pending.add(id)
      if (!pending.has(id) || !terminalStatuses.has(task.status)) continue
      if (task.status === 'completed' && task.reportStatus !== 'completed' && !task.applyConflict) continue
      pending.delete(id)
      if (task.status === 'completed' && (task.reportStatus === 'completed' || task.applyConflict) && decimalId(task.reportId)) {
        const key = id
        // Another open tab may already have shown this completion.
        if (notified.has(key) || read().notified.includes(key)) continue
        notified.add(key)
        persist()
        onCompleted(task)
      }
    }
    persist()
  }
  async function page(params) {
    const { data } = await listJobs(params)
    if (!Array.isArray(data?.rows) || !Number.isSafeInteger(Number(data.total)) || Number(data.total) < 0) {
      throw new Error('生成队列加载失败，请重试')
    }
    return data
  }
  async function refresh() {
    if (!owner || inflight) return inflight
    clearTimeout(timer)
    const currentEpoch = epoch
    const current = () => Boolean(owner) && currentEpoch === epoch
    const request = (async () => {
      try {
        const [recent, firstActive] = await Promise.all([
          page({ pageNum: 1, pageSize: 20 }),
          page({ pageNum: 1, pageSize: 100, status: 'active' })
        ])
        if (!current()) return
        const rows = new Map(recent.rows.map(task => [String(task.jobId || task.id), task]))
        const addActive = result => { for (const task of result.rows) rows.set(String(task.jobId || task.id), task) }
        addActive(firstActive)
        // The active queue can be larger than the latest-history page.
        for (let number = 2; number <= Math.ceil(Number(firstActive.total) / 100); number++) {
          addActive(await page({ pageNum: number, pageSize: 100, status: 'active' }))
          if (!current()) return
        }
        const missing = [...pending].filter(id => !rows.has(id))
        const finished = await Promise.allSettled(missing.map(id => getJob(id)))
        if (!current()) return
        for (const result of finished) {
          if (result.status === 'fulfilled') {
            const task = result.value.data
            const id = decimalId(task?.jobId || task?.id)
            if (id) rows.set(id, task)
          }
        }
        const tasks = [...rows.values()]
        for (const task of tasks) {
          const id = decimalId(task.jobId || task.id)
          if (!id || (task.ownerId != null && String(task.ownerId) !== owner)) continue
          if (initialized && !knownIds.has(id)) pending.add(id)
          knownIds.add(id)
        }
        initialized = true
        updateTasks(tasks)
        observe(tasks)
        onError('')
      } catch (error) {
        if (current()) onError(error?.msg || error?.message || '生成队列暂时无法更新，请重试')
      } finally {
        if (current()) timer = setTimeout(refresh, interval)
      }
    })()
    inflight = request
    try { await request } finally { if (inflight === request) inflight = null }
  }
  function stop() {
    epoch++
    owner = ''
    clearTimeout(timer)
    inflight = null
  }
  function start(userId) {
    stop()
    initialized = false
    knownIds = new Set()
    owner = decimalId(userId) || ''
    if (!owner) return
    const state = read()
    pending = new Set(state.pending)
    notified = new Set(state.notified)
    void refresh()
  }
  return { start, stop, observe, refresh }
}
