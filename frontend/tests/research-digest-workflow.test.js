import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import * as ids from '../src/utils/portal/businessId.js'
import * as times from '../src/utils/portal/businessTime.js'
import { templatePreview } from '../src/utils/portal/researchWorkspace.js'
import { templateGenerationError } from '../src/utils/pipeline/compactContract.js'
import { cleanReportCitationNotes, reportCitationParts } from '../src/utils/portal/reportDocument.js'
import { newScheduleForm, readScheduleForm, schedulePayload, scheduleSummary } from '../src/utils/portal/digestScheduleEditor.js'

const read = name => readFileSync(new URL(`../src/views/portal/${name}.vue`, import.meta.url), 'utf8')
function setup(name, expose, overrides = {}) {
  const scope = effectScope(), callbacks = []
  let writes = 0
  const write = () => { writes++; throw Error('unexpected write') }
  const selection = { selectedIds: ref([]), selectedMaterials: ref([]), verifying: ref(false), problems: ref([]), setHint() {}, setSelection() {}, verifySelected: async () => true, refreshEvidence() {} }
  const store = { workspaceEpoch: 1, digestReports: [], tasks: [], sectionErrors: {}, basket: [], hydrate: async () => {} }
  const context = vm.createContext({
    Date, computed, reactive, ref, watch, nextTick, ...ids, ...times, templatePreview, templateGenerationError,
    cleanReportCitationNotes, reportCitationParts, newScheduleForm, readScheduleForm, schedulePayload, scheduleSummary,
    onMounted() {}, onBeforeUnmount(fn) { callbacks.push(fn) }, onBeforeRouteLeave() {}, onBeforeRouteUpdate() {},
    useRoute: () => reactive({ query: {}, params: { id: '41' } }), useRouter: () => ({ push() {} }), usePortalStore: () => store,
    ElMessage: { warning() {}, success() {}, error() {}, info() {} }, ElMessageBox: { confirm: write },
    useEvidenceSelection: () => selection,
    searchPipelineResearchMaterials: async () => ({ data: { rows: [], total: 0 } }),
    getPipelineIntelligenceDetail() {}, getPipelineKnowledgeDocument() {}, getToken: () => 'mock',
    getCitationPath: () => '', DIGEST_SELECTION_LIMIT: 50,
    createPipelineResearchJob: write, updatePipelineResearchReport: write, finalizePipelineResearchReport: write,
    createPipelineDigestSchedule: write, savePipelineDigestScheduleConfig: write,
    updatePipelineDigestSchedule: write, runPipelineDigestSchedule: write, deletePipelineDigestSchedule: write,
    setTimeout: () => 1, clearTimeout() {}, window: { removeEventListener() {} },
    ...overrides
  })
  const script = read(name).split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
  scope.run(() => vm.runInContext(`${script}\nglobalThis.view = { ${expose} }`, context))
  return { ...context.view, selection, writes: () => writes, close() { callbacks.forEach(fn => fn()); scope.stop() } }
}
const reportTypes = ['research-demand', 'technology-route', 'project-demand']
const templates = reportTypes.flatMap((reportType, index) => [0, 1].map(n => ({
  id: String(31 + index * 2 + n), purpose: 'research', reportType, name: `${reportType}-${n}`, version: 'V3', modelId: '10',
  sections: [{ id: 1, title: '章节', words: 1200, description: '原始要求', required: true }]
})))
test('wizard starts with task parameters, keeps multiple real templates per type, and submits edited outline with original fields', async () => {
  const v = setup('pages/ResearchCreateView', 'form, activeStep, nextStepBlocked, nextStep, outline, totalWords, loadTemplates, availableReportTemplates, buildResearchPayload', {
    listPipelineTemplates: async () => ({ data: { rows: templates } })
  })
  try {
    assert.equal(v.activeStep.value, 0)
    assert.equal(v.nextStepBlocked.value, true)
    v.nextStep(); assert.equal(v.activeStep.value, 0)
    v.form.projectDescription = '生产中需要研究腐蚀检测的适用边界'; v.form.project = '测试任务'; v.form.keywords = ['自定义词']; v.form.requirements = '按企业规范编制，不得编造结论'
    v.nextStep(); assert.equal(v.activeStep.value, 1)
    await v.loadTemplates(); await nextTick()
    for (const reportType of reportTypes) {
      v.form.reportType = reportType; await nextTick()
      assert.equal(v.availableReportTemplates.value.length, 2)
      v.form.template = v.availableReportTemplates.value[1].id; await nextTick()
      v.outline.value[0].words = 1700; v.outline.value[0].description = '修改后的边界'
      v.selection.selectedIds.value = ['9007199254740993']
      const p = v.buildResearchPayload()
      assert.equal(p.reportType, reportType)
      assert.equal(p.title, '测试任务')
      assert.equal(p.project, p.title)
      assert.equal('direction' in p, false)
      assert.equal(p.projectDescription, '生产中需要研究腐蚀检测的适用边界')
      assert.equal(p.requirements, '按企业规范编制，不得编造结论')
      assert.equal(p.templateId, v.form.template)
      assert.equal(p.templateVersion, 'V3')
      assert.equal(p.outline[0].words, 1700)
      assert.equal(p.outline[0].description, '修改后的边界')
      assert.equal(p.outline[0].required, true)
      assert.equal(p.selectedItemIds[0], '9007199254740993')
      assert.equal(p.keywords[0], '自定义词')
      assert.equal(p.options.publicSupplement, false)
      assert.equal(v.totalWords.value, 1700)
    }
    v.outline.value[0].words = null
    assert.throws(() => v.buildResearchPayload(), /字数/)
    v.form.template = '999'
    assert.throws(() => v.buildResearchPayload(), /模板/)
    assert.equal(v.writes(), 0)
  } finally { v.close() }
})
test('unbound legacy templates are not silently assigned to every report type', async () => {
  const v = setup('pages/ResearchCreateView', 'form, availableReportTemplates, loadTemplates', {
    listPipelineTemplates: async () => ({ data: { rows: [{ ...templates[0], reportType: 'research' }, { ...templates[1], reportType: undefined }] } })
  })
  try {
    await v.loadTemplates()
    for (const type of reportTypes) { v.form.reportType = type; await nextTick(); assert.equal(v.availableReportTemplates.value.length, 0) }
  } finally { v.close() }
})
test('daily creation deep links fall back to weekly and daily payloads and source-task copies are blocked', async () => {
  const v = setup('pages/DigestCreateView', 'form, buildDigestPayload, buildReportPeriod, loadSourceTask, sourceTaskError', {
    useRoute: () => ({ query: { type: '日报', sourceTask: '41' } }),
    getPipelineResearchJob: async () => ({ data: { type: 'daily', config: {} } })
  })
  try {
    assert.equal(v.form.type, '周报')
    v.form.type = '月报'; v.form.month = new Date(2026, 1, 5)
    assert.equal(v.buildReportPeriod().period.join(','), '2026-02-01,2026-02-28')
    v.form.type = '日报'
    assert.throws(() => v.buildDigestPayload(), /仅支持新建周报或月报/)
    await v.loadSourceTask()
    assert.match(v.sourceTaskError.value, /历史日报仅供查阅/)
    assert.equal(v.writes(), 0)
  } finally { v.close() }
})
test('daily historical reports cannot edit, autosave, add evidence or finalize even while still drafts', async () => {
  for (const type of ['daily', '日报']) {
    const v = setup('pages/DigestEditorView', 'loadDigest, digest, sections, isReadOnly, addCandidate, addSection, updateSectionContent, saveVersion, finalizeDigest, saveCurrent', {
      getPipelineResearchReport: async () => ({ data: { id: '41', reportType: type, status: 'draft', sections: [{ id: 1, title: '原栏目', content: '原正文', citationIds: [] }], citations: [] } })
    })
    try {
      await v.loadDigest(); assert.equal(v.isReadOnly.value, true)
      v.addCandidate({ id: '12' }); v.addSection(); v.updateSectionContent({ currentTarget: { innerText: '试图改写' } })
      await v.saveVersion(); await v.finalizeDigest(); await v.saveCurrent({ saveVersion: true })
      assert.equal(v.sections.value.length, 1); assert.equal(v.sections.value[0].content, '原正文')
      assert.equal(v.writes(), 0)
    } finally { v.close() }
  }
})
test('render groups references at the end while preserving authored sections and sentence markers', () => {
  const v = setup('pages/DigestEditorView', 'sections, citations, bodySections, authoredReferences, buildMarkdown')
  try {
    v.sections.value = [{ id: 1, title: '要闻', content: '[2]成果已发布[2]。' }, { id: 2, title: '2. 参考资料', content: '[2] 人工补充的页码和备注' }]
    v.citations.value = [{ id: 2, title: '原来源' }]
    assert.equal(v.bodySections.value.length, 1)
    assert.equal(v.authoredReferences.value, '[2] 人工补充的页码和备注')
    assert.equal(v.sections.value.length, 2)
    assert.ok(v.buildMarkdown().includes('成果已发布[2]。'))
    assert.equal(reportCitationParts('[2]成果已发布[2]。', '要闻', 2).filter(part => part.citation).length, 1)
    assert.doesNotMatch(read('pages/DigestEditorView'), /class="ps-digest-news"/)
  } finally { v.close() }
})
test('legacy daily plans retain history protection and can only be deleted when eligible', async () => {
  const row = { id: '51', name: '日报旧计划', reportType: 'daily', templateId: '31', enabled: true, scheduleTime: '08:00', canDelete: false }
  assert.equal(newScheduleForm().frequency, 'weekly')
  const original = JSON.stringify(row), form = readScheduleForm(row)
  assert.equal(form.frequency, 'daily'); assert.match(scheduleSummary(form), /每天/)
  assert.throws(() => schedulePayload(form, { id: '31', digestCadence: 'all' }), /历史日报计划只读/)
  assert.equal(JSON.stringify(row), original)
  const v = setup('pages/DigestListView', 'runSchedule, toggleSchedule, removeSchedule, tabs')
  try {
    await v.runSchedule(row); await v.toggleSchedule(row); await v.removeSchedule(row)
    assert.equal(v.writes(), 0)
    assert.ok(!v.tabs.includes('历史日报')); assert.ok(!v.tabs.includes('日报'))
  } finally { v.close() }

  const eligible = { ...row, id: '52', enabled: false, canDelete: true }
  const deleted = []
  let confirmed = false
  const deletion = setup('pages/DigestListView', 'removeSchedule, schedules', {
    ElMessageBox: { confirm: async () => { if (!confirmed) throw Error('cancel') } },
    deletePipelineDigestSchedule: async id => { deleted.push(id) },
  })
  try {
    deletion.schedules.value = [row, eligible]
    await deletion.removeSchedule(eligible)
    assert.deepEqual(deleted, [])
    assert.equal(deletion.schedules.value.length, 2)
    confirmed = true
    await deletion.removeSchedule(eligible)
    assert.deepEqual(deleted, ['52'])
    assert.deepEqual(Array.from(deletion.schedules.value, item => item.id), ['51'])
  } finally { deletion.close() }
})
test('all changed Vue files compile and retain scoped styles; citation shading is presentation only', () => {
  for (const name of ['pages/ResearchCreateView', 'pages/DigestCreateView', 'pages/DigestListView', 'pages/DigestEditorView', 'components/DigestScheduleDialog']) {
    const source = read(name), { descriptor, errors } = parse(source)
    assert.deepEqual(errors, [])
    const script = compileScript(descriptor, { id: name })
    assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: name, id: name, compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
    assert.ok(descriptor.styles.every(style => style.scoped))
  }
  assert.match(read('pages/DigestEditorView'), /\.ps-citation-marker \{[^}]*background:/)
  assert.doesNotMatch(read('pages/ResearchCreateView').split('<script setup>')[0], /公开资料补充/)
})

