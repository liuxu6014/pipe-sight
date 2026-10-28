import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { ref, computed, watch, effectScope } from 'vue'
import { makeRewriteDraft, applyRewriteDraft, rewriteRequest } from '../src/utils/portal/reportRewrite.js'
import { buildReportMarkdown, cleanReportCitationNotes } from '../src/utils/portal/reportDocument.js'

function setup(propose = async () => ({ data: { text: '改写正文[1]。', revision: 'r1' } })) {
  const source = readFileSync(new URL('../src/views/portal/pages/ReportEditorView.vue', import.meta.url), 'utf8')
    .split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
  const scope = effectScope()
  let writes = 0, calls = 0, unmount, located
  const context = vm.createContext({ ref, computed, watch,
    makeRewriteDraft, applyRewriteDraft, rewriteRequest, buildReportMarkdown, cleanReportCitationNotes,
    onMounted() {}, onBeforeUnmount(fn) { unmount = fn }, onBeforeRouteLeave() {}, onBeforeRouteUpdate() {},
    useRoute: () => ({ params: { id: '40' } }), useRouter: () => ({}), usePortalStore: () => ({ researchReports: [] }),
    setTimeout() {}, clearTimeout() {}, window: { removeEventListener() {} },
    nextTick(fn) { fn?.() }, document: { getElementById(id) { located = id; return { scrollIntoView() {} } } },
    ElMessage: { success() {}, error() {}, warning() {}, info() {} },
    proposePipelineReportRewrite: async (...args) => { calls++; return propose(...args) },
    updatePipelineResearchReport: async () => { writes++; return { data: { versionNo: 2, revision: 'r2' } } },
  })
  scope.run(() => vm.runInContext(`${source}\nglobalThis.state = { report, sections, citations, isEditing, inspectorVisible, highlightedCitation, rewriteDraft, rewriteVisible, rewriteResult, rewriteError, openRewrite, generateRewrite, acceptRewrite, showCitation }`, context))
  const state = context.state
  state.report.value = { id: '40', title: '报告', versionNo: 1, revision: 'r1' }
  state.sections.value = [{ id: 1, title: '正文', content: '原始正文[1]。', words: 8 }, { id: 2, title: '第二章', content: '另章正文', words: 4 }]
  return { state, get writes() { return writes }, get calls() { return calls }, get located() { return located }, close() { unmount(); scope.stop() } }
}

test('default reading mode cannot invoke rewrite; proposal does not save until explicit acceptance', async () => {
  const view = setup()
  try {
    const s = view.state
    assert.equal(s.isEditing.value, false)
    assert.equal(s.inspectorVisible.value, false)
    s.openRewrite(s.sections.value[0])
    assert.equal(s.rewriteVisible.value, false)
    s.isEditing.value = true
    s.openRewrite(s.sections.value[0])
    await s.generateRewrite()
    assert.equal(s.rewriteResult.value, '改写正文[1]。')
    assert.equal(s.sections.value[0].content, '原始正文[1]。')
    assert.equal(view.writes, 0)
    await s.acceptRewrite()
    assert.equal(s.sections.value[0].content, '改写正文[1]。')
    assert.equal(s.sections.value[1].content, '另章正文')
    assert.equal(view.writes, 1)
  } finally { view.close() }
})

test('changes made while preview is open cannot be overwritten by acceptance', async () => {
  const view = setup()
  try {
    const s = view.state
    s.isEditing.value = true
    s.openRewrite(s.sections.value[0]); await s.generateRewrite()
    s.sections.value[0].content = '之后编辑的正文[1]。'
    await s.acceptRewrite()
    assert.equal(s.sections.value[0].content, '之后编辑的正文[1]。')
    assert.equal(view.writes, 0)
    assert.match(s.rewriteError.value, /已修改/)
  } finally { view.close() }
})

test('read-only reports never request model proposals', async () => {
  const view = setup()
  try {
    view.state.report.value.readOnly = true
    view.state.isEditing.value = true
    view.state.openRewrite(view.state.sections.value[0])
    await view.state.generateRewrite()
    assert.equal(view.calls, 0)
    assert.equal(view.writes, 0)
  } finally { view.close() }
})

test('late rewrite response after leaving editor is ignored', async () => {
  let resolve
  const view = setup(() => new Promise(yes => { resolve = yes }))
  const s = view.state
  s.isEditing.value = true
  s.openRewrite(s.sections.value[0])
  const pending = s.generateRewrite()
  await new Promise(yes => setImmediate(yes))
  view.close()
  resolve({ data: { text: '晚到的改写正文[1]。', revision: 'r1' } })
  await pending
  assert.equal(s.rewriteResult.value, '')
  assert.equal(view.writes, 0)
})

test('clicking an actual reference opens and locates its source card without saving', () => {
  const view = setup()
  try {
    const s = view.state
    s.citations.value = [{ id: 1, title: '来源' }]
    s.showCitation('[1]')
    assert.equal(s.inspectorVisible.value, true)
    assert.equal(s.highlightedCitation.value, '1')
    assert.equal(view.located, 'report-reference-1')
    assert.equal(view.writes, 0)
  } finally { view.close() }
})
