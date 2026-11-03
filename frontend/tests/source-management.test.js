import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import * as Vue from 'vue'
import { parse, compileScript, compileTemplate, compileStyle } from '@vue/compiler-sfc'
import * as management from '../src/utils/pipeline/sourceManagement.js'
import { sourceEnabled } from '../src/utils/pipeline/compactContract.js'
import { canCreateSourceType, supportsSourceAdapter } from '../src/utils/pipeline/sourceAdapters.js'
import { buildManagementNavigation, resolveActiveNavigation } from '../src/utils/management-navigation.js'

const source = readFileSync(new URL('../src/views/pipeline/source/index.vue', import.meta.url), 'utf8')
const { sourceIntervalChoices, sourceIntervalCron, sourceFrequency, sourceFrequencyText, existingSourcePayload, newWechatSourcePayload } = management
const page = (path, extra = {}) => ({ path, component: () => {}, meta: { title: path }, ...extra })
const sample = (extra = {}) => ({
  id: '100000000000001', name: '现有来源', type: 'paper', adapter: 'crossref_works',
  url: 'https://example.com/papers', cron: '0 3 * * 1', timezone: 'UTC',
  modelId: '200000000000001', isEnabled: false,
  config: { query: 'pipeline', limit: 19, nested: { keep: true } }, ...extra
})

// Execute actual page handlers with local spies only. Never import the API client.
function harness({ rows = [], permissions = true, list, update, create, disable } = {}) {
  const calls = { list: 0, update: [], create: [], disable: [], errors: [] }
  const context = vm.createContext({
    ...Vue, ...management, sourceEnabled, defineOptions() {}, onMounted() {},
    checkPermi: keys => typeof permissions === 'function' ? permissions(keys) : permissions,
    ElMessage: { success() {}, error: message => calls.errors.push(message) },
    listPipelineSources: async () => { calls.list++; return list ? list() : { data: { rows } } },
    updatePipelineSource: async (...args) => { calls.update.push(args); return update?.(...args) },
    createPipelineSource: async data => { calls.create.push(data); return create?.(data) },
    disablePipelineSource: async id => { calls.disable.push(id); return disable?.(id) }
  })
  const script = parse(source).descriptor.scriptSetup.content.replace(/^import .*$/gm, '')
  vm.runInContext(`${script}\nglobalThis.view = { rows, sourceError, loading, dialogVisible, dialogError, saving, sourceForm, frequency, intervalChoices, frequencyPreview, editingSource, pendingSourceId, busy, activeType, sourceTypeOptions, filteredRows, openEditDialog, editDetails, sourceTable, page, pageSize, pagedRows, loadSources, openCreateDialog, openFrequencyDialog, resetIntervalAmount, saveSource, toggleSource }`, context)
  return { state: context.view, calls }
}

test('only WeChat may be created; registered adapters do not constitute a source whitelist', () => {
  for (const type of ['website', 'news', 'paper', 'unknown', undefined]) assert.equal(canCreateSourceType(type), false)
  assert.equal(canCreateSourceType('wechat'), true)
  assert.equal(supportsSourceAdapter({ type: 'wechat', adapter: 'wechat_rss' }), true)
  assert.equal(supportsSourceAdapter({ type: 'news', adapter: 'pipechina_group_news' }), true)
})

test('every offered interval round trips through the existing five-field cron contract', () => {
  for (const [unit, amounts] of Object.entries(sourceIntervalChoices)) {
    for (const amount of amounts) {
      const cron = sourceIntervalCron({ unit, amount })
      assert.equal(cron.split(' ').length, 5)
      assert.deepEqual(sourceFrequency(cron), { unit, amount })
      if (unit === 'minute' || unit === 'hour') assert.equal((unit === 'minute' ? 60 : 24) % amount, 0)
    }
  }
  assert.equal(sourceIntervalCron({ unit: 'off', amount: 1 }), null)
  assert.equal(sourceFrequencyText(null), '未设置定时采集')
  assert.equal(sourceFrequencyText('0 */6 * * *'), '每 6 小时')
  assert.equal(sourceFrequencyText('0 3 * * *'), '每天 03:00')
  assert.equal(sourceFrequencyText('0 0 * * mon'), '每周一 00:00')
})

