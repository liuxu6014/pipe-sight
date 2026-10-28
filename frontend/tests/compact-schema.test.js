import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import * as businessIds from '../src/utils/portal/businessId.js'
import * as vue from 'vue'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import * as contract from '../src/utils/pipeline/compactContract.js'
import * as sourceAdapters from '../src/utils/pipeline/sourceAdapters.js'

const read = path => readFileSync(new URL('../src/' + path, import.meta.url), 'utf8')
function page(path, dependencies, exports) {
  const scope = vue.effectScope(), timers = new Map(), messages = []
  let sequence = 0, leave = () => {}
  const context = vm.createContext({
    ...vue, ...contract, ...sourceAdapters, defineOptions() {}, onMounted() {}, onBeforeUnmount(fn) { leave = fn },
    checkPermi: () => true, checkRole: () => true,
    setTimeout(fn) { timers.set(++sequence, fn); return sequence }, clearTimeout(id) { timers.delete(id) },
    ElMessage: Object.fromEntries(['success', 'info', 'warning', 'error'].map(level => [level, text => messages.push({ level, text })])),
    ...dependencies
  })
  const script = parse(read(path)).descriptor.scriptSetup.content.replace(/^import .*\n/gm, '')
  scope.run(() => vm.runInContext(script + '\nglobalThis.page = { ' + exports + ' }', context))
  return { ...context.page, messages, timers, close() { leave(); scope.stop() }, async tick() {
    const [id, fn] = timers.entries().next().value || []
    assert.ok(fn, 'expected a scheduled refresh'); timers.delete(id); await fn()
  } }
}

test('image input never enables image generation and disabled models are not selectable', () => {
  const models = [
    { modelId: 1, status: '0', capabilities: ['text_generate', 'image_input'] },
    { modelId: 2, status: '0', capabilities: ['image_generate'] },
    { modelId: 3, status: '1', capabilities: ['image_generate'] },
    { modelId: 4, status: '0', supportImages: 'Y' }
  ]
  assert.deepEqual(contract.modelsFor(models, 'image_generate').map(row => row.modelId), [2])
  assert.deepEqual(contract.modelsFor(models, 'text_generate').map(row => row.modelId), [1])
})

test('category payload defaults are disabled and enabling without a model is explicitly rejected', () => {
  assert.deepEqual(contract.categoryPayload({ name: ' 类别 ', prompt: ' 依据摘要分类 ' }), {
    name: '类别', prompt: '依据摘要分类', modelId: null, appliesTo: 'all', sortOrder: 0, isEnabled: false
  })
  assert.throws(() => contract.categoryPayload({ name: '类别', prompt: '提示词', isEnabled: true }), /请选择文本生成模型/)
  assert.equal(contract.categoryPayload({ name: '类别', prompt: '提示词', modelId: 1, isEnabled: true }).isEnabled, true)
})

test('template generation requires configured text and requested image capabilities', () => {
  assert.match(contract.templateGenerationError({ modelId: null }), /文本生成模型/)
  assert.match(contract.templateGenerationError({ modelId: 1, modelConfigured: false }), /文本生成模型/)
  assert.equal(contract.templateGenerationError({ modelId: 1, modelConfigured: true }), '')
  assert.match(contract.templateGenerationError({ modelId: 1, imageConfig: { enabled: true } }), /图片生成模型/)
  assert.equal(contract.templateGenerationError({ modelId: 1, imageModelId: 2, imageModelConfigured: true, imageConfig: { enabled: true } }), '')
})

test('stop acknowledgements distinguish process exit from a pending stop and terminal races', () => {
  assert.match(contract.stopResultMessage({ status: 'stopping' }), /等待采集进程确认退出/)
  assert.equal(contract.stopResultMessage({ status: 'cancelled' }), '本次采集已取消')
  assert.equal(contract.stopResultMessage({ status: 'success' }), '当前运行状态：成功')
})

