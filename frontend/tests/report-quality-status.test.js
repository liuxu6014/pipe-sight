import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { computed, effectScope, ref, watch } from 'vue'
import { isDigestType } from '../src/views/portal/utils/routing.js'

const source = readFileSync(new URL('../src/views/portal/pages/ReportEditorView.vue', import.meta.url), 'utf8')
function editor() {
  const scope = effectScope()
  const context = vm.createContext({
    computed, ref, watch, isDigestType,
    onMounted() {}, onBeforeUnmount() {}, onBeforeRouteLeave() {}, onBeforeRouteUpdate() {},
    useRoute: () => ({ params: { id: '10' }, query: {}, path: '/portal/research/reports/10' }), useRouter: () => ({}),
    usePortalStore: () => ({ researchReports: [], digestReports: [], newsItems: [] }),
    setTimeout: () => 1, clearTimeout() {},
  })
  const script = source.split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
  scope.run(() => vm.runInContext(`${script}\nglobalThis.state = { report, saveState, citationCheckState, outlineCheckState, outlineCheckLabel, outlineCheckDescription }`, context))
  return { state: context.state, close: () => scope.stop() }
}
const issue = { code: 'chapter_length_deviation', section: '技术需求', actualWords: 1235, targetWords: 600,
  message: '章节“技术需求”约 1235 字词，规划 600 字；请核对篇幅。' }

test('generated report shows outline length warning independently of passed citation checks', () => {
  const view = editor()
  try {
    view.state.report.value = { versionNo: 3, metadata: { modelSnapshot: { checks: {
      citation: { status: 'passed', version: 3 }, outline: { status: 'warning', version: 3, issues: [issue] }
    } } } }
    assert.equal(view.state.citationCheckState.value, 'passed')
    assert.equal(view.state.outlineCheckState.value, 'warning')
    assert.match(view.state.outlineCheckLabel.value, /篇幅.*偏差/)
    assert.match(view.state.outlineCheckDescription.value, /1235.*600/)
    assert.match(source, /<el-alert[^>]*class="ps-outline-check-status"[^>]*:title="outlineCheckLabel"[^>]*:description="outlineCheckDescription"[^>]*type="warning"/)
  } finally { view.close() }
})

test('legacy qualityIssues remain visible and absent checks never imply length passed', () => {
  const view = editor()
  try {
    view.state.report.value = { qualityIssues: [issue] }
    assert.equal(view.state.outlineCheckState.value, 'warning')
    assert.match(view.state.outlineCheckDescription.value, /技术需求.*1235.*600/)
    view.state.report.value = {}
    assert.equal(view.state.outlineCheckState.value, 'not_run')
    view.state.report.value = { metadata: { modelSnapshot: { checks: { outline: { status: 'passed', issues: [] } } } } }
    assert.equal(view.state.outlineCheckState.value, 'passed')
    view.state.report.value.qualityIssues = [issue]
    assert.equal(view.state.outlineCheckState.value, 'warning')
  } finally { view.close() }
})

test('dirty, saving, failed or different version makes old length and citation checks stale', () => {
  const view = editor()
  try {
    view.state.report.value = { versionNo: 3, metadata: { modelSnapshot: { checks: {
      citation: { status: 'passed' }, outline: { status: 'passed', version: 3, issues: [] }
    } } } }
    for (const state of ['dirty', 'saving', 'error']) {
      view.state.saveState.value = state
      assert.equal(view.state.outlineCheckState.value, 'stale')
      assert.equal(view.state.citationCheckState.value, 'stale')
      assert.match(view.state.outlineCheckDescription.value, /不能代表当前版本/)
    }
    view.state.saveState.value = 'saved'
    view.state.report.value.versionNo = 4
    assert.equal(view.state.outlineCheckState.value, 'stale')
  } finally { view.close() }
})
