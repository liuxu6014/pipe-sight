import { useWizardHistory } from '../src/utils/portal/wizardHistory.js'
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { setImmediate } from 'node:timers/promises'
import * as vue from 'vue'
import { createMemoryHistory, createRouter, useRoute, useRouter } from 'vue-router'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { digestTemplatesFor, templateGenerationError } from '../src/utils/pipeline/compactContract.js'
import * as businessTimes from '../src/utils/portal/businessTime.js'
import * as businessIds from '../src/utils/portal/businessId.js'
import * as evidence from '../src/utils/portal/evidenceInput.js'
import { resolveBasketSelection } from '../src/utils/portal/basketSelection.js'
import { allocateReportWords } from '../src/utils/portal/reportLength.js'
import { cleanResultMeta } from '../src/utils/portal/discovery.js'
import { screeningRulesError } from '../src/utils/portal/digestScreeningRules.js'

const names = ['ResearchCreateView', 'DigestCreateView']
const sources = Object.fromEntries(names.map(name => [name, readFileSync(new URL(`../src/views/portal/pages/${name}.vue`, import.meta.url), 'utf8')]))
const later = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const settle = async () => { for (let i = 0; i < 4; i++) { await vue.nextTick(); await setImmediate() } }
const article = (id, overrides = {}) => ({ id, title: `真实资讯 ${id}`, category: 'news', status: 'approved', summary: '真实摘要', content: '真实正文', source_type: 'news', source: '实际来源', publish_time: '2026-10-13 12:00:00', ...overrides })
const screeningId = 'a'.repeat(32)
const screenedArticle = (id, keep = true, extras = {}) => ({
  id, title: `真实资讯 ${id}`, keep, category: '检测技术', tags: ['管道检测'], reason: '判断依据', ...extras
})
const screeningStart = (total = 1) => ({ data: { screeningId, total, processed: 0 } })
const screeningResult = rows => ({ data: { screeningId, total: rows.length, processed: rows.length, rows } })
async function screenWeekly(page) {
  page.form.period = [new Date(2026, 9, 13), new Date(2026, 9, 19)]
  await page.refreshPreview()
}
const material = (id, overrides = {}) => ({ id, name: `资料 ${id}`, status: '已解析', parseStatus: 'indexed', scanStatus: 'clean', allowAiUse: true, parsedText: '实际解析正文', ...overrides })