test('uneven and invalid intervals cannot silently become misleading cron schedules', () => {
  for (const frequency of [{ unit: 'hour', amount: 7 }, { unit: 'minute', amount: 7 }, { unit: 'day', amount: 2 }, { unit: 'hour', amount: 0 }, { unit: 'hour', amount: '6' }, { unit: 'other', amount: 1 }]) {
    assert.throws(() => sourceIntervalCron(frequency), /采集间隔/)
  }
})

test('non-interval schedules survive unchanged until an explicit replacement is selected', () => {
  for (const cron of ['0 3 * * 1', '0 3 * * *', '*/7 * * * *', '0 */7 * * *', '  15  8 * * mon-fri  ']) {
    const frequency = sourceFrequency(cron)
    assert.equal(frequency.unit, 'preserve')
    assert.equal(sourceIntervalCron(frequency, cron), cron)
  }
  assert.equal(sourceIntervalCron({ unit: 'hour', amount: 4 }, '0 3 * * 1'), '0 */4 * * *')
})

test('frequency and status payloads preserve all other persisted settings and state', () => {
  const row = sample()
  const snapshot = JSON.stringify(row)
  const expected = { ...row }; delete expected.id
  assert.deepEqual(existingSourcePayload(row, { cron: '0 */6 * * *' }), { ...expected, cron: '0 */6 * * *' })
  assert.deepEqual(existingSourcePayload(row, { isEnabled: true }), { ...expected, isEnabled: true })
  assert.equal(JSON.stringify(row), snapshot)
  assert.throws(() => existingSourcePayload(row, { type: 'wechat' }), /仅允许/)
})

test('legacy source aliases preserve URLs, model IDs, adapters and disabled state', () => {
  const payload = existingSourcePayload({ name: '旧新闻', type: 'news', endpoint: 'https://example.com', adapter_key: 'legacy_adapter', schedule_cron: '0 8 * * *', model_id: 7, is_enabled: false })
  assert.equal(payload.type, 'website')
  assert.equal(payload.adapter, 'legacy_adapter')
  assert.equal(payload.modelId, 7)
  assert.equal(payload.cron, '0 8 * * *')
  assert.equal(payload.isEnabled, false)
})

test('new WeChat payload is constrained and contains no fabricated source or translation setting', () => {
  const payload = newWechatSourcePayload({ sourceType: 'wechat', name: '  测试公众号  ', feedUrl: ' http://example.com/feed/1.xml ', adapterKey: 'crossref_works', modelId: 99 }, { unit: 'hour', amount: 6 })
  assert.deepEqual(payload, { name: '测试公众号', type: 'wechat', adapter: 'wechat_rss', url: null, cron: '0 */6 * * *', timezone: 'Asia/Shanghai', config: { feed_url: 'http://example.com/feed/1.xml', limit: 12 }, modelId: null, isEnabled: true })
  for (const sourceType of ['website', 'paper', 'news']) assert.throws(() => newWechatSourcePayload({ sourceType }, { unit: 'off' }), /仅支持新增公众号/)
  for (const feedUrl of ['', 'not a URL', 'javascript:alert(1)', 'https://user:pass@example.com']) {
    assert.throws(() => newWechatSourcePayload({ sourceType: 'wechat', name: '测试', feedUrl }, { unit: 'off' }), /RSS/)
  }
})

test('page loads all existing types including unsupported adapters and normalizes news type statistics', async () => {
  const rows = [sample(), sample({ id: '2', type: 'website' }), sample({ id: '3', type: 'wechat' }), sample({ id: '4', type: 'legacy', adapter: 'external' }), sample({ id: '5', type: 'news' })]
  const { state, calls } = harness({ rows })
  await state.loadSources()
  assert.deepEqual(state.rows.value, rows)
  assert.equal(state.sourceTypeOptions.value.length, 4)
  state.activeType.value = 'website'
  assert.deepEqual(state.filteredRows.value.map(row => row.id), ['2', '5'])
  state.activeType.value = 'paper'
  assert.equal(state.filteredRows.value.length, 1)
  state.activeType.value = 'wechat'
  assert.equal(state.filteredRows.value.length, 1)
  state.activeType.value = 'all'
  assert.equal(state.filteredRows.value.length, 5)
  assert.equal(calls.list, 1)
  assert.equal(calls.create.length + calls.update.length + calls.disable.length, 0)
})

