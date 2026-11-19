import test from 'node:test'
import assert from 'node:assert/strict'
import { createGenerationMonitor } from '../src/utils/portal/generationMonitor.js'

const job = (id, status, overrides = {}) => ({
  id: String(id), ownerId: '7', reportId: String(1000 + Number(id)), title: `报告 ${id}`,
  type: 'research-demand', status, reportStatus: status === 'completed' ? 'completed' : 'draft', ...overrides
})
const page = rows => ({ data: { rows, total: rows.length } })
const memory = () => {
  const values = new Map()
  return { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) }
}
const lockQueue = () => {
  let tail = Promise.resolve()
  return { request(_key, callback) {
    const result = tail.then(callback)
    tail = result.catch(() => {})
    return result
  } }
}
function setup(api = {}, storage = memory()) {
  const updates = [], completed = [], errors = []
  const monitor = createGenerationMonitor({
    listJobs: async () => page([]), getJob: async () => ({ data: null }), storage,
    updateTasks: tasks => updates.push(tasks), onCompleted: task => completed.push(task), onError: error => errors.push(error),
    ...api
  })
  return { monitor, updates, completed, errors, storage }
}

test('tracks multiple queued reports across page changes and notifies once per completed report', async () => {
  let finished = false
  const old = job(10, 'completed')
  const ctx = setup({ listJobs: async params => {
    const tasks = [job(11, finished ? 'completed' : 'running'), job(12, finished ? 'completed' : 'queued')]
    return page(params.status === 'active' ? tasks.filter(task => task.status !== 'completed') : [old, ...tasks])
  } })
  try {
    ctx.monitor.start('7')
    await ctx.monitor.refresh()
    assert.equal(ctx.completed.length, 0, 'old completed history is silent')
    finished = true
    // The monitor belongs to the portal, and is still running after a page leaves.
    await ctx.monitor.refresh()
    assert.deepEqual(ctx.completed.map(task => task.id), ['11', '12'])
    await ctx.monitor.refresh()
    assert.equal(ctx.completed.length, 2)
    assert.equal(ctx.updates.at(-1).filter(task => task.status === 'completed').length, 3)
  } finally { ctx.monitor.stop() }
})

test('recovers pending reports after refresh and remembers already shown completions', async () => {
  const storage = memory()
  const first = setup({ listJobs: async () => page([job(11, 'queued')]) }, storage)
  first.monitor.start('7')
  await first.monitor.refresh()
  first.monitor.stop()
  const second = setup({ listJobs: async params => page(params.status === 'active' ? [] : [job(11, 'completed')]) }, storage)
  try {
    second.monitor.start('7')
    await second.monitor.refresh()
    assert.equal(second.completed.length, 1)
  } finally { second.monitor.stop() }
  const third = setup({ listJobs: async () => page([job(11, 'completed')]) }, storage)
  try {
    third.monitor.start('7')
    await third.monitor.refresh()
    assert.equal(third.completed.length, 0)
  } finally { third.monitor.stop() }
})

test('a stale tab saving a running queue cannot erase another tab completion receipt', async () => {
  const storage = memory()
  const first = setup({}, storage), second = setup({}, storage)
  try {
    first.monitor.start('7')
    second.monitor.start('7')
    await Promise.all([first.monitor.refresh(), second.monitor.refresh()])
    first.monitor.observe([job(11, 'queued'), job(12, 'queued')])
    second.monitor.observe([job(11, 'queued'), job(12, 'queued')])
    first.monitor.observe([job(11, 'completed'), job(12, 'running')])
    second.monitor.observe([job(11, 'running'), job(12, 'running')])
    second.monitor.observe([job(11, 'completed'), job(12, 'completed')])
    first.monitor.observe([job(11, 'completed'), job(12, 'completed')])
    assert.deepEqual([...first.completed, ...second.completed].map(task => task.id).sort(), ['11', '12'])
  } finally { first.monitor.stop(); second.monitor.stop() }
})