// Execute the actual SFC setup/lifecycle with Vue and a memory router. All APIs
// are injected. Generation, scheduling and upload throw if accidentally called.
async function mount(name, { query = {}, api = {}, basket = [], timers = {} } = {}) {
  const messages = []
  const store = vue.reactive({ workspaceEpoch: 0, basket, newsItems: [], paperItems: [], knowledgeDocuments: [], hydrate: async () => {}, registerGenerationTask() {} })
  let mutations = 0
  const forbidden = () => { mutations++; throw new Error('This test must never generate, upload or schedule') }
  const dependencies = {
    ...vue, useRoute, useRouter, useWizardHistory, ...businessIds, ...businessTimes, ...evidence, digestTemplatesFor, templateGenerationError, resolveBasketSelection, allocateReportWords, cleanResultMeta,
    usePortalStore: () => store, PortalPageHeader: {}, PortalEmptyState: {}, DigestScheduleDialog: {}, DigestScreeningRules: {}, screeningRulesError, ResearchChapterPrompt: {}, PersonalTemplateDialog: {},
    ElMessage: Object.fromEntries(['success', 'warning', 'error'].map(level => [level, text => messages.push({ level, text })])),
    ...Object.fromEntries(['ArrowLeft', 'Check', 'Close', 'Delete', 'Plus', 'Rank', 'Search', 'UploadFilled', 'Refresh', 'Warning'].map(icon => [icon, {}])),
    getPipelineIntelligenceDetail: async id => ({ data: article(id) }),
    getPipelineKnowledgeDocument: async id => ({ data: material(id) }),
    getPipelineResearchJob: async () => ({ data: {} }),
    getPipelineContentFilters: async () => ({ data: { articleCategories: ['后台类别'] } }),
    searchPipelineIntelligence: async () => ({ data: { rows: [], total: 0 } }),
    startPipelineDigestScreening: async () => screeningStart(),
    advancePipelineDigestScreening: async () => screeningResult([screenedArticle('504')]),
    searchPipelineResearchMaterials: async () => ({ data: { rows: [], total: 0 } }),
    listPipelineTemplates: async () => ({ data: { rows: [{ templateKey: '100', modelId: 1, modelConfigured: true, name: '已发布模板', reportType: name === 'DigestCreateView' ? 'weekly' : 'research-demand', digestCadence: name === 'DigestCreateView' ? 'weekly' : null, version: 'V4', sections: [{ id: 1, title: '实际章节', words: 1000 }] }] } }),
    createPipelineResearchJob: forbidden, createPipelineTemplate: forbidden, createPipelineDigestSchedule: forbidden, uploadPipelineKnowledgeDocument: forbidden, reparsePipelineKnowledgeDocument: forbidden,
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
  // Evidence scenarios use completed task parameters and an explicit weekly period.
  // Blank first-step validation is exercised separately in research-digest-workflow.test.js.
  if (name === 'ResearchCreateView') {
    page.form.project = '选材契约测试报告'
  } else {
    page.form.period = [new Date(2026, 9, 13), new Date(2026, 9, 19)]
  }
  await settle()
  return { get page() { return page }, store, router, messages, get mutations() { return mutations }, close: () => app.unmount() }
}

test('mounted research wizard validates parameters before template and evidence steps, then submits the edited outline contract', async () => {
  const templates = ['research-demand', 'technology-route', 'project-demand'].flatMap((reportType, index) =>
    [0, 1].map(offset => ({ id: String(200 + index * 2 + offset), purpose: 'research', reportType,
      modelId: 1, modelConfigured: true, version: 'V5', name: `${reportType}-${offset}`,
      sections: [{ id: 1, title: '模板章节', words: 1000, description: '模板描述' }] })))
  const ctx = await mount('ResearchCreateView', { basket: [article('111')], api: {
    listPipelineTemplates: async () => ({ data: { rows: templates } })
  } })
  try {
    ctx.page.form.project = ''
    ctx.page.nextStep()
    assert.equal(ctx.page.activeStep.value, 0)
    assert.equal(ctx.page.nextStepBlocked.value, true)
    ctx.page.form.project = '管道检测任务'
    ctx.page.form.reportType = 'technology-route'
    await settle()
    ctx.page.nextStep()
    assert.equal(ctx.page.activeStep.value, 1)
    assert.equal(ctx.page.availableReportTemplates.value.length, 2)
    ctx.page.form.template = '203'
    await settle()
    ctx.page.nextStep()
    assert.equal(ctx.page.activeStep.value, 2)
    await ctx.page.verifySelected()
    ctx.page.nextStep()
    assert.equal(ctx.page.activeStep.value, 3)
    ctx.page.outline.value[0].words = 1800
    ctx.page.outline.value[0].description = '用户补充的分析边界'
    const payload = ctx.page.buildResearchPayload()
    assert.equal(payload.reportType, 'technology-route')
    assert.equal(payload.templateId, '203')
    assert.equal(payload.templateVersion, 'V5')
    assert.equal(payload.outline[0].words, 1800)
    assert.equal(payload.outline[0].description, '用户补充的分析边界')
    assert.deepEqual(payload.selectedItemIds, ['111'])
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('digest preloads template rules and starts only with the current prompt', async () => {
  const calls = []
  const ctx = await mount('DigestCreateView', { api: {
    listPipelineTemplates: async () => ({ data: { rows: [
      { id: '201', name: '专题周报', purpose: 'digest', digestCadence: 'weekly', screeningPrompt: '本期检测技术' }
    ], defaultScreeningPrompt: '系统规则' } }),
    startPipelineDigestScreening: async data => { calls.push(data); return screeningStart() }
  } })
  try {
    assert.equal(ctx.page.screeningPrompt.value, '系统规则')
    ctx.page.form.templateId = '201'
    assert.equal(ctx.page.screeningPrompt.value, '本期检测技术')
    ctx.page.screeningPrompt.value = ' 只纳入技术落地报道 '
    await settle()
    assert.equal(calls.length, 0)
    await screenWeekly(ctx.page)
    assert.equal(calls[0].screeningPrompt, '只纳入技术落地报道')
    assert.equal(calls[0].templateId, '201')
    for (const field of ['sources', 'keywords', 'directions']) assert.equal(Object.hasOwn(calls[0], field), false)
    ctx.page.form.templateId = ''
    assert.equal(ctx.page.screeningPrompt.value, '系统规则')
    assert.equal(ctx.page.screeningRows.value, null)
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('only explicit save-as creates a reusable digest template and selects the returned copy', async () => {
  const base = { id: '201', purpose: 'digest', name: '原模板', digestCadence: 'all', prompt: '原正文要求', screeningPrompt: '原通用要求', screeningCategories: [] }
  const calls = []
  const ctx = await mount('DigestCreateView', { api: {
    listPipelineTemplates: async () => ({ data: { rows: [base], defaultWritingPrompts: { monthly: '系统月报正文要求' }, defaultScreeningPrompt: '系统通用要求' } }),
    createPipelineTemplate: async body => {
      calls.push(body)
      if (calls.length === 1) throw Error('保存失败')
      return { data: { ...body, id: String(300 + calls.length) } }
    }
  } })
  try {
    const page = ctx.page
    page.form.type = '月报'
    page.form.templateId = base.id
    const rules = [{ name: '方向二', prompt: '现场数据' }, { name: '方向一', prompt: '公开试验' }]
    page.screeningCategories.value = rules
    page.screeningPrompt.value = ' 仅收录新进展 '
    page.openSaveTemplate()
    page.saveDialogOpen.value = false
    await page.refreshPreview()
    await page.saveAsTemplate()
    assert.equal(calls.length, 0)
    page.openSaveTemplate()
    page.newTemplateName.value = ' 月报副本 '
    await page.saveAsTemplate()
    assert.equal(page.saveDialogOpen.value, true)
    assert.equal(page.form.templateId, base.id)
    assert.match(page.saveTemplateError.value, /保存失败/)
    await Promise.all([page.saveAsTemplate(), page.saveAsTemplate()])
    assert.equal(calls.length, 2)
    assert.deepEqual(calls[1], { name: '月报副本', purpose: 'digest', digestCadence: 'monthly', isEnabled: true,
      description: '', prompt: base.prompt, screeningPrompt: '仅收录新进展', screeningCategories: rules })
    assert.equal(page.saveDialogOpen.value, false)
    assert.equal(page.form.templateId, '302')
    assert.deepEqual(page.screeningCategories.value, rules)
    assert.equal(page.screeningPrompt.value, '仅收录新进展')
    assert.equal(page.screeningId.value, '')
    assert.deepEqual(base.screeningCategories, [])
    assert.equal(base.screeningPrompt, '原通用要求')
    page.form.templateId = ''
    page.openSaveTemplate()
    page.newTemplateName.value = '基于系统模板'
    await page.saveAsTemplate()
    assert.equal(calls.at(-1).prompt, '系统月报正文要求')
    assert.equal(calls.at(-1).screeningPrompt, '系统通用要求')
  } finally { ctx.close() }
})

test('digest submits all ordered categories together and discards stale results when their rules change', async () => {
  const templateRules = [{ name: '检测技术', prompt: '检测方法有新进展' }, { name: '工程应用', prompt: '工程试点已落地' }]
  const calls = []
  const ctx = await mount('DigestCreateView', { api: {
    listPipelineTemplates: async () => ({ data: { rows: [], defaultScreeningCategories: templateRules } }),
    startPipelineDigestScreening: async data => { calls.push(data); return screeningStart(3) },
    advancePipelineDigestScreening: async () => screeningResult([
      screenedArticle('111'), screenedArticle('112', true, { category: '工程应用' }), screenedArticle('113', false)
    ])
  } })
  const page = ctx.page
  try {
    page.screeningCategories.value = [templateRules[1], templateRules[0]]
    await screenWeekly(page)
    assert.deepEqual(calls.map(call => call.screeningCategories), [[templateRules[1], templateRules[0]]])
    assert.deepEqual(page.categoryCounts.value, [{ name: '工程应用', count: 1 }, { name: '检测技术', count: 1 }])
    assert.deepEqual(page.passedRows.value.map(row => row.id), ['111', '112'])
    assert.equal(page.buildDigestPayload().screeningPrompt, null)
    page.screeningCategories.value = [templateRules[0], { name: '检测技术', prompt: '另一规则' }]
    assert.equal(page.canStart.value, false)
    assert.equal(page.screeningId.value, '')
    page.resetRules()
    assert.deepEqual(page.screeningCategories.value, templateRules)
    assert.equal(page.canStart.value, true)
  } finally { ctx.close() }
})


test('digest can use the system default without selecting a personal template', async () => {
  let payload
  const ctx = await mount('DigestCreateView', { api: {
    listPipelineTemplates: async () => ({ data: { rows: [], defaultScreeningPrompt: '保留本期进展', defaultScreeningCategories: [] } }),
    createPipelineResearchJob: async data => { payload = data; return { data: { jobId: '900' } } }
  } })
  try {
    await screenWeekly(ctx.page)
    await ctx.page.createDigest()
    assert.equal(payload.reportType, 'weekly')
    assert.equal(payload.screeningPrompt, null)
    assert.equal(Object.hasOwn(payload, 'materials'), false)
    assert.equal(Object.hasOwn(payload, 'selectedItemIds'), false)
    for (const field of ['templateId', 'templateVersion', 'outline', 'templatePrompt', 'template_prompt']) {
      assert.equal(Object.hasOwn(payload, field), false)
    }
    assert.ok(ctx.messages.some(item => item.level === 'success' && item.text.includes('任务已进入后台生成队列')))
  } finally { ctx.close() }
})

test('NULL model templates stay selectable and research submission makes no generation request', async () => {
  const ctx = await mount('ResearchCreateView', { api: {
    listPipelineTemplates: async () => ({ data: { rows: [{ id: '101', name: '待配置模板', purpose: 'research', reportType: 'research-demand', modelId: null, modelConfigured: false, sections: [] }] } })
  } })
  try {
    assert.equal(ctx.page.selectedTemplate.value.id, '101')
    assert.equal(ctx.page.nextStepBlocked.value, false)
    await ctx.page.submitTask()
    assert.equal(ctx.mutations, 0)
    assert.ok(ctx.messages.some(item => item.text.includes('未配置可用的文本生成模型')))
  } finally { ctx.close() }
})

test('digest displays backend model configuration errors and preserves selected evidence for retry', async () => {
  let attempts = 0
  const ctx = await mount('DigestCreateView', { api: {
    createPipelineResearchJob: async () => { attempts++; throw { msg: '请先配置简报生成模型' } }
  } })
  try {
    await screenWeekly(ctx.page)
    ctx.page.form.summaryLength = 'short'
    await ctx.page.createDigest()
    assert.equal(attempts, 1)
    assert.deepEqual(ctx.page.passedRows.value.map(row => row.id), ['504'])
    assert.equal(ctx.page.form.summaryLength, 'short')
    assert.equal(ctx.page.submitting.value, false)
    assert.ok(ctx.messages.some(item => item.level === 'error' && item.text === '请先配置简报生成模型'))
    assert.equal(ctx.page.buildDigestPayload().screeningPrompt, null)
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

test('research checkbox selections are idempotent, removable and locked during submission', async () => {
  const ctx = await mount('ResearchCreateView')
  try {
    const toggle = ctx.page.toggleMaterial
    const selected = ctx.page.selectedIds
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
    assert.doesNotMatch(sources.ResearchCreateView, /<el-checkbox v-model="selectedIds"/)
  } finally { ctx.close() }
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
    assert.equal(ctx.page.form.project, '新任务')
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

test('manual digest generation switches cadence without schedule configuration', async () => {
  const ctx = await mount('DigestCreateView')
  try {
    for (const [frequency, type] of [
      ['weekly', '周报'], ['monthly', '月报']
    ]) {
      ctx.page.form.type = type
      await vue.nextTick()
      assert.equal(ctx.page.form.type, type)
      assert.equal(ctx.page.currentTypeConfig.value.reportType, frequency)
    }
    assert.equal(Object.hasOwn(ctx.page.form, 'schedule'), false)
    assert.equal(ctx.mutations, 0)
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

test('digest waits for every automatic screening batch and submits its receipt with all approved articles', async () => {
  const rows = [...Array.from({ length: 11 }, (_, i) => screenedArticle(`${701 + i}`)), screenedArticle('999', false)]
  const lastBatch = later()
  let batches = 0
  const ctx = await mount('DigestCreateView', { api: {
    startPipelineDigestScreening: async () => screeningStart(rows.length),
    advancePipelineDigestScreening: () => ++batches === 1
      ? Promise.resolve({ data: { screeningId, total: rows.length, processed: 8 } })
      : lastBatch.promise
  } })
  try {
    const screening = screenWeekly(ctx.page)
    await settle()
    assert.equal(ctx.page.screeningProcessed.value, 8)
    assert.equal(ctx.page.passedRows.value.length, 0)
    assert.equal(ctx.page.refreshing.value, true)
    lastBatch.resolve(screeningResult(rows))
    await screening
    assert.deepEqual(ctx.page.passedRows.value[0].tags, ['管道检测'])
    assert.equal(ctx.page.screeningRows.value.length, rows.length)
    assert.equal(ctx.page.passedRows.value.length, 11)
    assert.equal(ctx.page.canGenerate.value, true)
    const payload = ctx.page.buildDigestPayload()
    assert.equal(Object.hasOwn(payload, 'materials'), false)
    assert.equal(Object.hasOwn(payload, 'selectedItemIds'), false)
    assert.equal(payload.screeningPrompt, null)
    assert.equal(batches, 2)
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})


test('digest scope changes invalidate old classifications and reject late batch responses', async () => {
  const old = later()
  let calls = 0
  const ctx = await mount('DigestCreateView', { api: {
    advancePipelineDigestScreening: () => ++calls === 1 ? old.promise : Promise.resolve(screeningResult([screenedArticle('125')]))
  } })
  try {
    const first = screenWeekly(ctx.page)
    await settle()
    ctx.page.screeningPrompt.value = '新的筛选规则'
    await ctx.page.refreshPreview()
    old.resolve(screeningResult([screenedArticle('120')]))
    await first
    assert.deepEqual(ctx.page.passedRows.value.map(item => item.id), ['125'])
    ctx.page.screeningPrompt.value = '再次修改筛选规则'
    assert.equal(ctx.page.screeningId.value, '')
    assert.equal(ctx.page.passedRows.value.length, 0)
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})


test('digest detail fetch failures surface the affected article and revoke reason', async () => {
  await assert.rejects(() => evidence.fetchDigestPage({ period: ['2026-10-13'], sources: ['新闻网站'], directions: [], keywords: [] }, {
    search: async () => ({ data: { rows: [{ id: '108' }], total: 1 } }), getIntelligence: async () => { throw { msg: '已撤权' } }
  }, 1), /108.*已撤权/)
})

test('digest cannot advance with missing template rules after a catalog failure', async () => {
  let failed = true, screenings = 0
  const ctx = await mount('DigestCreateView', { api: {
    listPipelineTemplates: async () => {
      if (failed) throw { msg: '模板读取失败' }
      return { data: { rows: [] } }
    },
    startPipelineDigestScreening: async () => { screenings++; return screeningStart() }
  } })
  try {
    assert.equal(ctx.page.canStart.value, false)
    ctx.page.confirmGeneration()
    await settle()
    assert.equal(ctx.page.activeStep.value, 0)
    assert.equal(screenings, 0)
    failed = false
    await ctx.page.loadTemplates()
    assert.equal(ctx.page.canStart.value, true)
  } finally { ctx.close() }
})

test('digest submission error preserves authored screening rules and clears submitting state', async () => {
  let creates = 0
  const ctx = await mount('DigestCreateView', { api: {
    createPipelineResearchJob: async () => { creates++; throw { msg: '请先配置简报生成模型' } }
  } })
  try {
    ctx.page.screeningPrompt.value = '仅保留新的工程试验'
    await ctx.page.createDigest()
    assert.equal(creates, 1)
    assert.equal(ctx.page.screeningPrompt.value, '仅保留新的工程试验')
    assert.equal(ctx.page.submitting.value, false)
    assert.ok(ctx.messages.some(item => item.level === 'error' && item.text === '请先配置简报生成模型'))
  } finally { ctx.close() }
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
  const ctx = await mount('DigestCreateView', { api: { startPipelineDigestScreening: async params => { calls.push(params); return screeningStart() } } })
  try {
    const before = calls.length
    ctx.page.form.period = []
    await settle()
    assert.equal(calls.length, before)
    assert.deepEqual(ctx.page.buildReportPeriod().period, [])
    assert.equal(ctx.page.previewError.value, '')
    assert.equal(ctx.page.passedRows.value.length, 0)
    ctx.page.form.type = '周报'
    ctx.page.form.period = [new Date(2027, 0, 2), new Date(2026, 11, 31)]
    await ctx.page.refreshPreview()
    assert.equal(calls.length, before)
    assert.equal(ctx.page.previewError.value, '')
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('digest late requests after unmount cannot publish candidates', async () => {
  const response = later()
  const ctx = await mount('DigestCreateView', { api: { advancePipelineDigestScreening: () => response.promise } })
  const pending = screenWeekly(ctx.page)
  await settle()
  ctx.close()
  response.resolve(screeningResult([screenedArticle('136')]))
  await pending
  await settle()
  assert.equal(ctx.page.passedRows.value.length, 0)
  assert.equal(ctx.mutations, 0)
})

test('stale template IDs warn without replacing authored text or outline on template reload', async () => {
  const ctx = await mount('ResearchCreateView', { query: { template: 'template-01' } })
  try {
    ctx.page.form.requirements = '用户输入的需求正文'
    ctx.page.form.project = '用户填写标题'
    ctx.page.outline.value = [{ id: 1, title: '用户编辑章节', content: '用户章节正文', words: 1000 }]
    await ctx.page.loadTemplates()
    await settle()
    assert.equal(ctx.page.form.template, 'template-01')
    assert.match(ctx.page.templateUpgradeNotice.value, /编号已升级/)
    assert.equal(ctx.page.form.requirements, '用户输入的需求正文')
    assert.equal(ctx.page.form.project, '用户填写标题')
    assert.equal(ctx.page.outline.value[0].content, '用户章节正文')
    await ctx.page.submitTask()
    assert.equal(ctx.mutations, 0)
    assert.ok(ctx.messages.some(item => item.text.includes('编号已升级')))
  } finally { ctx.close() }
})

test('digest copy restores a screening prompt but never submits a stale writing prompt or outline', async () => {
  let catalogCalls = 0
  const ctx = await mount('DigestCreateView', { query: { template: 'old-template-uuid', sourceTask: '77' }, api: {
    listPipelineTemplates: async params => {
      catalogCalls++
      assert.equal(params.category, 'digest')
      return { data: { rows: [{ id: '9007199254740993', purpose: 'digest', digestCadence: 'weekly' }] } }
    },
    getPipelineResearchJob: async () => ({ data: { type: 'weekly', screeningPrompt: '仅纳入创新进展', config: {
      templateId: '9007199254740993', template_prompt: '旧模板中的提示词', outline: [{ title: '旧章节' }],
      period: ['2026-10-13', '2026-10-19'], keywords: [], options: { summaryLength: 'short' }
    } } }),
  } })
  try {
    await ctx.page.loadSourceTask()
    await settle()
    const payload = ctx.page.buildDigestPayload()
    assert.equal(payload.screeningPrompt, '仅纳入创新进展')
    assert.equal(Object.hasOwn(payload, 'materials'), false)
    assert.equal(Object.hasOwn(payload, 'selectedItemIds'), false)
    assert.equal(ctx.page.screeningPrompt.value, '仅纳入创新进展')
    assert.equal(payload.options.summaryLength, 'short')
    assert.equal(Object.hasOwn(ctx.page.form, 'template'), false)
    assert.equal(payload.templateId, '9007199254740993')
    for (const field of ['templateVersion', 'outline', 'templatePrompt', 'template_prompt']) {
      assert.equal(Object.hasOwn(payload, field), false)
    }
    await ctx.router.replace({ path: '/create', query: { template: 'another-old-template-uuid', sourceTask: '77' } })
    await settle()
    assert.equal(ctx.page.buildDigestPayload().screeningPrompt, '仅纳入创新进展')
    assert.equal(catalogCalls, 1)
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})

test('research generation selects the real large decimal template ID without hardcoded fallbacks', async () => {
  for (const name of ['ResearchCreateView']) {
    const id = '9007199254740993'
    const ctx = await mount(name, { api: {
      listPipelineTemplates: async () => ({ data: { rows: [{ id, name: '真实模板编号', purpose: name === 'DigestCreateView' ? 'digest' : 'research', reportType: name === 'DigestCreateView' ? 'digest' : 'research-demand', digestCadence: name === 'DigestCreateView' ? 'weekly' : null, modelId: null, modelConfigured: false, sections: [] }] } })
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

test('research legacy template queries never select a replacement and retain user input on same-page navigation', async () => {
  for (const name of ['ResearchCreateView']) {
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

test('digest Back and Forward preserve the confirmation step without submitting', async () => {
  const ctx = await mount('DigestCreateView')
  try {
    ctx.page.confirmGeneration()
    await settle()
    assert.equal(ctx.page.activeStep.value, 1)
    ctx.page.advanceStep()
    assert.equal(ctx.page.activeStep.value, 1)
    ctx.page.goBack()
    await settle()
    assert.equal(ctx.page.activeStep.value, 0)
    ctx.router.forward()
    await settle()
    assert.equal(ctx.page.activeStep.value, 1)
    assert.equal(ctx.mutations, 0)
  } finally { ctx.close() }
})


test('weekly and monthly submit directly to the background generation queue', async () => {
  for (const type of ['周报', '月报']) {
    const created = []
    const ctx = await mount('DigestCreateView', { api: {
      createPipelineResearchJob: async payload => { created.push(payload); return { data: { jobId: '432' } } }
    } })
    const page = ctx.page
    try {
      page.form.type = type
      await settle()
      page.confirmGeneration()
      await settle()
      assert.equal(page.activeStep.value, 1)
      assert.equal(page.canGenerate.value, true)
      page.form.summaryLength = 'long'
      await page.createDigest()
      assert.equal(created.length, 1)
      assert.equal(created[0].reportType, type === '周报' ? 'weekly' : 'monthly')
      assert.equal(created[0].options.summaryLength, 'long')
      assert.equal(Object.hasOwn(created[0], 'selectedItemIds'), false)
      assert.equal(Object.hasOwn(created[0], 'screeningId'), false)
    } finally { ctx.close() }
  }
})


test('confirmation stays on the second step and generation waits for submission', async () => {
  const created = []
  const ctx = await mount('DigestCreateView', { api: {
    createPipelineResearchJob: async payload => { created.push(payload); return { data: { jobId: '433' } } }
  } })
  try {
    ctx.page.confirmGeneration()
    await settle()
    assert.equal(ctx.page.activeStep.value, 1)
    assert.equal(ctx.page.canGenerate.value, true)
    await ctx.page.createDigest()
    assert.equal(created.length, 1)
  } finally { ctx.close() }
})