test('malformed/failed list responses show a retryable error; unauthorized pages never request data', async () => {
  for (const list of [async () => ({ data: {} }), async () => { throw new Error('列表失败') }]) {
    const { state } = harness({ list })
    await state.loadSources()
    assert.ok(state.sourceError.value)
    assert.equal(state.loading.value, false)
  }
  const { state, calls } = harness({ permissions: false })
  await state.loadSources()
  assert.match(state.sourceError.value, /权限/)
  assert.equal(calls.list, 0)
})

test('frequency action changes cron only and keeps a disabled source disabled', async () => {
  const row = sample({ type: 'wechat' })
  const { state, calls } = harness({ rows: [row] })
  state.openFrequencyDialog(row)
  assert.equal(state.frequency.unit, 'preserve')
  await state.saveSource()
  assert.equal(calls.update[0][1].cron, row.cron)
  state.openFrequencyDialog(row)
  Object.assign(state.frequency, { unit: 'hour', amount: 6 })
  await state.saveSource()
  assert.equal(calls.update[1][0], row.id)
  assert.equal(calls.update[1][1].cron, '0 */6 * * *')
  assert.equal(calls.update[1][1].isEnabled, false)
  assert.equal(calls.update[1][1].modelId, row.modelId)
  assert.equal(calls.create.length, 0)
})

test('new source dialog has no news/paper save path and rejects invalid RSS before any request', async () => {
  const { state, calls } = harness()
  state.openCreateDialog()
  assert.equal(state.sourceForm.sourceType, 'wechat')
  await state.saveSource()
  assert.ok(state.dialogError.value)
  Object.assign(state.sourceForm, { name: '测试', feedUrl: 'https://example.com/rss', sourceType: 'paper' })
  await state.saveSource()
  assert.match(state.dialogError.value, /仅支持新增公众号/)
  assert.equal(calls.create.length, 0)
  state.sourceForm.sourceType = 'wechat'
  await state.saveSource()
  assert.equal(calls.create.length, 1)
  assert.equal(calls.create[0].type, 'wechat')
  assert.equal(state.dialogVisible.value, false)
})

test('interval unit changes reset incompatible values without modifying any server data', () => {
  const { state, calls } = harness()
  Object.assign(state.frequency, { unit: 'hour', amount: 30 })
  state.resetIntervalAmount()
  assert.equal(state.frequency.amount, 1)
  assert.equal(state.frequencyPreview.value, '每 1 小时')
  assert.equal(calls.update.length, 0)
})

test('failed status changes leave rows unchanged and release pending state', async () => {
  const row = sample()
  const { state, calls } = harness({ update: async () => { throw new Error('启用失败') }, disable: async () => { throw new Error('停用失败') } })
  await state.toggleSource(row)
  assert.equal(row.isEnabled, false)
  assert.equal(calls.update[0][1].isEnabled, true)
  row.isEnabled = true
  await state.toggleSource(row)
  assert.equal(row.isEnabled, true)
  assert.equal(calls.disable[0], row.id)
  assert.equal(state.pendingSourceId.value, null)
  assert.equal(calls.errors.length, 2)
})

test('save and status actions prevent duplicate or competing requests while pending', async () => {
  let finish
  const { state, calls } = harness({ update: () => new Promise(resolve => { finish = resolve }) })
  const row = sample({ type: 'wechat' })
  state.openFrequencyDialog(row)
  const pending = state.saveSource()
  await state.saveSource()
  await state.toggleSource(row)
  state.openCreateDialog()
  assert.equal(calls.update.length, 1)
  assert.equal(state.editingSource.value.id, row.id)
  finish()
  await pending
  assert.equal(state.saving.value, false)
})

test('failed frequency saves retain the dialog and show the actual service error', async () => {
  const { state } = harness({ update: async () => { throw new Error('当前适配器不可用') } })
  state.openFrequencyDialog(sample({ type: 'wechat', adapter: 'legacy' }))
  await state.saveSource()
  assert.equal(state.dialogVisible.value, true)
  assert.equal(state.saving.value, false)
  assert.equal(state.dialogError.value, '当前适配器不可用')
})

