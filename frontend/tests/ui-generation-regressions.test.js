import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
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

test('G01: only explicit matching cadence or all is eligible; legacy names are conservative', () => {
  const match = action('DigestCreateView', 'templateMatchesType')
  for (const digestCadence of ['daily', 'weekly', 'monthly', 'all', null, 'unknown']) {
    assert.equal(match({ digestCadence, name: '模板' }, '日报'), ['daily', 'all'].includes(digestCadence))
  }
  assert.equal(match({ name: '管网科技情报月报' }, '日报'), false)
  assert.equal(match({ name: '管网科技情报日报' }, '日报'), true)
  assert.equal(match({ name: '日报周报混合模板' }, '日报'), false)
  assert.equal(match({ digestCadence: null, name: '管网科技情报日报' }, '日报'), false)
  assert.equal(match({ reportType: 'digest', purpose: 'digest', name: '未知' }, '日报'), false)
})

test('G01: loading, switching and query selection reject mismatched templates; payload rechecks', () => {
  const form = { type: '日报', template: '2' }
  const templateOptions = { value: [{ value: '1', digestCadence: 'daily' }, { value: '2', digestCadence: 'monthly' }] }
  const templateMatchesType = action('DigestCreateView', 'templateMatchesType')
  action('DigestCreateView', 'selectTemplateForType', { form, templateOptions, templateMatchesType })()
  assert.equal(form.template, '1')
  form.template = 'old-template-uuid'
  action('DigestCreateView', 'selectTemplateForType', { form, templateOptions, templateMatchesType })()
  assert.equal(form.template, 'old-template-uuid')
  const source = page('DigestCreateView')
  assert.match(source, /availableTemplates = computed\([^\n]*templateMatchesType/)
  assert.match(source, /watch\(\(\) => route.query.template,[^\n]*selectTemplateForType/)
  assert.match(source, /function buildDigestPayload\(\)[\s\S]*?templateMatchesType\(selectedTemplate, form.type\)/)
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

test('G08: schedule cards reflect real policy and distinguish missing history from zero', () => {
  const policy = action('DigestListView', 'scheduleHolidayPolicy')
  const status = action('DigestListView', 'scheduleStatus')
  assert.equal(policy({ config: { holiday_policy: 'skip' }, holidayPolicy: 'run' }), '节假日跳过')
  assert.equal(policy({}), '节假日照常执行')
  assert.equal(status({}), '暂无执行记录')
  assert.equal(status({ lastStatus: 'failed' }), '执行失败')
  assert.equal(status({ lastStatus: 'no_data' }), '无匹配资料，已跳过')
  assert.equal(status({ lastStatus: 'completed', hasResult: true }), '已生成')
  const target = action('DigestListView', 'scheduleResultPath')
  assert.equal(target({ latestReportId: '96', hasResult: false }), '')
  assert.equal(target({ latestReportId: '96', hasResult: true }), '/portal/digests/96')
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
    digest: { value: { title: '简报' } },
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
