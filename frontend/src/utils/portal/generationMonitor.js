import { decimalId } from './businessId.js'

const activeStatuses = new Set(['queued', 'running'])
const terminalStatuses = new Set(['completed', 'failed', 'cancelled'])

// Lives with the portal shell, so changing the current page never stops tracking.
export function createGenerationMonitor({ listJobs, getJob, updateTasks, onCompleted, onError, storage, locks = globalThis.navigator?.locks, interval = 5000 }) {
  let owner = ''
  let epoch = 0
  let timer
  let inflight
  let pending = new Set()
  let notified = new Set()
  let settled = new Set()
  let announcing = new Set()
  let initialized = false
  let knownIds = new Set()

  function read() {
    try {
      const state = JSON.parse(storage?.getItem(`ps-generation-notices-${owner}`) || '{}')
      return {
        pending: Array.isArray(state.pending) ? state.pending.filter(decimalId) : [],
        notified: Array.isArray(state.notified) ? state.notified.filter(value => typeof value === 'string') : [],
        settled: Array.isArray(state.settled) ? state.settled.filter(decimalId) : []
      }
    } catch { return { pending: [], notified: [], settled: [] } }
  }
  function writeState() {
    try {
      // A still-running tab must not erase notices already claimed by another
      // tab when it saves its older pending queue after a refresh.
      const saved = read()
      for (const key of saved.notified) notified.add(key)
      for (const key of [...saved.settled, ...notified]) settled.add(key)
      for (const key of saved.pending) pending.add(key)
      for (const key of settled) pending.delete(key)
      storage?.setItem(`ps-generation-notices-${owner}`, JSON.stringify({ pending: [...pending], notified: [...notified].slice(-200), settled: [...settled].slice(-200) }))
    } catch { /* Tracking still works for the current session when storage is unavailable. */ }
  }
  function persist() {
    if (!locks?.request) return writeState()
    const currentEpoch = epoch, currentOwner = owner
    return (async () => {
      try {
        await locks.request(`ps-generation-notices-${currentOwner}`, () => {
          if (owner === currentOwner && epoch === currentEpoch) writeState()
        })
      } catch { if (owner === currentOwner && epoch === currentEpoch) onError('任务跟踪暂时无法同步，请在生成队列查看结果') }
    })()
  }
  function announce(task, id) {
    const currentEpoch = epoch, currentOwner = owner
    const current = () => owner === currentOwner && epoch === currentEpoch
    const claim = () => {
      if (!current()) return
      if (!notified.has(id) && !read().notified.includes(id)) {
        notified.add(id)
        settled.add(id)
        pending.delete(id)
        writeState()
        onCompleted(task)
      } else {
        settled.add(id)
        pending.delete(id)
        writeState()
      }
    }
    if (!locks?.request) return claim()
    if (announcing.has(id)) return
    const claims = announcing
    claims.add(id)
    // localStorage read/merge/write is not atomic across browser processes.
    // Serialize receipt claims when Web Locks is available (including localhost).
    void (async () => {
      try { await locks.request(`ps-generation-notices-${currentOwner}`, claim) }
      catch { if (current()) onError('完成提醒暂时无法同步，请在生成队列查看结果') }
      finally { claims.delete(id) }
    })()
  }
  function observe(tasks, submittedIds = []) {
    if (!owner) return
    for (const id of submittedIds) if (decimalId(id)) pending.add(String(id))
    for (const task of tasks) {
      if (task.ownerId != null && String(task.ownerId) !== owner) continue
      const id = decimalId(task.jobId || task.id)
      if (!id) continue
      if (activeStatuses.has(task.status) && !settled.has(id)) pending.add(id)
      if (!pending.has(id) || !terminalStatuses.has(task.status)) continue
      if (task.status === 'completed' && task.reportStatus !== 'completed' && !task.applyConflict) continue
      if (task.status === 'completed' && (task.reportStatus === 'completed' || task.applyConflict) && decimalId(task.reportId)) {
        announce(task, id)
      } else if (task.status !== 'completed') {
        settled.add(id)
        pending.delete(id)
      }
    }
    return persist()
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
        await observe(tasks)
        if (!current()) return
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
    announcing = new Set()
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
    settled = new Set([...state.settled, ...state.notified])
    void refresh()
  }
  return { start, stop, observe, refresh }
}
