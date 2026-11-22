import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as vue from 'vue'
import { renderToString } from 'vue/server-renderer'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { getCitationPath } from '../src/utils/portal/citationRouting.js'
import { buildPersonalReports, hasReportOutput } from '../src/utils/portal/personalReports.js'
import { cleanReportCitationNotes } from '../src/utils/portal/reportDocument.js'

const page = name => readFileSync(new URL(`../src/views/portal/pages/${name}.vue`, import.meta.url), 'utf8')
// Exercise the actual setup functions with isolated dependencies; never import API wrappers.
function action(pageName, name, dependencies = {}) {
  const script = page(pageName).split('<script setup>')[1].split('</script>')[0]
  const start = script.search(new RegExp(`(?:async )?function ${name}\\(`))
  assert.ok(start >= 0, `${name} exists`)
  const rest = script.slice(start)
  const firstLine = rest.split('\n')[0]
  const source = firstLine.endsWith('}') ? firstLine : rest.slice(0, rest.indexOf('\n}') + 2)
  return new Function(...Object.keys(dependencies), `return (${source})`)(...Object.values(dependencies))
}
const messages = () => ({ warning() {}, success() {}, error() {}, info() {} })

test('digest section source counts use resolved citation associations, not stale cached counts', () => {
  const resolve = action('DigestEditorView', 'sectionSources', { citations: { value: [{ id: 1 }, { id: '2' }] } })
  assert.equal(resolve({ sources: 0, citationIds: ['1', 2, 2, 'missing'] }).length, 2)
  assert.equal(resolve({ sources: 99 }).length, 0)
  assert.match(page('DigestEditorView'), /sectionSources\(section\)\.length/)
})

test('G01: fixed-format digest payload accepts weekly and monthly without any template or outline', () => {
  const form = { type: '周报', directions: ['油气管网'], keywords: ['检测'], sources: ['新闻网站'],
    itemCount: 10, summaryLength: 'normal', hotAnalysis: true, duplicateMerge: true }
  const build = action('DigestCreateView', 'buildDigestPayload', { form,
    canGenerate: { value: true }, screeningPromptOverride: { value: null }, categoryOverride: { value: null },
    refreshing: { value: false }, previewError: { value: '' }, sourceTaskLoading: { value: false }, sourceTaskError: { value: '' },
    currentTypeConfig: { get value() { return { reportType: form.type === '周报' ? 'weekly' : 'monthly' } } },
    buildReportPeriod: () => ({ period: ['2026-10-01', '2026-10-31'], label: '测试周期' }),
    periodFieldLabel: { value: '报告周期' }, requireBusinessId: id => id
  })
  for (const [type, reportType] of [['周报', 'weekly'], ['月报', 'monthly']]) {
    form.type = type
    const payload = build()
    assert.equal(payload.reportType, reportType)
    assert.equal(Object.hasOwn(payload, 'materials'), false)
    assert.equal(Object.hasOwn(payload, 'selectedItemIds'), false)
    assert.equal(payload.screeningPrompt, null)
    assert.equal(payload.screeningCategories, null)
    for (const field of ['templateId', 'templateVersion', 'outline', 'templatePrompt']) assert.equal(Object.hasOwn(payload, field), false)
  }
  form.type = '日报'
  assert.throws(build, /仅支持新建周报或月报/)
})

test('G05: report UI no longer offers historical version or restore operations', () => {
  const source = page('ReportEditorView')
  assert.doesNotMatch(source, /restorePipelineResearchReportVersion|function restoreVersion|版本记录|版本对比/)
  assert.match(source, /保存修改/)
  assert.match(source, /expectedRevision: report\.value\.revision/)
})

for (const status of ['queued', 'running', 'failed', 'dead_letter', 'cancelled']) {
  test(`G06: empty placeholder merges with ${status} task without an output link`, () => {
    const rows = buildPersonalReports({ userId: 7, reports: [{ id: '12', ownerId: 7, content: '', status: 'planned' }], tasks: [{ id: '13', reportId: '12', status }] })
    assert.equal(rows.length, 1)
    assert.equal(rows[0].hasOutput, false)
    assert.equal(rows[0].kind, 'task')
    assert.equal(rows[0].path, '/portal/research/tasks/13')
    assert.notEqual(rows[0].statusLabel, '已生成')
  })
}
test('G06: orphan empty report is unavailable; published content and failed retry remain visible', () => {
  const empty = buildPersonalReports({ userId: 7, reports: [{ id: '12', ownerId: 7, content: ' ' }] })[0]
  assert.equal(empty.hasOutput, false)
  assert.equal(empty.path, '')
  const rows = buildPersonalReports({ userId: 7, reports: [{ id: '12', ownerId: 7, content: '正文', status: 'published' }], tasks: [{ id: '13', reportId: '12', status: 'failed' }] })
  assert.equal(rows.length, 2)
  assert.equal(rows.find(row => row.kind === 'report').statusLabel, '已发布')
})

