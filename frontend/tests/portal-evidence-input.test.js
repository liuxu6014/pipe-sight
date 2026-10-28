import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { setImmediate } from 'node:timers/promises'
import * as vue from 'vue'
import { createMemoryHistory, createRouter, useRoute, useRouter } from 'vue-router'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { templateGenerationError } from '../src/utils/pipeline/compactContract.js'
import * as businessTimes from '../src/utils/portal/businessTime.js'
import * as businessIds from '../src/utils/portal/businessId.js'
import * as evidence from '../src/utils/portal/evidenceInput.js'
import { resolveBasketSelection } from '../src/utils/portal/basketSelection.js'

const names = ['ResearchCreateView', 'DigestCreateView']
const sources = Object.fromEntries(names.map(name => [name, readFileSync(new URL(`../src/views/portal/pages/${name}.vue`, import.meta.url), 'utf8')]))
const later = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const settle = async () => { for (let i = 0; i < 4; i++) { await vue.nextTick(); await setImmediate() } }
const article = (id, overrides = {}) => ({ id, title: `真实资讯 ${id}`, category: 'news', status: 'approved', summary: '真实摘要', content: '真实正文', source_type: 'news', source: '实际来源', publish_time: '2026-10-13 12:00:00', ...overrides })
const material = (id, overrides = {}) => ({ id, name: `资料 ${id}`, status: '已解析', parseStatus: 'indexed', scanStatus: 'clean', allowAiUse: true, parsedText: '实际解析正文', ...overrides })

// Execute the actual SFC setup/lifecycle with Vue and a memory router. All APIs
// are injected. Generation, scheduling and upload throw if accidentally called.
async function mount(name, { query = {}, api = {}, basket = [], timers = {} } = {}) {
  const messages = []
  const store = vue.reactive({ workspaceEpoch: 0, basket, newsItems: [], paperItems: [], knowledgeDocuments: [], hydrate: async () => {} })
  let mutations = 0
  const forbidden = () => { mutations++; throw new Error('This test must never generate, upload or schedule') }
  const dependencies = {
    ...vue, useRoute, useRouter, ...businessIds, ...businessTimes, ...evidence, templateGenerationError, resolveBasketSelection,
    usePortalStore: () => store, PortalPageHeader: {}, PortalEmptyState: {}, DigestScheduleDialog: {},
    ElMessage: Object.fromEntries(['success', 'warning', 'error'].map(level => [level, text => messages.push({ level, text })])),
    ...Object.fromEntries(['ArrowLeft', 'Check', 'Close', 'Delete', 'Plus', 'Rank', 'Search', 'UploadFilled', 'Refresh', 'Warning'].map(icon => [icon, {}])),
    getPipelineIntelligenceDetail: async id => ({ data: article(id) }),
    getPipelineKnowledgeDocument: async id => ({ data: material(id) }),
    getPipelineResearchJob: async () => ({ data: {} }),
    getPipelineContentFilters: async () => ({ data: { articleCategories: ['后台类别'] } }),
    searchPipelineIntelligence: async () => ({ data: { rows: [], total: 0 } }),
    searchPipelineDigestCandidates: params => (api.searchPipelineIntelligence || (async () => ({ data: { rows: [], total: 0 } })))(params),
    searchPipelineResearchMaterials: async () => ({ data: { rows: [], total: 0 } }),
    listPipelineTemplates: async () => ({ data: { rows: [{ templateKey: '100', modelId: 1, modelConfigured: true, name: '已发布模板', reportType: name === 'DigestCreateView' ? 'daily' : 'research-demand', digestCadence: name === 'DigestCreateView' ? 'daily' : null, version: 'V4', sections: [{ id: 1, title: '实际章节', words: 1000 }] }] } }),
    createPipelineResearchJob: forbidden, createPipelineDigestSchedule: forbidden, uploadPipelineKnowledgeDocument: forbidden, reparsePipelineKnowledgeDocument: forbidden,
    ...api, ...timers
  }
  const { descriptor } = parse(sources[name])
  const script = compileScript(descriptor, { id: name }).content.replace(/^import[\s\S]*?from ['"][^'"]+['"];?\n?/gm, '').replace('export default', 'return')
  const entries = Object.entries(dependencies).filter(([key]) => key !== 'module.exports' && key !== 'default')
  const component = new Function(...entries.map(([key]) => key), script)(...entries.map(([, value]) => value))
  let page
  const setup = component.setup
  component.setup = (props, ctx) => { page = setup(props, ctx); return page }
  component.render = () => vue.h('div')
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/create', component }, { path: '/:rest(.*)*', component: { render: () => null } }] })
  const node = type => ({ type, children: [], parent: null })
  const renderer = vue.createRenderer({
    createElement: node, createText: node, createComment: node,
    setText() {}, setElementText() {}, patchProp() {}, nextSibling: () => null, parentNode: child => child.parent,
    insert(child, parent) { child.parent = parent; parent.children.push(child) },
    remove(child) { if (child.parent) child.parent.children = child.parent.children.filter(item => item !== child) }
  })
  const app = renderer.createApp({ render: () => vue.h(vue.resolveComponent('RouterView')) }).use(router)
  await router.push({ path: '/create', query })
  app.mount(node('root'))
  await settle()
  return { get page() { return page }, store, router, messages, get mutations() { return mutations }, close: () => app.unmount() }
}

