import test from 'node:test'
import assert from 'node:assert/strict'
import { setTimeout as delay, setImmediate } from 'node:timers/promises'
import { computed, createRenderer, h, nextTick, reactive, ref } from 'vue'
import { usePagedResults } from '../src/utils/portal/usePagedResults.js'

const deferred = () => {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const response = (rows, total = rows.length) => ({ data: { rows, total } })
const settle = async () => { await nextTick(); await setImmediate(); await nextTick() }

// Real Vue lifecycle, with controlled network ordering and no DOM dependency.
function mount(load, options = {}) {
  const query = reactive({ keyword: '', status: 'all', sort: 'updated_desc', pageSize: 10 })
  const page = ref(options.page || 1), epoch = ref(0), enabled = ref(options.enabled ?? true)
  const params = computed(() => ({ ...query, pageNum: page.value }))
  const node = type => ({ type, children: [], parent: null })
  const renderer = createRenderer({
    createElement: node, createText: node, createComment: node,
    setText() {}, setElementText() {}, patchProp() {}, nextSibling: () => null,
    parentNode: child => child.parent,
    insert(child, parent) { child.parent = parent; parent.children.push(child) },
    remove(child) { if (child.parent) child.parent.children = child.parent.children.filter(item => item !== child) }
  })
  let state
  const app = renderer.createApp({
    setup() { state = usePagedResults(load, params, epoch, page, enabled); return () => h('div') }
  })
  app.mount(node('root'))
  return { state, query, page, epoch, enabled, close: () => app.unmount() }
}

test('server pages receive filters, sort and page size; keyword requests debounce', async () => {
  const calls = []
  const ctx = mount(async params => {
    calls.push({ ...params })
    return response([{ id: `${params.status}:${params.pageNum}` }], 45)
  })
  try {
    await settle()
    assert.deepEqual(calls, [{ keyword: '', status: 'all', sort: 'updated_desc', pageSize: 10, pageNum: 1 }])
    ctx.page.value = 2
    await settle()
    assert.deepEqual(ctx.state.rows.value, [{ id: 'all:2' }])
    ctx.query.status = 'completed'
    await settle()
    assert.equal(calls.at(-1).status, 'completed')
    ctx.query.sort = 'name_asc'
    ctx.query.pageSize = 20
    await settle()
    assert.equal(calls.at(-1).sort, 'name_asc')
    assert.equal(calls.at(-1).pageSize, 20)
    const previous = calls.length
    ctx.query.keyword = '管'
    ctx.query.keyword = '管道'
    assert.deepEqual(ctx.state.rows.value, [])
    assert.equal(ctx.state.total.value, 0)
    assert.equal(calls.length, previous)
    await delay(210)
    await settle()
    assert.equal(calls.length, previous + 1)
    assert.equal(calls.at(-1).keyword, '管道')
    assert.equal(ctx.state.total.value, 45)
  } finally { ctx.close() }
})

test('older response cannot overwrite a newer page or finish its loading state', async () => {
  const requests = []
  const ctx = mount(params => {
    const pending = deferred(); requests.push({ ...pending, params }); return pending.promise
  })
  try {
    ctx.page.value = 2
    assert.equal(requests.length, 2)
    requests[0].resolve(response([{ id: 'old-page' }], 80))
    await settle()
    assert.deepEqual(ctx.state.rows.value, [])
    assert.equal(ctx.state.loading.value, true)
    requests[1].resolve(response([{ id: 'page-two' }], 35))
    await settle()
    assert.deepEqual(ctx.state.rows.value, [{ id: 'page-two' }])
    assert.equal(ctx.state.total.value, 35)
    assert.equal(ctx.state.loading.value, false)
  } finally { ctx.close() }
})

test('account epoch immediately removes private rows and fences old account responses', async () => {
  const requests = []
  const ctx = mount(() => { const pending = deferred(); requests.push(pending); return pending.promise })
  try {
    requests[0].resolve(response([{ id: 'account-a' }], 12))
    await settle()
    const oldRefresh = ctx.state.refresh()
    ctx.epoch.value++
    assert.deepEqual(ctx.state.rows.value, [])
    assert.equal(ctx.state.total.value, 0)
    requests[2].resolve(response([{ id: 'account-b' }], 1))
    await settle()
    requests[1].resolve(response([{ id: 'account-a-secret' }], 99))
    await oldRefresh
    assert.deepEqual(ctx.state.rows.value, [{ id: 'account-b' }])
    assert.equal(ctx.state.total.value, 1)
  } finally { ctx.close() }
})

test('disabled automatic-task tab neither requests reports nor clamps its independent page', async () => {
  const requests = []
  const ctx = mount(params => {
    const pending = deferred(); requests.push({ ...pending, params }); return pending.promise
  }, { page: 3, enabled: false })
  try {
    await settle()
    assert.equal(requests.length, 0)
    assert.equal(ctx.page.value, 3)
    ctx.enabled.value = true
    assert.equal(requests.length, 1)
    ctx.enabled.value = false
    ctx.page.value = 4
    requests[0].resolve(response([], 0))
    await settle()
    assert.equal(ctx.page.value, 4)
    assert.equal(requests.length, 1)
    assert.deepEqual(ctx.state.rows.value, [])
    assert.equal(ctx.state.loading.value, false)
    await ctx.state.refresh()
    assert.equal(requests.length, 1)
    assert.equal(ctx.page.value, 4)
    ctx.enabled.value = true
    requests[1].resolve(response([], 11))
    await settle()
    assert.equal(ctx.page.value, 2)
    assert.equal(requests.length, 3)
    assert.equal(requests[2].params.pageNum, 2)
    requests[2].resolve(response([{ id: 'last-page' }], 11))
    await settle()
    assert.deepEqual(ctx.state.rows.value, [{ id: 'last-page' }])
  } finally { ctx.close() }
})

test('manual refresh error retains loaded rows; query change clears old results and retry recovers', async () => {
  const requests = []
  const ctx = mount(() => { const pending = deferred(); requests.push(pending); return pending.promise })
  try {
    requests[0].resolve(response([{ id: 'usable-old' }], 21))
    await settle()
    const refresh = ctx.state.refresh()
    requests[1].reject(new Error('暂时不可用'))
    await refresh
    assert.equal(ctx.state.error.value, '暂时不可用')
    assert.deepEqual(ctx.state.rows.value, [{ id: 'usable-old' }])
    assert.equal(ctx.state.total.value, 21)
    ctx.query.status = 'failed'
    assert.equal(ctx.state.error.value, '')
    assert.deepEqual(ctx.state.rows.value, [])
    assert.equal(ctx.state.total.value, 0)
    requests[2].reject({ msg: '筛选请求失败' })
    await settle()
    assert.equal(ctx.state.error.value, '筛选请求失败')
    assert.equal(ctx.state.loading.value, false)
    const retry = ctx.state.refresh()
    requests[3].resolve(response([{ id: 'filtered' }], 1))
    await retry
    assert.equal(ctx.state.error.value, '')
    assert.deepEqual(ctx.state.rows.value, [{ id: 'filtered' }])
  } finally { ctx.close() }
})

test('unmount cancels debounce and ignores an already running loader', async () => {
  let calls = 0
  const pending = deferred()
  const ctx = mount(() => { calls++; return pending.promise })
  ctx.query.keyword = '未发送'
  ctx.close()
  pending.resolve(response([{ id: 'after-unmount' }], 10))
  await delay(210)
  await settle()
  assert.equal(calls, 1)
  assert.deepEqual(ctx.state.rows.value, [])
  assert.equal(ctx.state.total.value, 0)
})