test('G06: digest list empty rows route to generation record and cannot export', async () => {
  const state = action('DigestListView', 'digestReportState', {
    hasReportOutput, portalStore: { tasks: [{ id: '13', reportId: '12', status: 'failed' }] },
  })({ id: '12', content: '', status: '草稿' })
  assert.equal(state.hasOutput, false)
  assert.equal(state.path, '/portal/research/tasks/13')
  assert.equal(state.status, '生成失败')
  let calls = 0
  await action('DigestListView', 'exportDigest', {
    hasReportOutput, ElMessage: messages(), exportingId: { value: '' },
    exportPipelineResearchReport: async () => { calls++; throw Error('must not call') },
  })({ id: '12', content: '' })
  assert.equal(calls, 0)
})

test('G06: completed task linked to an explicitly empty report stays a task, never an output', () => {
  const rows = buildPersonalReports({ userId: 7, reports: [{ id: '12', ownerId: 7, content: '' }], tasks: [{ id: '13', reportId: '12', status: 'completed' }] })
  assert.equal(rows.length, 1)
  assert.equal(rows[0].kind, 'task')
  assert.equal(rows[0].hasOutput, false)
})

test('G06: task output entry requires a completed task and recorded report output', () => {
  const canOpen = action('ResearchTaskView', 'canOpenTaskReport')
  assert.equal(canOpen({ reportId: '12', status: 'running', reportStatus: 'draft' }), false)
  assert.equal(canOpen({ reportId: '12', status: 'completed', reportStatus: 'draft' }), false)
  assert.equal(canOpen({ reportId: '12', status: 'completed' }), false)
  assert.equal(canOpen({ reportId: '12', status: 'completed', reportStatus: 'completed' }), true)
})

test('G09: object sources render readable fields and missing quotes never overwrite authored text', () => {
  const label = action('DigestEditorView', 'citationSourceLabel')
  assert.equal(label({ source: { name: '管网新闻', url: 'https://example.org' } }), '管网新闻')
  assert.equal(label({ source: '期刊' }), '期刊')
  assert.equal(label({ source: {}, type: 'paper' }), 'paper')
  for (const sources of [[], [{ id: 1, title: '来源', source: {} }], [{ id: 1, quote: '有效' }, { id: 2, quote: ' ' }]]) {
    const currentSection = { value: { content: '保留的手写正文', words: 7 } }
    let saves = 0
    action('DigestEditorView', 'rebuildSection', { isReadOnly: { value: false }, currentSection,
      currentSectionSources: { value: sources }, markSaving: () => saves++, ElMessage: messages() })()
    assert.equal(currentSection.value.content, '保留的手写正文')
    assert.equal(saves, 0)
  }
})

test('digest serialization keeps sentence-final citations and readable object sources without HTML', () => {
  const content = action('DigestEditorView', 'buildMarkdown', {
    digest: { value: { title: '简报' } }, referenceDigest: { value: false },
    sections: { value: [{ title: '本期要闻', content: '[1]研究显示可行[1]。另一结论[1]。' }] },
    citations: { value: [{ id: 1, title: '研究资料', source: { name: '来源机构' } }] },
    cleanReportCitationNotes, citationSourceLabel: action('DigestEditorView', 'citationSourceLabel'),
  })()
  assert.match(content, /研究显示可行\[1\]。另一结论\[1\]。/)
  assert.match(content, /\[1\] 研究资料（来源机构，来源条目）/)
  assert.doesNotMatch(content, /\[object Object\]|<sup/)
})

test('G10: removing one citation removes its markers and association without touching other references or links', () => {
  const currentSection = { value: { citationIds: [1, '11', 2], content: '甲[1][11]。乙[2]。链接[1](https://example.org)。代码 `[1]`。' } }
  action('DigestEditorView', 'removeSource', { isReadOnly: { value: false }, currentSection, markSaving() {} })('1')
  assert.deepEqual(currentSection.value.citationIds, ['11', 2])
  assert.equal(currentSection.value.content, '甲[11]。乙[2]。链接[1](https://example.org)。代码 `[1]`。')
  assert.equal(currentSection.value.sources, 2)
  assert.equal(currentSection.value.words, currentSection.value.content.length)
})