test('API wrappers use confirmed paths, canonical payloads and idempotency keys without any network', async () => {
  const calls = []
  const context = vm.createContext({ ...businessIds, request: options => { calls.push(options); return Promise.resolve({}) }, crypto: { randomUUID: () => 'test-key' } })
  for (const path of ['api/pipeline/intelligence.js', 'api/pipeline/categories.js']) {
    vm.runInContext(read(path).replace(/^import .*\n/gm, '').replace(/export /g, ''), context)
  }
  await vm.runInContext("createPipelineCategory({ name: '类别', prompt: '提示词', modelId: null, isEnabled: false, appliesTo: 'all', sortOrder: 0 })", context)
  assert.equal(calls.at(-1).url, '/pipeline/categories')
  assert.equal(calls.at(-1).data.isEnabled, false)
  await vm.runInContext("updatePipelineCategory('51', { isEnabled: false })", context)
  assert.equal(calls.at(-1).url, '/pipeline/categories/51')
  await vm.runInContext("deletePipelineCategory('52')", context)
  assert.equal(calls.at(-1).method, 'delete')
  await vm.runInContext("runPipelineTask('53')", context)
  assert.equal(calls.at(-1).url, '/pipeline/tasks/53/run')
  assert.equal(calls.at(-1).data.requestId, 'manual:test-key')
  await vm.runInContext("retryPipelineTask('54', 'retry-key')", context)
  assert.equal(calls.at(-1).url, '/pipeline/tasks/runs/54/retry')
  assert.equal(calls.at(-1).data.requestId, 'retry-key')
  await vm.runInContext("stopPipelineCollectionRun('55')", context)
  assert.equal(calls.at(-1).url, '/pipeline/tasks/runs/55/stop')
  await vm.runInContext('listPipelineReports()', context)
  assert.equal(calls.at(-1).url, '/pipeline/research/reports')
  await vm.runInContext("exportPipelineReport('56', { format: 'markdown' })", context)
  assert.equal(calls.at(-1).url, '/pipeline/research/reports/56/export')
})

test('collection refreshes running and stopping to cancelled, preserves errors, and clears timers on exit', async () => {
  let status = 'running', fail = false, stops = 0
  const h = page('views/pipeline/task/index.vue', {
    listPipelineTasks: async () => { if (fail) throw new Error('刷新失败'); return { data: { rows: [{ id: 'source', latestRunId: 'run', isEnabled: true, status }] } } },
    stopPipelineCollectionRun: async id => { assert.equal(id, 'run'); stops++; status = 'stopping'; return { data: { status } } }
  }, 'rows, taskError, loadTasks, handleStop, handleRetry, handleRunTask')
  try {
    await h.loadTasks(); assert.equal(h.timers.size, 1)
    await h.handleStop(h.rows.value[0]); assert.equal(stops, 1)
    assert.ok(h.messages.some(item => item.text.includes('等待采集进程确认退出')))
    fail = true; await h.tick()
    assert.equal(h.taskError.value, '刷新失败'); assert.equal(h.rows.value[0].status, 'stopping')
    fail = false; status = 'cancelled'; await h.tick()
    assert.equal(h.taskError.value, ''); assert.equal(h.rows.value[0].status, 'cancelled'); assert.equal(h.timers.size, 0)
    await h.handleRetry(h.rows.value[0]) // cancelled is not a failed retry candidate
    await h.handleRunTask({ id: 'source', isEnabled: false, status: 'waiting' })
  } finally { h.close() }
  assert.equal(h.timers.size, 0)
})

test('failed retry calls the failed run and refreshes to the returned new active run', async () => {
  let retried = false
  const h = page('views/pipeline/task/index.vue', {
    retryPipelineTask: async id => { assert.equal(id, 'failed-run'); retried = true; return { data: { id: 'child', parentId: id, status: 'queued' } } },
    listPipelineTasks: async () => ({ data: { rows: [{ id: 'source', isEnabled: true, latestRunId: 'child', status: 'queued' }] } })
  }, 'rows, handleRetry')
  try {
    await h.handleRetry({ id: 'source', isEnabled: true, latestRunId: 'failed-run', status: 'failed' })
    assert.equal(retried, true); assert.equal(h.rows.value[0].latestRunId, 'child'); assert.equal(h.timers.size, 1)
  } finally { h.close() }
})

test('leaving collection page during a delayed refresh cannot restart polling', async () => {
  let resolve
  const h = page('views/pipeline/task/index.vue', { listPipelineTasks: () => new Promise(yes => { resolve = yes }) }, 'loadTasks, rows')
  const pending = h.loadTasks(); h.close()
  resolve({ data: { rows: [{ status: 'running' }] } }); await pending
  assert.equal(h.rows.value.length, 0); assert.equal(h.timers.size, 0)
})