test('read-only permission permits listing but prevents creation, frequency changes and toggling', async () => {
  const { state, calls } = harness({ permissions: keys => keys.includes('pipeline:source:list') })
  await state.loadSources()
  state.openCreateDialog()
  state.openFrequencyDialog(sample())
  await state.saveSource()
  await state.toggleSource(sample())
  assert.equal(state.dialogVisible.value, false)
  assert.equal(calls.list, 1)
  assert.equal(calls.create.length + calls.update.length + calls.disable.length, 0)
})

test('collection is one top-level source link, tasks stay available in the unmodified registration tree', () => {
  const routes = [{ path: '/pipeline', component: 'Layout', children: [page('task'), page('source', { query: '{"type":"paper"}' }), page('source')] }]
  const snapshot = JSON.stringify(routes)
  const menus = buildManagementNavigation(routes)
  assert.equal(menus.length, 1)
  assert.equal(menus[0].path, '/pipeline/source')
  assert.equal(menus[0].meta.title, '采集管理')
  assert.equal(menus[0].children, undefined)
  assert.equal(menus[0].query, undefined)
  assert.equal(resolveActiveNavigation({ path: '/pipeline/task' }, menus), '/pipeline/source')
  assert.equal(resolveActiveNavigation({ path: '/pipeline/task/detail/123' }, menus), '/pipeline/source')
  assert.equal(JSON.stringify(routes), snapshot)
  assert.equal(routes[0].children[0].path, 'task')
})

test('collection projection never invents unauthorized source links or reveals hidden parents', () => {
  assert.deepEqual(buildManagementNavigation([page('/pipeline/task')]), [])
  assert.deepEqual(buildManagementNavigation([page('/pipeline/source', { hidden: true }), page('/pipeline/task')]), [])
  assert.deepEqual(buildManagementNavigation([{ path: '/pipeline', hidden: true, children: [page('source')] }]), [])
})

test('user management navigation remains the same authorized RuoYi group', () => {
  const users = [page('/system/user'), page('/system/role')]
  const before = buildManagementNavigation(users)
  const after = buildManagementNavigation([...users, page('/pipeline/source'), page('/pipeline/task')])
  assert.deepEqual(after.find(menu => menu.meta.title === '用户管理'), before[0])
  assert.deepEqual(before[0].children.map(menu => menu.path), ['/system/user', '/system/role'])
})

