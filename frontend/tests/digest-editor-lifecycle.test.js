import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { computed, ref, effectScope } from 'vue'
import { cleanReportCitationNotes } from '../src/utils/portal/reportDocument.js'
import { getCitationPath } from '../src/utils/portal/citationRouting.js'
import { decimalId } from '../src/utils/portal/businessId.js'

const source = readFileSync(new URL('../src/views/portal/pages/DigestEditorView.vue', import.meta.url), 'utf8')
const setup = source.split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
function deferred() { let resolve; const promise = new Promise(yes => { resolve = yes }); return { promise, resolve } }
function editor(get, overrides = {}) {
  let dispose
  const scope = effectScope()
  const context = vm.createContext({
    computed, ref, cleanReportCitationNotes, getCitationPath, decimalId,
    onMounted() {}, onBeforeUnmount(fn) { dispose = fn }, onBeforeRouteLeave() {}, onBeforeRouteUpdate() {},
    useRoute: () => ({ params: { id: '41' }, query: {} }), useRouter: () => ({}),
    usePortalStore: () => ({ digestReports: [], newsItems: [] }),
    getPipelineResearchReport: get, getToken: () => 'test',
    window: { addEventListener() {}, removeEventListener() {} }, clearTimeout() {}, setTimeout() { return 1 },
    ElMessage: { warning() {}, error() {}, success() {} },
    ...overrides
  })
  scope.run(() => vm.runInContext(`${setup}\nglobalThis.page = { loadDigest, digest, sections, citations, addCandidate, loaded, loadError, isReadOnly, exportDigest, exporting, activeTab }`, context))
  return { ...context.page, close() { dispose(); scope.stop() } }
}
test('digest load arriving after disposal cannot publish private content into the editor', async () => {
  const response = deferred(), view = editor(() => response.promise)
  const pending = view.loadDigest()
  view.close()
  response.resolve({ data: { id: '41', title: 'Late private content', sections: [{ content: 'private' }] } })
  await pending
  assert.equal(view.loaded.value, false)
  assert.notEqual(view.digest.value.title, 'Late private content')
})
test('digest detail respects backend readOnly independent of publication state', async () => {
  const view = editor(async () => ({ data: { id: '41', status: 'draft', readOnly: true, sections: [] } }))
  await view.loadDigest()
  assert.equal(view.isReadOnly.value, true)
  view.close()
})
test('source titles are actual typed detail links, not success-check decorations', () => {
  assert.match(source, /getCitationPath\(source\)/)
  assert.match(source, /getCitationPath\(item\)/)
  assert.doesNotMatch(source, /CircleCheckFilled/)
  assert.doesNotMatch(source, /条可信来源/)
})

test('source and export deep links open their respective inspector panels', () => {
  for (const [panel, expected] of [['sources', '来源清单'], ['exports', '导出记录']]) {
    const view = editor(undefined, { useRoute: () => ({ params: { id: '41' }, query: { panel } }) })
    assert.equal(view.activeTab.value, expected)
    view.close()
  }
})

test('duplicate export clicks create one task, open history, and surface a resumable status failure', async () => {
  const created = deferred(), messages = []
  let creates = 0, downloads = 0
  const view = editor(undefined, {
    createPipelineResearchReportExport: () => { creates++; return created.promise },
    listPipelineResearchReportExports: async () => { throw Error('offline') },
    downloadPipelineResearchReportExport: async () => { downloads++ },
    setTimeout: fn => { fn(); return 1 },
    ElMessage: { error: text => messages.push(text), success() {} }
  })
  const pending = view.exportDigest('docx')
  await Promise.resolve(); await Promise.resolve()
  await view.exportDigest('docx')
  assert.equal(creates, 1)
  created.resolve({ data: { exportId: '82' } })
  await pending
  assert.equal(view.activeTab.value, '导出记录')
  assert.ok(messages.some(text => /已创建.*导出记录/.test(text)))
  assert.equal(view.exporting.value, false)
  assert.equal(downloads, 0)
  view.close()
})

test('leaving during export creation does not start a polling or download request afterwards', async () => {
  const created = deferred()
  let polls = 0, downloads = 0
  const view = editor(undefined, {
    createPipelineResearchReportExport: () => created.promise,
    listPipelineResearchReportExports: async () => { polls++; return { data: { rows: [] } } },
    downloadPipelineResearchReportExport: async () => { downloads++ }
  })
  const pending = view.exportDigest('pdf')
  await Promise.resolve(); await Promise.resolve()
  view.close()
  created.resolve({ data: { exportId: '82' } })
  await pending
  assert.equal(polls, 0)
  assert.equal(downloads, 0)
})

test('adding the same article across pages reuses its citation and never duplicates the section association', () => {
  const view = editor(undefined, { ElMessage: { info() {}, success() {}, warning() {} } })
  view.sections.value = [{ id: 1, title: '栏目', content: '', citationIds: [] }]
  view.citations.value = [{ id: 1, sourceId: 26, type: 'article', title: '原来源' }]
  view.addCandidate({ id: '26', title: '资讯', source: '来源' })
  view.addCandidate({ id: '26', title: '资讯', source: '来源' })
  assert.equal(view.citations.value.length, 1)
  assert.equal(view.sections.value[0].citationIds.length, 1)
  assert.equal(view.sections.value[0].status, 'draft')
  assert.equal(view.sections.value[0].content, '')
  view.close()
})