test('template saves canonical configuration with NULL models and never invokes publication', async () => {
  let saved
  const h = page('views/pipeline/template/index.vue', {
    Files: {}, Document: {}, Calendar: {}, Collection: {},
    createPipelineTemplate: async payload => { saved = payload }, listPipelineTemplates: async () => ({ data: { rows: [] } })
  }, 'form, saveTemplate')
  try {
    Object.assign(h.form, { name: '模板', prompt: '依据资料生成', modelId: null, imageModelId: null })
    await h.saveTemplate()
    assert.deepEqual(Object.keys(saved).sort(), ['name','purpose','prompt','description','modelId','imageModelId','sections','imageConfig','isEnabled'].sort())
    assert.equal(saved.modelId, null); assert.equal(saved.isEnabled, true)
  } finally { h.close() }
})

test('category UI rejects invalid enabling before making an API request and allows a disabled save', async () => {
  let calls = 0
  const h = page('views/pipeline/model/index.vue', {
    getCurrentInstance: () => ({ proxy: { useDict: () => ({ ai_provider_type: [] }) } }),
    createPipelineCategory: async data => { calls++; assert.equal(data.isEnabled, false); assert.equal(data.modelId, null) },
    listPipelineCategories: async () => ({ data: { rows: [] } })
  }, 'categoryForm, saveCategory')
  try {
    Object.assign(h.categoryForm, { name: '类别', prompt: '提示词', isEnabled: true })
    await h.saveCategory(); assert.equal(calls, 0)
    assert.ok(h.messages.some(item => item.text.includes('请选择文本生成模型')))
    h.categoryForm.isEnabled = false; await h.saveCategory(); assert.equal(calls, 1)
  } finally { h.close() }
})

test('source configuration preserves disabled state and failed toggles never invert the current switch', async () => {
  const writes = []
  let fail = false
  const h = page('views/pipeline/source/index.vue', {
    listPipelineSources: async () => ({ data: { rows: [] } }),
    updatePipelineSource: async (id, payload) => { if (fail) throw new Error('保存失败'); writes.push({ id, payload }) },
    disablePipelineSource: async () => { throw new Error('停用失败') }
  }, 'resetForm, sourceForm, sourcePayload, saveSource, toggleSource')
  try {
    h.resetForm({ id: 's', name: '来源', type: 'website', adapter: 'pipechina_group_news', config: { timeout: 30 }, isEnabled: false })
    h.sourceForm.name = '更新来源'
    const data = h.sourcePayload()
    assert.equal(data.isEnabled, false); assert.equal(data.config.timeout, 30)
    assert.equal(data.timezone, 'Asia/Shanghai'); assert.equal(data.type, 'website')
    assert.equal('sourceCode' in data, false); assert.equal('handoffMode' in data, false)
    await h.saveSource(); assert.equal(writes[0].payload.isEnabled, false)
    const source = { id: 's', name: '来源', type: 'website', adapter: 'pipechina_group_news', isEnabled: true }
    await h.toggleSource(source); assert.equal(source.isEnabled, true)
    assert.ok(h.messages.some(item => item.text === '停用失败'))
    fail = true; source.isEnabled = false; await h.toggleSource(source)
    assert.equal(source.isEnabled, false)
  } finally { h.close() }
})

test('all changed business pages compile their scripts and templates', () => {
  for (const path of ['pipeline/task/index','pipeline/source/index','pipeline/model/index','pipeline/template/index','pipeline/intelligence/index','pipeline/intelligence/detail','pipeline/dashboard/index','portal/pages/PaperDetailView','portal/pages/PaperListView','portal/pages/ResearchCreateView','portal/pages/DigestCreateView']) {
    const { descriptor } = parse(read('views/' + path + '.vue'))
    const script = compileScript(descriptor, { id: path })
    const result = compileTemplate({ source: descriptor.template.content, filename: path, id: path, compilerOptions: { bindingMetadata: script.bindings } })
    assert.deepEqual(result.errors, [], path)
  }
})

test('model provider options match supported protocols and use compatible for other endpoints', () => {
  const source = read('views/pipeline/model/index.vue')
  const options = [...source.matchAll(/value: '(openai|openai-compatible|compatible|deepseek)'/g)].map(match => match[1])
  assert.deepEqual(options, ['openai', 'openai-compatible', 'compatible', 'deepseek'])
  assert.doesNotMatch(source, /ai_provider_type/)
  assert.ok(source.includes('其他服务商请选 compatible'))
})