test('digest starts unfiltered and uses administrator category labels', async () => {
  const calls = []
  const ctx = await mount('DigestCreateView', { api: { searchPipelineDigestCandidates: async params => { calls.push(params); return { data: { rows: [], total: 0 } } } } })
  try {
    assert.deepEqual(ctx.page.form.keywords, [])
    assert.deepEqual(ctx.page.form.directions, [])
    assert.deepEqual(ctx.page.categoryOptions.value, ['后台类别'])
    assert.deepEqual(calls[0].keywords, [])
    ctx.page.updateKeywords([' 管道 ', '不存在', '管道', ' '])
    await settle()
    assert.deepEqual(calls.at(-1).keywords, ['管道', '不存在'])
    assert.deepEqual(ctx.page.form.keywords, ['管道', '不存在'])
    ctx.page.updateKeywords(undefined)
    await settle()
    assert.deepEqual(calls.at(-1).keywords, [])
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('digest writing outline follows the selected template instead of invented category columns', async () => {
  const ctx = await mount('DigestCreateView', { api: {
    listPipelineTemplates: async () => ({ data: { rows: [{ id: '100', name: '日报', digestCadence: 'daily', modelId: 1, modelConfigured: true,
      sections: [{ title: '行业进展', words: 500, required: true }, { title: '业务影响', words: 400, required: true },
        { title: '热点研判', words: 300, required: false }, { title: '来源清单', words: 100, required: true }] }] } })
  } })
  try {
    ctx.page.form.directions = ['后台类别']
    ctx.page.form.hotAnalysis = false
    await settle()
    assert.deepEqual(ctx.page.columnSuggestions.value, ['行业进展', '业务影响'])
    ctx.page.form.hotAnalysis = true
    await settle()
    assert.deepEqual(ctx.page.columnSuggestions.value, ['行业进展', '业务影响', '热点研判'])
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('NULL model templates stay selectable and research submission makes no generation request', async () => {
  const ctx = await mount('ResearchCreateView', { api: {
    listPipelineTemplates: async () => ({ data: { rows: [{ id: '101', name: '待配置模板', purpose: 'research', modelId: null, modelConfigured: false, sections: [] }] } })
  } })
  try {
    assert.equal(ctx.page.selectedTemplate.value.id, '101')
    assert.equal(ctx.page.nextStepBlocked.value, false)
    await ctx.page.submitTask()
    assert.equal(ctx.mutations, 0)
    assert.ok(ctx.messages.some(item => item.text.includes('未配置可用的文本生成模型')))
  } finally { ctx.close() }
})

test('one canonical digest template is selectable for daily weekly monthly and missing models prevent enqueue and schedule', async () => {
  const ctx = await mount('DigestCreateView', { api: {
    listPipelineTemplates: async () => ({ data: { rows: [{ id: '503', name: '简报模板', purpose: 'digest', reportType: 'digest', digestCadence: 'all', modelId: null, modelConfigured: false }] } })
  } })
  try {
    for (const type of ['日报', '周报', '月报']) {
      ctx.page.form.type = type; await settle()
      assert.equal(ctx.page.availableTemplates.value[0].value, '503')
      assert.equal(ctx.page.form.template, '503')
    }
    ctx.page.form.type = '日报'; await settle()
    ctx.page.form.schedule = true
    ctx.page.selectedCandidateIds.value = ['504']
    await ctx.page.createDigest()
    assert.equal(ctx.mutations, 0)
    assert.ok(ctx.messages.some(item => item.text.includes('未配置可用的文本生成模型')))
  } finally { ctx.close() }
})

test('research upload dialog closes after success and adds the returned material to selection', async () => {
  const pending = later()
  const ctx = await mount('ResearchCreateView', { api: { uploadPipelineKnowledgeDocument: async data => {
    assert.equal(data.get('category'), '内部资料')
    assert.equal(data.get('permissionScope'), 'private')
    return pending.promise
  } } })
  try {
    ctx.page.activeStep.value = 1
    ctx.page.uploadDialogVisible.value = true
    const file = new Blob(['test material'], { type: 'text/plain' })
    Object.defineProperty(file, 'name', { value: 'material.txt' })
    const input = { files: [file], value: 'material.txt' }
    const upload = ctx.page.uploadResearchMaterial({ target: input })
    assert.equal(ctx.page.uploading.value, true)
    assert.equal(ctx.page.nextStepBlocked.value, true)
    pending.resolve({ data: { id: '102' } })
    await upload
    await settle()
    assert.equal(ctx.page.uploadDialogVisible.value, false)
    assert.equal(ctx.page.uploading.value, false)
    assert.ok(ctx.page.selectedIds.value.includes('102'))
    assert.ok(ctx.messages.some(message => message.level === 'success' && message.text === '已保存到资料库'))
    assert.equal(input.value, '')
  } finally { ctx.close() }
})

test('material parsing labels distinguish queued, parsing, failed and unknown without implying readiness', () => {
  for (const parseStatus of ['queued', 'parsing']) {
    assert.equal(evidence.materialParseLabel({ parseStatus }), '解析中')
    assert.equal(evidence.researchEvidenceRow(material('103', { parseStatus }), 'material').reason, '解析中')
  }
  assert.equal(evidence.materialParseLabel({ parse_status: 'failed' }), '解析失败')
  assert.equal(evidence.researchEvidenceRow(material('103', { parseStatus: 'failed' }), 'material').reason, '解析失败')
  assert.equal(evidence.materialParseLabel({}), '')
  assert.equal(evidence.materialParseLabel({ parseStatus: 'indexed' }), '')
  assert.equal(evidence.researchEvidenceRow(material('103', { scanStatus: 'quarantined' }), 'material').ready, false)
})

test('research material list exposes parse state before selection and blocks failed selected evidence', async () => {
  const ctx = await mount('ResearchCreateView', { api: {
    searchPipelineResearchMaterials: async () => ({ data: { rows: [{ id: '505', type: 'document', title: '失败资料', parseStatus: 'failed' }], total: 1 } }),
    getPipelineKnowledgeDocument: async id => ({ data: material(id, { parseStatus: 'failed' }) })
  } })
  try {
    assert.equal(evidence.materialParseLabel(ctx.page.availableMaterials.value[0].detail), '解析失败')
    ctx.page.selectedIds.value = ['505']
    await ctx.page.verifySelected()
    assert.equal(ctx.page.availableMaterials.value[0].reason, '解析失败')
    ctx.page.activeStep.value = 1
    assert.equal(ctx.page.nextStepBlocked.value, true)
  } finally { ctx.close() }
})

test('research automatically polls pending parsing, stops on completion and cancels timers on exit', async () => {
  const timers = new Map()
  let token = 0
  let status = 'parsing'
  let reads = 0
  const ctx = await mount('ResearchCreateView', { timers: {
    setTimeout: (callback, delay) => { assert.equal(delay, 3000); timers.set(++token, callback); return token },
    clearTimeout: id => timers.delete(id)
  }, api: {
    searchPipelineResearchMaterials: async () => ({ data: { rows: [{ id: '104', type: 'document', title: '资料', parseStatus: 'parsing' }], total: 1 } }),
    getPipelineKnowledgeDocument: async id => { reads++; return { data: material(id, { parseStatus: status }) } }
  } })
  try {
    assert.equal(timers.size, 1)
    const fire = async () => { const [id, callback] = timers.entries().next().value; timers.delete(id); callback(); await settle() }
    await fire()
    assert.equal(reads, 1)
    assert.equal(timers.size, 1)
    status = 'indexed'
    await fire()
    assert.equal(ctx.page.availableMaterials.value[0].detail.parseStatus, 'indexed')
    assert.equal(timers.size, 0)
    await ctx.page.loadMaterials()
    await settle()
    assert.equal(timers.size, 1)
    ctx.close()
    assert.equal(timers.size, 0)
  } finally { ctx.close() }
})

test('research parsing refresh updates visible and off-page selected documents without resetting page or selection', async () => {
  let status = 'parsing'
  const ctx = await mount('ResearchCreateView', { api: {
    searchPipelineResearchMaterials: async () => ({ data: { rows: [{ id: '104', type: 'document', title: '资料', parseStatus: 'parsing' }], total: 25 } }),
    getPipelineKnowledgeDocument: async id => ({ data: material(id, { parseStatus: status }) })
  } })
  try {
    ctx.page.selectedIds.value = ['105']
    await ctx.page.verifySelected()
    ctx.page.materialPage.value = 2
    await settle()
    status = 'indexed'
    await ctx.page.refreshParsingMaterials()
    assert.equal(ctx.page.availableMaterials.value[0].detail.parseStatus, 'indexed')
    assert.equal(ctx.page.selectedMaterials.value[0].ready, true)
    assert.deepEqual(ctx.page.selectedIds.value, ['105'])
    assert.equal(ctx.page.materialPage.value, 2)
  } finally { ctx.close() }
})

test('research parsing retry is single-flight, retains selection and resumes updates; failures stay retryable', async () => {
  let status = 'failed'
  let calls = 0
  const pending = later()
  const ctx = await mount('ResearchCreateView', { api: {
    searchPipelineResearchMaterials: async () => ({ data: { rows: [{ id: '104', type: 'document', title: '资料', parseStatus: 'failed' }], total: 1 } }),
    getPipelineKnowledgeDocument: async id => ({ data: material(id, { parseStatus: status }) }),
    reparsePipelineKnowledgeDocument: async () => { calls++; return pending.promise }
  } })
  try {
    ctx.page.selectedIds.value = ['104']
    await ctx.page.verifySelected()
    const retry = ctx.page.retryMaterial(ctx.page.availableMaterials.value[0])
    await ctx.page.retryMaterial(ctx.page.availableMaterials.value[0])
    assert.equal(calls, 1)
    status = 'queued'
    pending.resolve({ data: material('104', { parseStatus: 'queued' }) })
    await retry
    assert.equal(evidence.materialParseLabel(ctx.page.availableMaterials.value[0].detail), '解析中')
    assert.deepEqual(ctx.page.selectedIds.value, ['104'])
    status = 'indexed'
    await ctx.page.refreshParsingMaterials()
    assert.equal(ctx.page.selectedMaterials.value[0].ready, true)
  } finally { ctx.close() }
})

test('research parsing refresh retains pending state through network failure and ignores late responses after unmount', async () => {
  let fail = false
  let pending
  const ctx = await mount('ResearchCreateView', { api: {
    getPipelineIntelligenceDetail: async () => { throw new Error('不是资讯') },
    searchPipelineResearchMaterials: async () => ({ data: { rows: [{ id: '104', type: 'document', title: '资料', parseStatus: 'parsing' }], total: 1 } }),
    getPipelineKnowledgeDocument: async id => {
      if (fail) throw new Error('离线')
      return pending ? pending.promise : { data: material(id, { parseStatus: 'parsing' }) }
    }
  } })
  try {
    ctx.page.selectedIds.value = ['104']
    await ctx.page.verifySelected()
    fail = true
    await ctx.page.refreshParsingMaterials()
    assert.equal(ctx.page.selectedMaterials.value[0].detail.parseStatus, 'parsing')
    assert.match(ctx.page.parsingRefreshError.value, /自动重试/)
    fail = false
    pending = later()
    const refresh = ctx.page.refreshParsingMaterials()
    ctx.close()
    pending.resolve({ data: material('104') })
    await refresh
    assert.equal(ctx.page.materialRows.value[0].detail.parseStatus, 'parsing')
  } finally { ctx.close() }
})

test('research parsing retry failures retain failed state and allow another attempt', async () => {
  let calls = 0
  const ctx = await mount('ResearchCreateView', { api: {
    searchPipelineResearchMaterials: async () => ({ data: { rows: [{ id: '104', type: 'document', title: '资料', parseStatus: 'failed' }], total: 1 } }),
    reparsePipelineKnowledgeDocument: async () => { calls++; throw { msg: '重试服务暂不可用' } }
  } })
  try {
    await ctx.page.retryMaterial(ctx.page.availableMaterials.value[0])
    assert.equal(ctx.page.availableMaterials.value[0].detail.parseStatus, 'failed')
    assert.deepEqual(ctx.page.retryingMaterialIds.value, [])
    assert.ok(ctx.messages.some(message => message.text === '重试服务暂不可用'))
    await ctx.page.retryMaterial(ctx.page.availableMaterials.value[0])
    assert.equal(calls, 2)
  } finally { ctx.close() }
})

test('research upload errors keep the dialog open for retry without adding materials', async () => {
  const ctx = await mount('ResearchCreateView', { api: { uploadPipelineKnowledgeDocument: async () => { throw { msg: '上传失败，请重试' } } } })
  try {
    ctx.page.uploadDialogVisible.value = true
    const file = new Blob(['test material'])
    Object.defineProperty(file, 'name', { value: 'material.txt' })
    const input = { files: [file], value: 'material.txt' }
    await ctx.page.uploadResearchMaterial({ target: input })
    assert.equal(ctx.page.uploadDialogVisible.value, true)
    assert.equal(ctx.page.uploadError.value, '上传失败，请重试')
    assert.equal(ctx.page.uploading.value, false)
    assert.equal(ctx.page.selectedIds.value.length, 0)
    assert.equal(input.value, '')
  } finally { ctx.close() }
})

test('catalog rows without review status can be selected and are verified against authoritative detail', async () => {
  const pending = later()
  let calls = 0
  const ctx = await mount('ResearchCreateView', { api: {
    searchPipelineResearchMaterials: async () => ({ data: { rows: [{ id: '106', title: '未附审核状态的资讯', type: 'news' }], total: 1 } }),
    getPipelineIntelligenceDetail: async id => { calls++; return pending.promise }
  } })
  try {
    ctx.store.newsItems = [{ id: '106', title: '未附审核状态的资讯', summary: '列表摘要' }]
    const row = ctx.page.availableMaterials.value.find(item => item.id === '106')
    assert.equal(row.state, 'unchecked')
    assert.equal(row.ready, false)
    assert.equal(row.reason, '选择后核验')
    ctx.page.activeStep.value = 1
    ctx.page.toggleMaterial(row.id, true)
    assert.equal(calls, 1)
    assert.equal(ctx.page.nextStepBlocked.value, true)
    pending.resolve({ data: article(row.id) })
    await settle()
    assert.equal(ctx.page.selectedMaterials.value[0].ready, true)
    assert.equal(ctx.page.nextStepBlocked.value, false)
    assert.deepEqual([...ctx.page.buildResearchPayload().selectedItemIds], [row.id])
    ctx.page.toggleMaterial(row.id, false)
    assert.equal(ctx.page.selectedIds.value.length, 0)
  } finally { ctx.close() }
})

test('research news and wechat tabs query distinct sources while keeping selection', async () => {
  const requests = []
  const ctx = await mount('ResearchCreateView', { api: { searchPipelineResearchMaterials: async query => {
    requests.push({ ...query })
    return { data: { rows: [{ id: query.type === 'wechat' ? '601' : '602', title: query.type, type: 'news', source_type: query.type }], total: 1 } }
  } } })
  try {
    assert.deepEqual(ctx.page.materialTabs, ['全部', '新闻资讯', '公众号', '论文', '内部资料'])
    ctx.page.materialTab.value = '新闻资讯'
    await settle()
    assert.equal(requests.at(-1).type, 'news')
    ctx.page.toggleMaterial('news', true)
    await settle()
    ctx.page.materialTab.value = '公众号'
    await settle()
    assert.equal(requests.at(-1).type, 'wechat')
    assert.equal(ctx.page.availableMaterials.value[0].type, '公众号')
    ctx.page.toggleMaterial('wechat', true)
    await settle()
    ctx.page.materialTab.value = '新闻资讯'
    await settle()
    assert.deepEqual([...ctx.page.selectedIds.value], ['news', 'wechat'])
  } finally { ctx.close() }
})

test('research material pagination queries the whole catalog and preserves cross-page selections', async () => {
  const requests = []
  const ctx = await mount('ResearchCreateView', { api: { searchPipelineResearchMaterials: async query => {
    requests.push({ ...query })
    const id = query.keyword ? '107' : `${700 + query.pageNum}`
    return { data: { rows: [{ id, title: id, type: query.type === 'paper' ? 'paper' : 'news' }], total: query.keyword ? 1 : 31 } }
  } } })
  try {
    assert.equal(ctx.page.materialPageSize.value, 10)
    assert.equal(requests.at(-1).pageSize, 10)
    ctx.page.toggleMaterial('701', true)
    await settle()
    ctx.page.materialPage.value = 2
    await settle()
    assert.equal(requests.at(-1).pageNum, 2)
    assert.deepEqual(ctx.page.availableMaterials.value.map(item => item.id), ['702'])
    ctx.page.toggleMaterial('702', true)
    await settle()
    ctx.page.materialPage.value = 1
    await settle()
    assert.deepEqual([...ctx.page.selectedIds.value], ['701', '702'])
    ctx.page.materialPageSize.value = 20
    await settle()
    assert.equal(requests.at(-1).pageSize, 20)
    assert.equal(requests.at(-1).pageNum, 1)
    ctx.page.materialPageSize.value = 50
    ctx.page.materialTab.value = '论文'
    ctx.page.materialKeyword.value = '远端论文'
    await settle()
    assert.equal(requests.at(-1).pageSize, 50)
    assert.equal(requests.at(-1).type, 'paper')
    assert.equal(requests.at(-1).keyword, '远端论文')
    assert.deepEqual(ctx.page.availableMaterials.value.map(item => item.id), ['107'])
    assert.deepEqual([...ctx.page.buildResearchPayload().selectedItemIds], ['701', '702'])
  } finally { ctx.close() }
})

test('current research page selection toggles without changing selections on other pages', async () => {
  const ctx = await mount('ResearchCreateView', { api: {
    searchPipelineResearchMaterials: async query => ({ data: {
      rows: (query.pageNum === 1 ? ['first'] : ['second', 'third', '108']).map(id => ({ id, title: id, type: 'news' })), total: 14
    } }),
    getPipelineIntelligenceDetail: async id => ({ data: article(id, { allowAiUse: id !== '108' }) })
  } })
  try {
    ctx.page.toggleMaterial('first', true)
    await settle()
    ctx.page.materialPage.value = 2
    await settle()
    ctx.page.toggleMaterial('108', true)
    await settle()
    ctx.page.selectCurrentMaterialPage()
    await settle()
    assert.deepEqual([...ctx.page.selectedIds.value], ['first', '108', 'second', 'third'])
    assert.equal(ctx.page.currentMaterialPageSelected.value, true)
    ctx.page.selectCurrentMaterialPage()
    await settle()
    assert.deepEqual([...ctx.page.selectedIds.value], ['first'])
    assert.equal(ctx.page.currentMaterialPageSelected.value, false)
    ctx.page.toggleMaterial('108', false)
    ctx.page.materialRows.value = ctx.page.materialRows.value.map(item => item.id === '108' ? { ...item, state: 'unavailable' } : item)
    ctx.page.selectCurrentMaterialPage()
    await settle()
    assert.deepEqual([...ctx.page.selectedIds.value], ['first', 'second', 'third'])
    ctx.page.toggleMaterial('second', false)
    await settle()
    assert.equal(ctx.page.currentMaterialPageSelected.value, false)
    ctx.page.selectCurrentMaterialPage()
    await settle()
    assert.deepEqual([...ctx.page.selectedIds.value].sort(), ['first', 'second', 'third'])
    ctx.page.submitting.value = true
    ctx.page.toggleMaterial('second', false)
    ctx.page.selectCurrentMaterialPage()
    assert.deepEqual([...ctx.page.selectedIds.value].sort(), ['first', 'second', 'third'])
    ctx.page.submitting.value = false
    ctx.page.materialPage.value = 1
    await settle()
    assert.equal(ctx.page.availableMaterials.value[0].id, 'first')
    assert.ok(ctx.page.selectedIds.value.includes('first'))
  } finally { ctx.close() }
})

test('late research material pages cannot replace a newer search and failures remain retryable', async () => {
  const old = later()
  let fail = false
  const ctx = await mount('ResearchCreateView', { api: { searchPipelineResearchMaterials: async query => {
    if (query.keyword === '120') return old.promise
    if (fail) throw { msg: '资料加载失败' }
    return { data: { rows: [{ id: query.keyword ? '603' : '109', type: 'news', title: '资料' }], total: 1 } }
  } } })
  try {
    ctx.page.materialKeyword.value = '120'
    await settle()
    ctx.page.materialKeyword.value = '125'
    await settle()
    old.resolve({ data: { rows: [{ id: '110', type: 'news' }], total: 100 } })
    await settle()
    assert.equal(ctx.page.availableMaterials.value[0].id, '603')
    fail = true
    await ctx.page.loadMaterials()
    assert.equal(ctx.page.materialError.value, '资料加载失败')
    assert.equal(ctx.page.availableMaterials.value.length, 0)
    fail = false
    await ctx.page.loadMaterials()
    assert.equal(ctx.page.materialError.value, '')
    assert.equal(ctx.page.availableMaterials.value[0].id, '603')
  } finally { ctx.close() }
})

test('detail review states distinguish missing status, pending, rejected and withdrawn without authorizing them', () => {
 for (const status of [undefined, 'pending', 'rejected', 'withdrawn']) {
  const row = evidence.researchEvidenceRow(article('111', { status }), 'article')
  assert.equal(row.ready, true)
  assert.equal(row.state, 'verified')
 }
 assert.equal(evidence.researchEvidenceRow(article('111', { allowAiUse: false }), 'article').ready, false)
})

test('catalog approval never bypasses a rejected detail response', async () => {
 const ctx = await mount('ResearchCreateView', { api: { getPipelineIntelligenceDetail: async id => ({ data: article(id, { allowAiUse: false }) }) } })
 try {
  ctx.store.newsItems = [article('108')]
  ctx.page.toggleMaterial('108', true)
  await settle()
  assert.equal(ctx.page.selectedMaterials.value[0].ready, false)
  assert.equal(ctx.page.selectedMaterials.value[0].reason, '未允许用于 AI')
  assert.throws(() => ctx.page.buildResearchPayload(), /未核验或不可用/)
 } finally { ctx.close() }
})

test('basket-selected articles become one report payload without unselected articles', async () => {
  const ctx = await mount('ResearchCreateView', { query: { selected: ['111', '113'] }, basket: [article('111'), article('112'), article('113')] })
  try {
    assert.deepEqual([...ctx.page.selectedIds.value], ['111', '113'])
    assert.deepEqual([...ctx.page.buildResearchPayload().selectedItemIds], ['111', '113'])
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('both changed SFC scripts and templates compile', () => {
  for (const name of names) {
    const { descriptor, errors } = parse(sources[name])
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: name })
    assert.deepEqual(compileTemplate({ id: name, filename: name, source: descriptor.template.content, compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
  }
})

test('research imports every basket ID beyond the initial catalog and builds the full verified payload', async () => {
  const requests = []
  const basket = Array.from({ length: 25 }, (_, index) => ({ id: `${800 + index}`, title: '旧快照不能代替授权详情', type: 'article' }))
  const ctx = await mount('ResearchCreateView', { basket, api: { getPipelineIntelligenceDetail: async id => { requests.push(id); return { data: article(id) } } } })
  try {
    await ctx.page.verifySelected()
    assert.equal(ctx.page.selectedIds.value.length, 25)
    assert.equal(new Set(requests).size, 25)
    assert.equal(ctx.page.selectedMaterials.value[24].title, '真实资讯 824')
    assert.equal(ctx.page.buildResearchPayload().selectedItemIds.length, 25)
    assert.equal(ctx.page.selectionProblems.value.length, 0)
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('research outline controls reorder the submitted chapters and preserve at least one chapter', async () => {
  const ctx = await mount('ResearchCreateView', { basket: [{ id: '114', type: 'article' }] })
  try {
    await ctx.page.verifySelected()
    ctx.page.outline.value = [{ id: 1, title: '第一章', words: 1000 }, { id: 2, title: '第二章', words: 1500 }, { id: 3, title: '第三章', words: 1200 }]
    ctx.page.moveOutline(2, -1)
    assert.deepEqual(ctx.page.buildResearchPayload().outline.map(item => item.id), [1, 3, 2])
    ctx.page.moveOutline(0, -1)
    ctx.page.moveOutline(2, 1)
    assert.deepEqual(ctx.page.outline.value.map(item => item.id), [1, 3, 2])
    ctx.page.removeOutline(1)
    ctx.page.removeOutline(3)
    ctx.page.removeOutline(2)
    assert.deepEqual(ctx.page.outline.value.map(item => item.id), [2])
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('checkbox selections are idempotent, removable and locked during submission', async () => {
  for (const name of names) {
    const ctx = await mount(name)
    try {
      const toggle = name === 'ResearchCreateView' ? ctx.page.toggleMaterial : ctx.page.toggleCandidate
      const selected = name === 'ResearchCreateView' ? ctx.page.selectedIds : ctx.page.selectedCandidateIds
      toggle('111', true)
      toggle('111', true)
      toggle('112', true)
      assert.deepEqual([...selected.value], ['111', '112'])
      toggle('111', false)
      assert.deepEqual([...selected.value], ['112'])
      ctx.page.submitting.value = true
      toggle('112', false)
      assert.deepEqual([...selected.value], ['112'])
      assert.equal(ctx.mutations, 0)
      assert.doesNotMatch(sources[name], /<el-checkbox v-model="(?:selectedIds|selectedCandidateIds)"/)
    } finally { ctx.close() }
  }
})

test('research keeps missing and denied IDs visible and blocks payloads instead of using snapshots', async () => {
  const ctx = await mount('ResearchCreateView', { basket: [{ id: '115', type: 'article' }, { id: '108', type: 'article', title: '私有快照标题' }], api: { getPipelineIntelligenceDetail: async id => { if (id === '108') throw { msg: '资料不存在或无权访问' }; return { data: article(id) } }, getPipelineKnowledgeDocument: async () => { throw { msg: '资料不存在或无权访问' } } } })
  try {
    assert.deepEqual([...ctx.page.selectedIds.value], ['115', '108'])
    assert.equal(ctx.page.selectedMaterials.value[1].title, '选材 108')
    assert.match(ctx.page.selectionProblems.value[0].reason, /无权访问/)
    assert.throws(() => ctx.page.buildResearchPayload(), /不可用/)
    ctx.page.activeStep.value = 1
    ctx.page.nextStep()
    assert.equal(ctx.page.activeStep.value, 1)
    ctx.page.toggleMaterial('108', false)
    await settle()
    assert.deepEqual(ctx.page.buildResearchPayload().selectedItemIds, ['115'])
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('research checks parsed material safety and explicit AI authorization; paper abstracts stay abstracts', async () => {
  const docs = { '501': material('501'), '502': material('502', { parseStatus: 'parsing' }), '116': material('116', { scanStatus: 'quarantined' }), '117': material('117', { allowAiUse: false }) }
  const ctx = await mount('ResearchCreateView', { basket: [...Object.keys(docs).map(id => ({ id, type: 'material' })), { id: '118', type: 'paper' }, { id: '119', type: 'paper' }], api: {
    getPipelineKnowledgeDocument: async id => ({ data: docs[id] }),
    getPipelineIntelligenceDetail: async id => ({ data: article(id, { category: 'paper', source_type: 'paper', open_access_status: 'restricted', summary: id === '119' ? '' : '可访问的论文摘要', content: '' }) })
  } })
  try {
    await ctx.page.verifySelected()
    assert.equal(ctx.page.selectionProblems.value.length, 4)
    assert.match(ctx.page.selectedMaterials.value.find(item => item.id === '118').meta, /仅使用.*摘要/)
    assert.equal(ctx.page.selectedMaterials.value.find(item => item.id === '118').ready, true)
    assert.match(ctx.page.selectedMaterials.value.find(item => item.id === '119').reason, /摘要/)
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('research copying combines original selectedItems and all configured IDs, and keeps the actual outline', async () => {
  const ctx = await mount('ResearchCreateView', { query: { sourceTask: '120' }, basket: [{ id: '121', type: 'article' }], api: { getPipelineResearchJob: async () => ({ data: {
    title: '原任务', selectedItems: [{ id: '122', type: '科技资讯', title: '快照' }], config: { templateId: '100', selectedItemIds: ['122', '123'], direction: '检测技术' }, outline: [{ id: 99, title: '原任务真实大纲', words: 1800 }]
  } }) } })
  try {
    await ctx.page.verifySelected()
    assert.deepEqual([...ctx.page.selectedIds.value], ['122', '123'])
    assert.equal(ctx.page.selectedMaterials.value[1].title, '真实资讯 123')
    assert.equal(ctx.page.outline.value[0].title, '原任务真实大纲')
    assert.deepEqual(ctx.page.buildResearchPayload().selectedItemIds, ['122', '123'])
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('copy failure does not pretend a new empty task is a successfully copied task', async () => {
  const ctx = await mount('ResearchCreateView', { query: { sourceTask: '108' }, basket: [{ id: '124', type: 'article' }], api: { getPipelineResearchJob: async () => { throw { msg: '任务无权访问' } } } })
  try {
    assert.match(ctx.page.sourceTaskError.value, /无权访问/)
    assert.deepEqual([...ctx.page.selectedIds.value], ['124'])
    assert.throws(() => ctx.page.buildResearchPayload(), /原任务/)
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('old copied task responses and removed-selection details cannot overwrite newer input', async () => {
  const oldTask = later()
  const slowDetail = later()
  const ctx = await mount('ResearchCreateView', { api: {
    getPipelineResearchJob: id => id === '120' ? oldTask.promise : Promise.resolve({ data: { title: '新任务', config: { selectedItemIds: ['125'] } } }),
    getPipelineIntelligenceDetail: id => id === '126' ? slowDetail.promise : Promise.resolve({ data: article(id) })
  } })
  try {
    const old = ctx.page.loadSourceTask('120')
    await ctx.page.loadSourceTask('125')
    oldTask.resolve({ data: { title: '旧任务', config: { selectedItemIds: ['120'] } } })
    await old
    await settle()
    assert.equal(ctx.page.form.name, '新任务（副本）')
    assert.deepEqual([...ctx.page.selectedIds.value], ['125'])
    ctx.page.setSelection([{ id: '126', type: 'article' }])
    ctx.page.toggleMaterial('126', false)
    slowDetail.resolve({ data: article('126') })
    await settle()
    assert.equal(ctx.page.selectedMaterials.value.length, 0)
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('retry replaces a denied material with authorized current detail; account changes clear verification', async () => {
  let fail = true
  const ctx = await mount('ResearchCreateView', { basket: [{ id: '127', type: 'material' }], api: { getPipelineKnowledgeDocument: async id => { if (fail) throw { msg: '暂不可用' }; return { data: material(id) } }, getPipelineIntelligenceDetail: async () => { throw { msg: '不在公开目录中' } } } })
  try {
    assert.equal(ctx.page.selectionProblems.value.length, 1)
    fail = false
    await ctx.page.verifySelected(true)
    assert.equal(ctx.page.selectionProblems.value.length, 0)
    ctx.store.workspaceEpoch++
    assert.equal(ctx.page.selectionProblems.value.length, 1)
    assert.match(ctx.page.selectionProblems.value[0].reason, /账号已变化/)
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('legacy snapshot types only route requests; actual authorized detail decides paper versus material', async () => {
  const row = await evidence.verifyEvidence({ id: '128', type: '论文' }, {
    getIntelligence: async () => { throw { msg: '不在公开目录' } },
    getMaterial: async id => ({ data: material(id, { type: '论文' }) })
  })
  assert.equal(row.itemType, 'material')
  assert.equal(row.ready, true)
  const paper = await evidence.verifyEvidence({ id: '129', type: 'material' }, {
    getMaterial: async () => { throw { msg: '不存在' } },
    getIntelligence: async id => ({ data: article(id, { category: 'paper', source_type: 'paper' }) })
  })
  assert.equal(paper.itemType, 'paper')
  assert.match(paper.meta, /仅使用.*摘要/)
})

test('precise dates reject year-only, month-only, invalid dates and handle Shanghai day boundaries', () => {
  for (const value of ['', null, '2026', '2026-10', '2026-02-30', '2026-13-01']) assert.equal(evidence.preciseDate(value), '')
  assert.equal(evidence.preciseDate('2026-12-31T16:00:00Z'), '2027-01-01')
  assert.equal(evidence.preciseDate('2026-12-31 23:59:59'), '2026-12-31')
  const scope = { period: ['2026-12-31', '2027-01-01'], sources: ['新闻网站'] }
  assert.equal(evidence.digestCandidate(article('130', { publish_time: '2026-12-31 00:00:00' }), scope), true)
  assert.equal(evidence.digestCandidate(article('131', { publish_time: '2027-01-01 23:59:59' }), scope), true)
  assert.equal(evidence.digestCandidate(article('132', { publish_time: '2027-01-02' }), scope), false)
  assert.equal(evidence.digestCandidate(article('paper', { category: 'paper' }), scope), false)
})

test('digest independent plan dialog does not couple plan configuration to manual generation', async () => {
  const ctx = await mount('DigestCreateView')
  try {
    for (const [frequency, type] of [
      ['daily', '日报'], ['weekly', '周报'], ['monthly', '月报']
    ]) {
      ctx.page.form.type = type
      await vue.nextTick()
      assert.equal(ctx.page.form.type, type)
      assert.equal(ctx.page.currentTypeConfig.value.reportType, frequency)
    }
    ctx.page.planDialog.value = true
    assert.equal(ctx.page.form.type, '月报')
    assert.equal(Object.hasOwn(ctx.page.form, 'schedule'), false)
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('digest refuses over-limit single and page selections atomically and still allows deselection', async () => {
  const ctx = await mount('DigestCreateView')
  try {
    ctx.page.selectedCandidateIds.value = Array.from({ length: 50 }, (_, i) => `${900 + i}`)
    ctx.page.toggleCandidate('125', true)
    assert.equal(ctx.page.selectedCandidateIds.value.length, 50)
    assert.match(ctx.page.selectionNotice.value, /最多选择 50/)
    ctx.page.previewPages.value = { '10:1': { rows: [{ id: '125', ready: true }] } }
    ctx.page.selectCurrentPage()
    assert.equal(ctx.page.selectedCandidateIds.value.length, 50)
    ctx.page.toggleCandidate('900', false)
    ctx.page.toggleCandidate('125', true)
    assert.equal(ctx.page.selectedCandidateIds.value.length, 50)
    assert.ok(ctx.page.selectedCandidateIds.value.includes('125'))
    ctx.page.selectedCandidateIds.value.push('137')
    assert.throws(() => ctx.page.buildDigestPayload(), /最多选择 50/)
  } finally { ctx.close() }
})

test('digest queries the server by direction/keyword and actual page, then checks detail dates and sources', async () => {
  const calls = []
  const details = {
    '133': article('133', { publish_time: '2026-12-31' }),
    '120': article('120', { publish_time: '2026-01-01' }),
    '134': article('134', { publish_time: '' }),
    '135': article('135', { publish_time: '2026' }),
    '1201': article('1201', { publish_time: '2026-12-31', source_type: 'wechat' }),
    '1202': article('1202', { publish_time: '2026-12-31', category: 'paper', summary: '论文摘要' })
  }
  const result = await evidence.fetchDigestPage({ period: ['2026-12-31'], sources: ['新闻网站'], directions: ['检测技术'], keywords: ['关键词A', '关键词B'] }, {
    search: async params => { calls.push(params); return { data: { rows: Object.keys(details).map(id => ({ id })), total: 250 } } },
    getIntelligence: async id => ({ data: details[id] })
  }, 3)
  assert.equal(calls.length, 1)
  assert.equal(calls[0].pageNum, 3)
  assert.deepEqual(calls[0].period, ['2026-12-31'])
  assert.deepEqual(calls[0].keywords, ['关键词A', '关键词B'])
  assert.deepEqual(calls[0].directions, ['检测技术'])
  assert.deepEqual(result.rows.map(item => item.id), ['133'])
  assert.equal(result.inspected, 6, 'overlapping keyword results are deduplicated')
  assert.equal(result.pageCount, 13)
})

test('multiple digest keywords share the page capacity without losing their following results', async () => {
  const scope = { period: ['2026-10-13'], sources: ['新闻网站'], directions: [], keywords: ['A', 'B'] }
  const api = {
    search: async query => ({ data: { rows: Array.from({ length: query.pageSize }, (_, index) => ({ id: `${1000 + (query.pageNum - 1) * query.pageSize + index}` })), total: 30 } }),
    getIntelligence: async id => ({ data: article(id) })
  }
  const first = await evidence.fetchDigestPage(scope, api, 1, 10)
  const second = await evidence.fetchDigestPage(scope, api, 2, 10)
  assert.equal(first.rows.length, 10)
  assert.equal(second.rows.length, 10)
  assert.equal(first.pageCount, 3)
  assert.equal(new Set([...first.rows, ...second.rows].map(item => item.id)).size, 20)
})

test('digest keyword groups larger than one page do not overflow or lose later keywords', async () => {
  const scope = { period: ['2026-10-13'], sources: ['新闻网站'], directions: [], keywords: Array.from({ length: 12 }, (_, index) => `keyword-${index}`) }
  const api = {
    search: async query => ({ data: { rows: query.keywords.slice((query.pageNum - 1) * query.pageSize, query.pageNum * query.pageSize).map(id => ({ id: String(1100 + scope.keywords.indexOf(id)) })), total: 12 } }),
    getIntelligence: async id => ({ data: article(id) })
  }
  const first = await evidence.fetchDigestPage(scope, api, 1, 10)
  const second = await evidence.fetchDigestPage(scope, api, 2, 10)
  assert.equal(first.rows.length, 10)
  assert.equal(second.rows.length, 2)
  assert.equal(first.pageCount, 2)
  assert.equal(new Set([...first.rows, ...second.rows].map(item => item.id)).size, 12)
})

test('digest preserves cross-page explicit selections and builds only those IDs without generating', async () => {
  const calls = []
  const ctx = await mount('DigestCreateView', { api: {
    searchPipelineIntelligence: async params => { calls.push(params); return { data: { rows: [{ id: `${700 + params.pageNum}` }], total: 45 } } }
  } })
  try {
    ctx.page.form.date = new Date(2026, 9, 13)
    await settle()
    assert.equal(ctx.page.previewPageSize.value, 10)
    assert.equal(calls.at(-1).pageSize, 10)
    ctx.page.selectCurrentPage()
    ctx.page.previewPage.value = 2
    await settle()
    ctx.page.selectCurrentPage()
    assert.deepEqual([...ctx.page.selectedCandidateIds.value], ['701', '702'])
    assert.equal(calls.at(-1).pageNum, 2)
    assert.equal(ctx.page.checkedCandidates.value.length, 2)
    assert.deepEqual(ctx.page.buildDigestPayload().selectedItemIds, ['701', '702'])
    assert.equal(ctx.page.currentCandidatePageSelected.value, true)
    ctx.page.selectCurrentPage()
    assert.deepEqual([...ctx.page.selectedCandidateIds.value], ['701'])
    assert.equal(ctx.page.currentCandidatePageSelected.value, false)
    ctx.page.selectCurrentPage()
    assert.deepEqual([...ctx.page.selectedCandidateIds.value], ['701', '702'])
    ctx.page.submitting.value = true
    ctx.page.selectCurrentPage()
    assert.deepEqual([...ctx.page.selectedCandidateIds.value], ['701', '702'])
    ctx.page.submitting.value = false
    ctx.page.previewPageSize.value = 20
    await settle()
    assert.equal(ctx.page.previewPage.value, 1)
    assert.equal(calls.at(-1).pageSize, 20)
    assert.deepEqual([...ctx.page.selectedCandidateIds.value], ['701', '702'])
    assert.deepEqual(ctx.page.buildDigestPayload().selectedItemIds, ['701', '702'])
    ctx.page.previewPageSize.value = 50
    await settle()
    assert.equal(calls.at(-1).pageSize, 50)
    assert.deepEqual(ctx.page.buildDigestPayload().selectedItemIds, ['701', '702'])
    ctx.page.toggleCandidate('701', false)
    assert.deepEqual(ctx.page.buildDigestPayload().selectedItemIds, ['702'])
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('digest scope changes invalidate old pages and selections; a late old response cannot publish', async () => {
  const old = later()
  let calls = 0
  const ctx = await mount('DigestCreateView', { api: { searchPipelineIntelligence: () => ++calls === 1 ? old.promise : Promise.resolve({ data: { rows: [{ id: '125' }], total: 1 } }) } })
  try {
    ctx.page.form.date = new Date(2026, 9, 13)
    ctx.page.form.keywords = ['新关键词']
    await settle()
    old.resolve({ data: { rows: [{ id: '120' }], total: 1 } })
    await settle()
    assert.deepEqual(ctx.page.candidateItems.value.map(item => item.id), ['125'])
    ctx.page.selectCurrentPage()
    ctx.page.form.sources = ['微信公众号']
    await settle()
    assert.equal(ctx.page.selectedCandidateIds.value.length, 0)
    assert.equal(ctx.page.candidateItems.value.length, 0)
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('digest request or detail failure is visible, not a zero candidate conclusion, and retry recovers', async () => {
  let fail = true
  const ctx = await mount('DigestCreateView', { api: { searchPipelineIntelligence: async () => { if (fail) throw { msg: '查询失败' }; return { data: { rows: [{ id: '111' }], total: 1 } } } } })
  try {
    ctx.page.form.date = new Date(2026, 9, 13)
    await settle()
    assert.equal(ctx.page.previewError.value, '查询失败')
    assert.equal(ctx.page.refreshing.value, false)
    assert.throws(() => ctx.page.buildDigestPayload(), /加载失败/)
    fail = false
    await ctx.page.refreshPreview()
    assert.equal(ctx.page.previewError.value, '')
    assert.equal(ctx.page.candidateItems.value.length, 1)
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
  await assert.rejects(() => evidence.fetchDigestPage({ period: ['2026-10-13'], sources: ['新闻网站'], directions: [], keywords: [] }, {
    search: async () => ({ data: { rows: [{ id: '108' }], total: 1 } }), getIntelligence: async () => { throw { msg: '已撤权' } }
  }, 1), /108.*已撤权/)
})

test('digest dedicated pagination can access the full filtered pool and rejects malformed totals', async () => {
  const scope = { period: ['2026-10-13'], sources: ['新闻网站'], directions: [], keywords: [] }
  const result = await evidence.fetchDigestPage(scope, { search: async () => ({ data: { rows: [], total: 10000 } }) }, 1)
  assert.equal(result.pageCount, 500)
  assert.equal(result.truncated, false)
  await assert.rejects(() => evidence.fetchDigestPage(scope, { search: async () => ({ data: {} }) }, 1), /分页数据无效/)
  await assert.rejects(() => evidence.fetchDigestPage({ ...scope, period: ['2026'] }, {}, 1), /报告周期/)
})

test('digest invalid/reversed periods do not query, and cleared controls never become an epoch date', async () => {
  const calls = []
  const ctx = await mount('DigestCreateView', { api: { searchPipelineIntelligence: async params => { calls.push(params); return { data: { rows: [], total: 0 } } } } })
  try {
    const before = calls.length
    ctx.page.form.date = null
    await settle()
    assert.equal(calls.length, before)
    assert.deepEqual(ctx.page.buildReportPeriod().period, [])
    assert.match(ctx.page.previewError.value, /报告周期/)
    ctx.page.form.type = '周报'
    ctx.page.form.period = [new Date(2027, 0, 2), new Date(2026, 11, 31)]
    await settle()
    assert.equal(calls.length, before)
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('digest late requests after unmount cannot publish candidates', async () => {
  const response = later()
  const ctx = await mount('DigestCreateView', { api: { searchPipelineIntelligence: () => response.promise } })
  ctx.close()
  response.resolve({ data: { rows: [{ id: '136' }], total: 1 } })
  await settle()
  assert.equal(ctx.page.candidateItems.value.length, 0)
  assert.equal(ctx.mutations, 0)
})

test('stale template IDs warn without replacing authored text or outline on template reload', async () => {
  const ctx = await mount('ResearchCreateView', { query: { template: 'template-01' } })
  try {
    ctx.page.form.requirements = '用户输入的需求正文'
    ctx.page.form.name = '用户填写标题'
    ctx.page.outline.value = [{ id: 1, title: '用户编辑章节', content: '用户章节正文', words: 1000 }]
    await ctx.page.loadTemplates()
    await settle()
    assert.equal(ctx.page.form.template, 'template-01')
    assert.match(ctx.page.templateUpgradeNotice.value, /编号已升级/)
    assert.equal(ctx.page.form.requirements, '用户输入的需求正文')
    assert.equal(ctx.page.form.name, '用户填写标题')
    assert.equal(ctx.page.outline.value[0].content, '用户章节正文')
    await ctx.page.submitTask()
    assert.equal(ctx.mutations, 0)
    assert.ok(ctx.messages.some(item => item.text.includes('编号已升级')))
  } finally { ctx.close() }
})

test('digest stale template remains visible after reloading and cannot submit', async () => {
  const ctx = await mount('DigestCreateView')
  try {
    ctx.page.form.template = 'template-02'
    ctx.page.form.keywords = ['用户关键词']
    await ctx.page.loadTemplates()
    assert.equal(ctx.page.form.template, 'template-02')
    assert.deepEqual([...ctx.page.form.keywords], ['用户关键词'])
    await ctx.page.createDigest()
    assert.equal(ctx.mutations, 0)
    assert.ok(ctx.messages.some(item => item.text.includes('编号已升级')))
  } finally { ctx.close() }
})

test('both generation forms select the real large decimal template ID without hardcoded fallbacks', async () => {
  for (const name of names) {
    const id = '9007199254740993'
    const ctx = await mount(name, { api: {
      listPipelineTemplates: async () => ({ data: { rows: [{ id, name: '真实模板编号', purpose: name === 'DigestCreateView' ? 'digest' : 'research', digestCadence: name === 'DigestCreateView' ? 'daily' : null, modelId: null, modelConfigured: false, sections: [] }] } })
    } })
    try {
      assert.equal(ctx.page.form.template, id)
      assert.equal(typeof ctx.page.form.template, 'string')
      if (name === 'ResearchCreateView') {
        assert.equal(ctx.page.selectedTemplate.value.id, id)
        await ctx.page.submitTask()
        assert.ok(ctx.messages.some(item => item.text.includes('未配置可用的文本生成模型')))
      } else {
        assert.equal(ctx.page.availableTemplates.value[0].value, id)
      }
      assert.equal(ctx.mutations, 0)
      assert.doesNotMatch(sources[name], /template-0[12]/)
    } finally { ctx.close() }
  }
})

test('legacy template queries never select a replacement in either form and retain user input on same-page navigation', async () => {
  for (const name of names) {
    const ctx = await mount(name, { query: { template: 'old-template-uuid' } })
    try {
      assert.equal(ctx.page.form.template, 'old-template-uuid')
      ctx.page.form.keywords = ['保留用户关键词']
      if (name === 'ResearchCreateView') {
        ctx.page.form.requirements = '保留用户正文'
        ctx.page.outline.value = [{ id: 1, title: '原章节', content: '章节正文' }]
      } else {
        ctx.page.form.type = '周报'
        await settle()
      }
      await ctx.router.replace({ path: '/create', query: { template: 'another-old-template-uuid' } })
      await settle()
      await ctx.page.loadTemplates()
      assert.equal(ctx.page.form.template, 'another-old-template-uuid')
      assert.deepEqual([...ctx.page.form.keywords], ['保留用户关键词'])
      if (name === 'ResearchCreateView') {
        assert.equal(ctx.page.form.requirements, '保留用户正文')
        assert.equal(ctx.page.outline.value[0].content, '章节正文')
      }
      await (name === 'ResearchCreateView' ? ctx.page.submitTask() : ctx.page.createDigest())
      assert.equal(ctx.mutations, 0)
      assert.ok(ctx.messages.some(item => item.text.includes('编号已升级')))
    } finally { ctx.close() }
  }
})
