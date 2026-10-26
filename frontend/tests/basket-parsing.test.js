import test from 'node:test'
import assert from 'node:assert/strict'
import { effectScope, reactive, nextTick } from 'vue'
import { useBasketParsing } from '../src/utils/portal/basketParsing.js'
import { verifyEvidence } from '../src/utils/portal/evidenceInput.js'

test('uploaded file basket references resolve directly as report materials, not news', async () => {
  let newsCalls = 0
  const row = await verifyEvidence({ id: '50', type: 'file' }, {
    getIntelligence: async () => { newsCalls++; throw new Error('新闻不存在') },
    getMaterial: async () => ({ data: { id: '50', name: '测试资料', parseStatus: 'ready', extractedText: '可用于生成的正文' } })
  })
  assert.equal(newsCalls, 0)
  assert.equal(row.ready, true)
  assert.equal(row.itemType, 'material')
})

function setup(list, retry = async () => {}) {
  const store = reactive({ workspaceEpoch: 1, basket: [{ id: '49', type: 'file' }], liveDocuments: [{ id: '49', parseStatus: 'queued' }] })
  const timers = new Map()
  let serial = 0
  const scope = effectScope()
  const state = scope.run(() => useBasketParsing(store, () => true, { list, retry }, {
    setTimeout: fn => { const id = ++serial; timers.set(id, fn); return id },
    clearTimeout: id => timers.delete(id)
  }))
  async function tick() {
    const [id, fn] = timers.entries().next().value
    timers.delete(id)
    await fn()
    await nextTick()
  }
  return { store, state, timers, scope, tick }
}

test('basket automatically refreshes pending status and stops once ready', async () => {
  const env = setup(async () => ({ data: { rows: [{ id: '49', parseStatus: 'ready' }] } }))
  try {
    assert.equal(env.state.label('49'), '解析中')
    assert.equal(env.timers.size, 1)
    await env.tick()
    assert.equal(env.state.label('49'), '已解析，可用于生成')
    assert.equal(env.timers.size, 0)
  } finally { env.scope.stop() }
})

test('failed material supports retry and resumes automatic refresh', async () => {
  let retried
  const env = setup(async () => ({ data: { rows: [{ id: '49', parseStatus: 'queued' }] } }), async id => { retried = id })
  try {
    env.store.liveDocuments = [{ id: '49', parseStatus: 'failed' }]
    await nextTick()
    assert.equal(env.state.label('49'), '解析失败')
    await env.state.retry('49')
    assert.equal(retried, '49')
    assert.equal(env.state.label('49'), '解析中')
    assert.equal(env.timers.size, 1)
  } finally { env.scope.stop() }
})

test('late poll response cannot update another session; disposal clears timer', async () => {
  let resolve
  const env = setup(() => new Promise(done => { resolve = done }))
  const pending = env.tick()
  env.store.workspaceEpoch++
  env.store.liveDocuments = []
  resolve({ data: { rows: [{ id: '49', parseStatus: 'ready' }] } })
  await pending
  assert.deepEqual(env.store.liveDocuments, [])
  env.scope.stop()
  assert.equal(env.timers.size, 0)
})

test('temporary polling failure remains visible and retries without losing data', async () => {
  const env = setup(async () => { throw new Error('offline') })
  try {
    await env.tick()
    assert.match(env.state.error.value, /自动重试/)
    assert.equal(env.store.liveDocuments[0].parseStatus, 'queued')
    assert.equal(env.timers.size, 1)
  } finally { env.scope.stop() }
})
