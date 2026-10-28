import test from 'node:test'
import assert from 'node:assert/strict'
import { createExportHistory, exportStatusLabel } from '../src/utils/portal/exportHistory.js'

const row = (status = 'queued', extra = {}) => ({ exportId: '81', reportId: '40', format: 'docx', status, reportVersionNo: 2, ...extra })
function setup(api) {
  const timers = new Map(); let serial = 0
  const history = createExportHistory(api, { setTimeout(fn, delay) { timers.set(++serial, { fn, delay }); return serial }, clearTimeout(id) { timers.delete(id) } })
  return { history, timers, async tick() { const [id, timer] = timers.entries().next().value; timers.delete(id); await timer.fn() } }
}
test('pending records refresh to completion without creating another export task', async () => {
  let calls = 0
  const env = setup({ list: async () => ({ data: { rows: [row(++calls === 1 ? 'queued' : 'completed')] } }) })
  await env.history.configure({ reportId: '40', enabled: true, canDownload: true })
  assert.equal(env.timers.size, 1)
  await env.tick()
  assert.equal(env.history.records.value[0].status, 'completed')
  assert.equal(env.timers.size, 0)
  env.history.dispose()
})
test('list failure preserves the last records, retries, and malformed results never become an empty success', async () => {
  let calls = 0
  const env = setup({ list: async () => ({ data: ++calls === 1 ? { rows: [row()] } : { rows: null } }) })
  await env.history.configure({ reportId: '40', enabled: true })
  await env.tick()
  assert.equal(env.history.records.value.length, 1)
  assert.match(env.history.error.value, /格式/)
  assert.equal(env.timers.size, 1)
  env.history.dispose()
  assert.equal(env.timers.size, 0)
})
test('late list responses cannot expose records after report or account context changes', async () => {
  let resolve
  const env = setup({ list: () => new Promise(done => { resolve = done }) })
  const pending = env.history.configure({ reportId: '40', epoch: 1, enabled: true })
  await env.history.configure({ reportId: '41', epoch: 2, enabled: false })
  resolve({ data: { rows: [row('completed')] } })
  await pending
  assert.equal(env.history.records.value.length, 0)
  assert.equal(env.timers.size, 0)
  env.history.dispose()
})
test('downloads only recorded completed files without exposing internal revisions in filenames', async () => {
  const downloads = []
  const env = setup({ list: async () => ({ data: { rows: [row('completed'), row('failed', { exportId: '82' })] } }), download: async (...args) => downloads.push(args) })
  await env.history.configure({ reportId: '40', enabled: true, canDownload: true, title: '测试/简报' })
  await env.history.download(env.history.records.value[1])
  assert.equal(downloads.length, 0)
  await env.history.download(env.history.records.value[0])
  assert.deepEqual(downloads[0], ['81', '测试_简报.docx'])
  await env.history.configure({ reportId: '40', enabled: true, canDownload: false })
  await env.history.download(env.history.records.value[0])
  assert.equal(downloads.length, 1)
  env.history.dispose()
})
test('disabling the view stops pending polling and unknown status never implies success', async () => {
  const env = setup({ list: async () => ({ data: { rows: [row()] } }) })
  await env.history.configure({ reportId: '40', enabled: true })
  await env.history.configure({ reportId: '40', enabled: false })
  assert.equal(env.timers.size, 0)
  assert.equal(exportStatusLabel('mystery'), '状态未记录')
  env.history.dispose()
})