test('G11: no pass claim is inferred from empty issues or citation-check configuration', () => {
  assert.doesNotMatch(page('DigestEditorView'), /未发现阻断导出的问题|已完成基础检查|基础质量检查已通过/)
  assert.doesNotMatch(page('ResearchTaskView'), /<dt>引用检查<\/dt>/)
})


async function renderTaskMaterials(type, overrides = {}) {
  const { descriptor } = parse(page('ResearchTaskView'))
  const script = compileScript(descriptor, { id: 'task-materials' })
  const compiled = compileTemplate({ source: descriptor.template.content, id: 'task-materials',
    compilerOptions: { mode: 'function', bindingMetadata: script.bindings } })
  assert.deepEqual(compiled.errors, [])
  const dependencies = { ...vue,
    useRoute: () => ({ name: 'PortalResearchTask', params: { id: '41' } }), useRouter: () => ({ push() {} }),
    useUserStore: () => ({ nickName: '验收用户' }), getCitationPath, formatBusinessTime: value => value || '',
    PortalEmptyState: {}, Check: {}, Loading: {}, WarningFilled: {}, ElMessage: {}, ElMessageBox: {},
    getPipelineResearchJob: async () => { throw Error('rendering must not issue a task request') },
    cancelPipelineResearchJob: async () => { throw Error('must not cancel') },
    retryPipelineResearchJob: async () => { throw Error('must not retry') }
  }
  const code = script.content.replace(/^import[\s\S]*?from ['"][^'"]+['"];?\n?/gm, '').replace('export default', 'return')
  const entries = Object.entries(dependencies).filter(([key]) => key !== 'default' && key !== 'module.exports')
  const component = new Function(...entries.map(([key]) => key), code)(...entries.map(([, value]) => value))
  const original = component.setup
  component.setup = (props, context) => {
    const state = original(props, context)
    state.loaded.value = true
    state.showMaterials.value = true
    state.task.value = { title: '历史任务', status: 'completed', progress: 100, type, fixedDigestFormat: ['weekly', 'monthly'].includes(type),
      selectedItems: [
        { id: '18', type: 'article', title: '历史新闻', source: '新闻来源' },
        { id: '26', type: 'paper', title: '历史论文', source: '期刊' },
        { id: '54', type: 'file', title: '历史上传附件.docx', source: { filename: '历史上传附件.docx' } }
      ], ...overrides }
    return state
  }
  component.render = new Function('Vue', compiled.code)(vue)
  const app = vue.createSSRApp(component)
  const slot = { setup: (_, context) => () => vue.h('div', context.slots.default?.()) }
  for (const name of ['el-button', 'el-tag', 'el-progress', 'el-alert', 'el-dialog', 'router-link']) app.component(name, slot)
  return renderToString(app)
}

test('a report edit conflict exposes the retained new result without an editable or unsafe HTML surface', async () => {
  const html = await renderTaskMaterials('research', { applyConflict: true,
    resultContent: '## 本次新结果\n\n这是本次生成的正文。\n\n<img src=x onerror=alert(1)>' })
  const result = html.match(/<article class="ps-task-result-content">([\s\S]*?)<\/article>/)?.[1]
  assert.ok(result)
  assert.match(result, /<h3>本次新结果<\/h3>/)
  assert.match(result, /这是本次生成的正文/)
  assert.match(result, /&lt;img/)
  assert.doesNotMatch(result, /<img|contenteditable/)
  assert.match(html, /现有报告中的修改继续保留/)
})

for (const type of ['weekly', 'monthly', 'research-demand']) {
  test(`task input summary respects ${type} scope while retaining historical uploaded evidence`, async () => {
    const html = await renderTaskMaterials(type)
    const summary = html.match(/<div class="ps-input-summary[^>]*>([\s\S]*?)<\/div>/)?.[1]
    assert.ok(summary)
    assert.match(summary, /新闻资讯.*1/)
    assert.match(summary, /论文.*1/)
    if (type === 'research-demand') {
      assert.match(summary, /上传资料.*1/)
    } else {
      assert.doesNotMatch(summary, /上传资料/)
      assert.match(html, /输出格式/)
      assert.match(html, /系统固定格式/)
    }
    // Summary simplification must not remove source snapshots from the dialog.
    assert.match(html, /输入资料清单/)
    assert.match(html, /历史上传附件\.docx/)
    assert.match(html, /上传资料 · 历史上传附件\.docx/)
    assert.match(html, /历史新闻/)
    assert.match(html, /历史论文/)
  })
}