test('wizard selects evidence before templates and model readiness blocks only final generation', async () => {
  const v = setup('pages/ResearchCreateView', 'form, activeStep, nextStepBlocked, finalGenerationError, nextStep, loadTemplates', {
    listPipelineTemplates: async () => ({ data: { rows: [{ ...templates[0], modelId: null, modelConfigured: false }] } })
  })
  try {
    await v.loadTemplates(); await nextTick()
    v.form.project = '真实项目'
    assert.equal(v.nextStepBlocked.value, false)
    v.nextStep(); assert.equal(v.activeStep.value, 1)
    assert.equal(v.nextStepBlocked.value, true)
    v.selection.selectedIds.value = ['101']
    assert.equal(v.nextStepBlocked.value, false)
    v.nextStep(); assert.equal(v.activeStep.value, 2)
    assert.equal(v.nextStepBlocked.value, false)
    v.nextStep(); assert.equal(v.activeStep.value, 3)
    assert.ok(v.finalGenerationError.value)
    assert.equal(v.writes(), 0)
  } finally { v.close() }
})

test('copied research tasks restore project descriptions from API naming styles or a legacy research direction', async () => {
  for (const descriptionKey of ['projectDescription', 'project_description', 'direction']) {
    const v = setup('pages/ResearchCreateView', 'form, loadSourceTask', {
      getPipelineResearchJob: async () => ({ data: { title: '原报告', config: { project: '原项目', [descriptionKey]: '原项目背景与待研究问题' } } })
    })
    try {
      await v.loadSourceTask('41')
      assert.equal(v.form.project, '原项目')
      assert.equal(v.form.projectDescription, '原项目背景与待研究问题')
      assert.equal(v.writes(), 0)
    } finally { v.close() }
  }
})