test('a second tab cannot overwrite pending tracking for a task outside recent history after reload', async () => {
  const storage = memory()
  const first = setup({}, storage), second = setup({}, storage)
  first.monitor.start('7')
  second.monitor.start('7')
  await Promise.all([first.monitor.refresh(), second.monitor.refresh()])
  first.monitor.observe([job(11, 'queued')])
  second.monitor.observe([job(12, 'queued')])
  first.monitor.stop(); second.monitor.stop()
  const requested = []
  const reloaded = setup({ getJob: async id => { requested.push(id); return { data: job(id, 'completed') } } }, storage)
  try {
    reloaded.monitor.start('7')
    await reloaded.monitor.refresh()
    assert.deepEqual(requested.sort(), ['11', '12'])
    assert.deepEqual(reloaded.completed.map(task => task.id).sort(), ['11', '12'])
  } finally { reloaded.monitor.stop() }
})

test('simultaneous tab completions atomically claim one notification with shared browser locks', async () => {
  const storage = memory(), locks = lockQueue()
  const first = setup({ locks }, storage), second = setup({ locks }, storage)
  try {
    first.monitor.start('7'); second.monitor.start('7')
    await Promise.all([first.monitor.refresh(), second.monitor.refresh()])
    await Promise.all([first.monitor.observe([job(11, 'queued')]), second.monitor.observe([job(12, 'queued')])])
    await Promise.all([
      first.monitor.observe([job(11, 'completed'), job(12, 'completed')]),
      second.monitor.observe([job(11, 'completed'), job(12, 'completed')])
    ])
    assert.deepEqual([...first.completed, ...second.completed].map(task => task.id).sort(), ['11', '12'])
    const saved = JSON.parse(storage.getItem('ps-generation-notices-7'))
    assert.deepEqual(saved.pending, [])
    assert.deepEqual(saved.notified.sort(), ['11', '12'])
  } finally { first.monitor.stop(); second.monitor.stop() }
})

test('stale running data cannot resurrect failed or cancelled tracking after another tab settles it', async () => {
  const storage = memory(), locks = lockQueue()
  const first = setup({ locks }, storage), second = setup({ locks }, storage)
  try {
    first.monitor.start('7'); second.monitor.start('7')
    await Promise.all([first.monitor.refresh(), second.monitor.refresh()])
    await first.monitor.observe([job(11, 'running'), job(12, 'queued')])
    await second.monitor.observe([job(11, 'failed'), job(12, 'cancelled')], ['11', '12'])
    await first.monitor.observe([job(11, 'running'), job(12, 'queued')])
    assert.deepEqual(JSON.parse(storage.getItem('ps-generation-notices-7')).pending, [])
    assert.equal(first.completed.length + second.completed.length, 0)
  } finally { first.monitor.stop(); second.monitor.stop() }
})

test('a queued notification lock cannot announce for a previous account', async () => {
  const locks = lockQueue()
  let unblock
  const blocker = locks.request('block', () => new Promise(resolve => { unblock = resolve }))
  await Promise.resolve()
  const ctx = setup({ locks })
  ctx.monitor.start('7')
  const pending = ctx.monitor.observe([job(11, 'completed')], ['11'])
  ctx.monitor.start('8')
  unblock(); await blocker; await pending; await ctx.monitor.refresh()
  assert.equal(ctx.completed.length, 0)
  assert.equal(ctx.storage.getItem('ps-generation-notices-7'), undefined)
  ctx.monitor.stop()
})