test('actual source SFC compiles, exposes exactly two row actions, and uses only scoped styles', () => {
  const { descriptor, errors } = parse(source)
  assert.deepEqual(errors, [])
  const script = compileScript(descriptor, { id: 'source-management' })
  const template = compileTemplate({ source: descriptor.template.content, filename: 'PipelineSource.vue', id: 'source-management', compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(template.errors, [])
  assert.equal(descriptor.styles.length, 1)
  assert.equal(descriptor.styles[0].scoped, true)
  assert.deepEqual(compileStyle({ source: descriptor.styles[0].content, id: 'data-v-source-management', scoped: true }).errors, [])
  const actions = descriptor.template.content.match(/<div class="source-list-actions"[\s\S]*?<\/div>/)[0]
  assert.equal((actions.match(/<el-button /g) || []).length, 1)
  assert.equal((actions.match(/<el-switch /g) || []).length, 1)
  assert.match(actions, /:model-value="sourceEnabled\(row\)"/)
  assert.match(actions, /:loading="pendingSourceId === row.id"/)
  const frequencyColumn = descriptor.template.content.match(/<el-table-column label="采集频率"[\s\S]*?<\/el-table-column>/)[0]
  assert.match(frequencyColumn, /openFrequencyDialog\(row\)/)
  assert.match(frequencyColumn, /v-if="canSourceSave"/)
  assert.match(actions, /toggleSource\(row\)/)
  assert.doesNotMatch(source, /runPipelineTask|runSource|VideoPlay|listModelAll|翻译模型|调度表达式/)
  assert.doesNotMatch(descriptor.template.content, /sourceForm\.sourceType|sourceForm\.modelId/)
  assert.match(frequencyColumn, /sourceType\(row\) === 'wechat'/)
  assert.match(descriptor.template.content, /<el-table[^>]*height="100%"/)
  for (const label of ['数据源名称', '来源类型', '采集频率', '最后采集', '是否启用']) assert.ok(descriptor.template.content.includes(`label="${label}"`))
})


test('three source categories stay visible when empty; news and papers only allow status changes', async () => {
  const { state, calls } = harness()
  assert.deepEqual(Array.from(state.sourceTypeOptions.value, item => item.label), ['全部（0）', '论文（0）', '新闻网站（0）', '公众号（0）'])
  for (const type of ['paper', 'website', 'news']) {
    const row = sample({ type })
    state.openFrequencyDialog(row)
    assert.equal(state.dialogVisible.value, false)
    state.editingSource.value = row
    await state.saveSource()
    assert.match(state.dialogError.value, /仅支持启停/)
    assert.equal(calls.update.length, 0)
    state.editingSource.value = null
  }
  const row = sample({ type: 'website' })
  await state.toggleSource(row)
  assert.equal(calls.update.length, 1)
  assert.equal(calls.update[0][1].cron, row.cron)
  assert.equal(calls.update[0][1].isEnabled, true)
})


test('source pagination slices filtered results, resets filters and sizes, and clamps after reload', async () => {
  const records = Array.from({ length: 25 }, (_, index) => sample({ id: String(index + 1), type: index < 12 ? 'wechat' : 'website' }))
  const { state, calls } = harness({ rows: records })
  await state.loadSources()
  assert.equal(state.pageSize.value, 10)
  assert.equal(state.pagedRows.value.length, 10)
  let scrollTop = -1
  state.sourceTable.value = { setScrollTop: value => { scrollTop = value } }
  state.page.value = 3
  await Vue.nextTick()
  assert.equal(state.pagedRows.value.length, 5)
  assert.equal(state.pagedRows.value[0].id, '21')
  assert.equal(scrollTop, 0)
  state.activeType.value = 'wechat'
  assert.equal(state.page.value, 1)
  assert.equal(state.filteredRows.value.length, 12)
  state.page.value = 2
  assert.equal(state.pagedRows.value.length, 2)
  state.pageSize.value = 20
  assert.equal(state.page.value, 1)
  assert.equal(state.pagedRows.value.length, 12)
  state.activeType.value = 'all'
  state.page.value = 2
  state.rows.value = records.slice(0, 4)
  assert.equal(state.page.value, 1)
  assert.equal(state.pagedRows.value.length, 4)
  state.activeType.value = 'paper'
  assert.equal(state.filteredRows.value.length, 0)
  assert.equal(state.pagedRows.value.length, 0)
  assert.equal(state.page.value, 1)
  assert.equal(calls.list, 1)
  assert.equal(calls.update.length + calls.create.length + calls.disable.length, 0)
})


test('editing WeChat updates name and RSS while preserving state, schedule and unrelated configuration', async () => {
  const row = sample({ type: 'wechat', adapter: 'wechat_rss', config: { feed_url: 'https://example.com/old', limit: 19, custom: true } })
  const { state, calls } = harness({ rows: [row] })
  state.openEditDialog(row)
  assert.equal(state.editDetails.value, true)
  assert.equal(state.sourceForm.feedUrl, row.config.feed_url)
  state.sourceForm.name = '新名称'
  state.sourceForm.feedUrl = 'https://example.com/new'
  await state.saveSource()
  const [id, payload] = calls.update[0]
  assert.equal(id, row.id)
  assert.equal(payload.name, '新名称')
  assert.equal(payload.config.feed_url, 'https://example.com/new')
  assert.equal(payload.config.limit, 19)
  assert.equal(payload.config.custom, true)
  assert.equal(payload.cron, row.cron)
  assert.equal(payload.isEnabled, false)
  assert.equal(payload.modelId, row.modelId)
  assert.equal(row.config.feed_url, 'https://example.com/old')
  state.openEditDialog(row)
  state.sourceForm.feedUrl = 'invalid'
  await state.saveSource()
  assert.equal(calls.update.length, 1)
  assert.match(state.dialogError.value, /RSS/)
  const readOnly = harness({ permissions: false })
  readOnly.state.openEditDialog(row)
  assert.equal(readOnly.state.dialogVisible.value, false)
  const news = harness()
  news.state.openEditDialog(sample({ type: 'website' }))
  assert.equal(news.state.dialogVisible.value, false)
})
