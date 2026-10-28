import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { ref, reactive, computed, toRefs } from 'vue'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { getDefaultLoginPath } from '../src/utils/portal/auth.js'

const read = path => fs.readFileSync(new URL(`../src/views/${path}.vue`, import.meta.url), 'utf8')
const tick = () => new Promise(resolve => setImmediate(resolve))
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }

// Execute the actual SFC setup with injected APIs only: no HTTP, import or Redis writes.
function setup(path, overrides = {}) {
  const { descriptor } = parse(read(path))
  const script = compileScript(descriptor, { id: 'system-ui-test' })
  assert.deepEqual(compileTemplate({ id: 'system-ui-test', source: descriptor.template.content, compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
  const hooks = [], mounted = [], activated = [], deactivated = [], errors = [], listeners = new Set(), charts = []
  let closes = 0
  const proxy = { $modal: { loading() {}, closeLoading() { closes++ }, msgError: message => errors.push(message), msgSuccess() {}, confirm: () => Promise.resolve() }, useDict: () => ({}), $refs: {}, ...overrides.proxy }
  const env = {
    ref, reactive, computed, toRefs, getCurrentInstance: () => ({ proxy }),
    onBeforeUnmount: fn => hooks.push(fn), onUnmounted: fn => hooks.push(fn),
    onDeactivated: fn => deactivated.push(fn), onActivated: fn => activated.push(fn),
    onMounted: fn => mounted.push(fn), nextTick: () => Promise.resolve(),
    ElLoading: { service: () => ({ close() { closes++ } }) },
    window: { innerHeight: 900, addEventListener: (name, fn) => listeners.add(fn), removeEventListener: (name, fn) => listeners.delete(fn) },
    echarts: { init() { const chart = { disposed: false, setOption() {}, resize() {}, dispose() { this.disposed = true } }; charts.push(chart); return chart } },
    getServer: () => Promise.resolve({ data: {} }), getCache: () => Promise.resolve({ data: { info: { used_memory_human: '1M' }, commandStats: [] } }),
    listCacheName: () => Promise.resolve({ data: [] }), getToken: () => 'test', useRouter: () => ({}), useAppStore: () => ({}),
    useUserStore: () => ({ roles: [], permissions: [] }), getDefaultLoginPath,
    ...overrides,
  }
  const code = script.content.replace(/^import[\s\S]*?from\s*['"][^'"]+['"];?\s*$/gm, '').replace(/^import\s*['"][^'"]+['"];?\s*$/gm, '').replaceAll('import.meta.env.VITE_APP_BASE_API', '"/test-api"').replace('export default', 'return')
  const component = new Function(...Object.keys(env), code)(...Object.values(env))
  const state = component.setup({}, { expose() {} })
  return { state, hooks, mounted, activated, deactivated, errors, listeners, charts, get closes() { return closes } }
}

for (const path of ['monitor/server/index', 'monitor/cache/index']) {
  test(`${path}: rejected request unlocks and retry succeeds`, async () => {
    let attempts = 0
    const api = () => ++attempts === 1 ? Promise.reject(new Error('offline')) : Promise.resolve({ data: { info: { used_memory_human: '1M' }, commandStats: [] } })
    const h = setup(path, { getServer: api, getCache: api })
    h.mounted.forEach(fn => fn())
    await tick()
    assert.equal(h.closes, 1)
    assert.ok(h.state.loadError.value)
    await h.state.getList()
    assert.equal(h.closes, 2)
    assert.equal(h.state.loadError.value, '')
    assert.match(read(path), /@click="getList"/)
  })
  test(`${path}: leaving during request closes lock and ignores late response`, async () => {
    const pending = deferred()
    const h = setup(path, { getServer: () => pending.promise, getCache: () => pending.promise })
    h.mounted.forEach(fn => fn())
    h.hooks.forEach(fn => fn())
    assert.equal(h.closes, 1)
    pending.resolve({ data: { info: { used_memory_human: '1M' }, commandStats: [] } })
    await tick()
    assert.equal(h.charts.length, 0)
    assert.equal(h.closes, 1)
  })
  test(`${path}: cached tab departure cleans up; old request cannot unlock reactivated tab`, async () => {
    const old = deferred(), current = deferred()
    let calls = 0
    const api = () => ++calls === 1 ? old.promise : current.promise
    const h = setup(path, { getServer: api, getCache: api })
    h.mounted.forEach(fn => fn())
    h.deactivated.forEach(fn => fn())
    assert.equal(h.closes, 1)
    h.activated.forEach(fn => fn())
    old.reject(new Error('old failure'))
    await tick()
    assert.equal(h.closes, 1)
    assert.equal(h.state.loadError.value, '')
    current.resolve({ data: { info: { used_memory_human: '1M' }, commandStats: [] } })
    await tick()
    assert.equal(h.closes, 2)
    assert.equal(calls, 2)
  })
}

test('cache charts release resize listener and instances when leaving', async () => {
  const h = setup('monitor/cache/index')
  h.mounted.forEach(fn => fn())
  await tick()
  assert.equal(h.charts.length, 2)
  h.hooks.forEach(fn => fn())
  assert.equal(h.listeners.size, 0)
  assert.ok(h.charts.every(chart => chart.disposed))
})

test('clear all waits for explicit confirmation, cancel makes no call, failures are visible', async () => {
  const confirmation = deferred(), errors = []
  let calls = 0, warning = ''
  const h = setup('monitor/cache/list', { clearCacheAll: async () => { calls++ }, proxy: { $modal: { confirm: text => { warning = text; return confirmation.promise }, msgSuccess() {}, msgError: text => errors.push(text) } } })
  const result = h.state.handleClearCacheAll()
  assert.equal(calls, 0)
  assert.match(warning, /当前\s*Redis\s*库.*全部缓存/)
  assert.match(warning, /登录.*失效/)
  confirmation.reject('cancel')
  await result
  assert.equal(calls, 0)
  // Use another instance to verify confirmation and request failure.
  const accepted = setup('monitor/cache/list', { clearCacheAll: async () => { calls++; throw new Error('offline') }, proxy: { $modal: { confirm: async () => {}, msgSuccess() {}, msgError: text => errors.push(text) } } })
  await accepted.state.handleClearCacheAll()
  assert.equal(calls, 1)
  assert.equal(errors.length, 1)
})

test('upload network/business failure, close and reopening reset state; no automatic resubmit', async () => {
  let cleared = 0, aborted = 0, submitted = 0
  const h = setup('system/user/index', { proxy: { $refs: { uploadRef: { clearFiles() { cleared++ }, abort() { aborted++ }, submit() { submitted++; throw new Error('submit failed') } } } } })
  const s = h.state
  s.handleImport()
  s.handleFileChange({ name: 'users.xlsx' })
  s.handleFileUploadProgress()
  s.handleFileError(new Error('offline'))
  assert.equal(s.upload.isUploading, false)
  assert.equal(s.upload.selectedFile, null)
  assert.ok(h.errors.length)
  s.handleFileSuccess({ code: 500, msg: '导入失败' }, {})
  assert.equal(s.upload.open, true)
  s.handleFileUploadProgress()
  s.resetUpload()
  assert.equal(s.upload.isUploading, false)
  s.upload.isUploading = true
  s.upload.updateSupport = true
  s.handleImport()
  assert.equal(s.upload.isUploading, false)
  assert.equal(s.upload.updateSupport, false)
  s.handleFileChange({ name: 'users.xlsx' })
  s.submitFileForm()
  assert.equal(s.upload.isUploading, false)
  assert.equal(submitted, 1)
  assert.ok(cleared && aborted)
  assert.match(read('system/user/index'), /:on-error="handleFileError"/)
  assert.match(read('system/user/index'), /@close="resetUpload"/)
})

test('404 uses existing role landing resolver and data monitor explains unavailability', () => {
  for (const [roles, expected] of [[[], '/portal'], [['admin'], '/pipeline/dashboard']]) {
    const h = setup('error/404', { useUserStore: () => ({ roles }) })
    assert.equal(h.state.homePath.value, expected)
  }
  assert.match(read('error/404'), /:to="homePath"/)
  const source = read('monitor/druid/index')
  assert.match(source, /暂不可用/)
  assert.match(source, /管理员/)
  assert.doesNotMatch(source, /iframe|i-frame|我是数据监控/i)
})