test('fetches the full active queue and follows a completed job outside recent history', async () => {
  let finished = false
  const calls = [], details = []
  const active = Array.from({ length: 101 }, (_, i) => job(i + 1, 'queued'))
  const ctx = setup({
    listJobs: async params => {
      calls.push(params)
      if (!params.status) return page(active.slice(80))
      const tasks = finished ? active.slice(1) : active
      const start = (params.pageNum - 1) * params.pageSize
      return { data: { rows: tasks.slice(start, start + params.pageSize), total: tasks.length } }
    },
    getJob: async id => { details.push(id); return { data: job(id, 'completed') } }
  })
  try {
    ctx.monitor.start('7')
    await ctx.monitor.refresh()
    assert.ok(calls.some(params => params.status === 'active' && params.pageNum === 2))
    assert.equal(ctx.updates.at(-1).length, 101)
    finished = true
    await ctx.monitor.refresh()
    assert.deepEqual(details, ['1'])
    assert.deepEqual(ctx.completed.map(task => task.id), ['1'])
  } finally { ctx.monitor.stop() }
})

test('network failures and incomplete outputs never trigger successful generation notices', async () => {
  let phase = 0
  const ctx = setup({ listJobs: async () => {
    if (phase === 1) throw Error('连接失败')
    return page([job(11, phase ? 'completed' : 'queued', { reportStatus: phase === 3 ? 'completed' : 'draft' })])
  } })
  try {
    ctx.monitor.start('7')
    await ctx.monitor.refresh()
    phase = 1
    await ctx.monitor.refresh()
    assert.equal(ctx.errors.at(-1), '连接失败')
    assert.equal(ctx.completed.length, 0)
    phase = 2
    await ctx.monitor.refresh()
    assert.equal(ctx.completed.length, 0)
    phase = 3
    await ctx.monitor.refresh()
    assert.equal(ctx.completed.length, 1)
  } finally { ctx.monitor.stop() }
})

test('a newly submitted task that finishes before the first refresh is still announced', async () => {
  const ctx = setup()
  try {
    ctx.monitor.start('7')
    await ctx.monitor.refresh()
    ctx.monitor.observe([job(11, 'completed')], ['11'])
    ctx.monitor.observe([job(11, 'completed', { updatedAt: 'changed' })], ['11'])
    assert.equal(ctx.completed.length, 1)
  } finally { ctx.monitor.stop() }
})

test('a late previous-account response cannot update the new account or announce its reports', async () => {
  let release
  const previous = new Promise(resolve => { release = resolve })
  const ctx = setup({ listJobs: async () => previous })
  ctx.monitor.start('7')
  const old = ctx.monitor.refresh()
  ctx.monitor.stop()
  release(page([job(11, 'completed')]))
  await old
  assert.equal(ctx.updates.length, 0)
  assert.equal(ctx.completed.length, 0)
  ctx.monitor.start('8')
  await ctx.monitor.refresh()
  ctx.monitor.observe([job(11, 'completed')], ['11'])
  assert.equal(ctx.completed.length, 0)
  ctx.monitor.stop()
})

test('a fast new task completed between polls still produces a completion notice', async () => {
  let second = false
  const ctx = setup({ listJobs: async params => page(params.status === 'active' || !second ? [] : [job(11, 'completed')]) })
  try {
    ctx.monitor.start('7')
    await ctx.monitor.refresh()
    second = true
    await ctx.monitor.refresh()
    assert.deepEqual(ctx.completed.map(task => task.id), ['11'])
    await ctx.monitor.refresh()
    assert.equal(ctx.completed.length, 1)
  } finally { ctx.monitor.stop() }
})

test('a completed result retained after a report edit still notifies even if the current report is empty', async () => {
  let finished = false
  const ctx = setup({ listJobs: async params => page(params.status === 'active' && finished ? [] : [
    job(11, finished ? 'completed' : 'queued', { applyConflict: finished, reportStatus: 'draft' })
  ]) })
  try {
    ctx.monitor.start('7')
    await ctx.monitor.refresh()
    finished = true
    await ctx.monitor.refresh()
    assert.equal(ctx.completed.length, 1)
    assert.equal(ctx.completed[0].applyConflict, true)
    await ctx.monitor.refresh()
    assert.equal(ctx.completed.length, 1)
  } finally { ctx.monitor.stop() }
})
