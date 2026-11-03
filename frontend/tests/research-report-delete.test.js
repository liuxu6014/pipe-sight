import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import * as vue from 'vue'
import { canDeleteResearchReport, createResearchRefresh, removeDeletedReport, reportRowActions } from '../src/utils/portal/researchWorkspace.js'

const row = { id: '40', title: '测试报告', kind: 'report', path: '/portal/research/reports/40', hasOutput: true, status: 'generated' }
function setup(confirm, remove = async () => {}) {
  const store = vue.reactive({ workspaceEpoch: 0, tasks: [{ id: '50', reportId: '40', status: 'completed' }, { id: '51', reportId: '41', status: 'completed' }], liveReports: [row, { ...row, id: '41' }], basket: [{ id: '26', type: 'paper' }], favorites: ['40', '26'], favoriteItems: [{ id: '40', type: 'report' }, { id: '26', type: 'paper' }], sectionErrors: {} })
  Object.defineProperty(store, 'researchReports', { get: () => store.liveReports })
  const user = vue.reactive({ id: '7' }), calls = [], errors = [], successes = []
  const source = readFileSync(new URL('../src/views/portal/pages/ResearchWorkbenchView.vue', import.meta.url), 'utf8').split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
  let dispose
  const scope = vue.effectScope()
  const context = vm.createContext({ ...vue, onMounted() {}, onBeforeUnmount(fn) { dispose = fn },
    setTimeout, clearTimeout, useRoute: () => ({ query: {} }), useRouter: () => ({}), usePortalStore: () => store, useUserStore: () => user,
    canDeleteResearchReport, createResearchRefresh, removeDeletedReport, reportRowActions,
    buildPersonalReports: ({ reports }) => reports, isDigestType: () => false, sortResearchReports: rows => rows,
    listPipelineResearchJobs: async () => ({ data: { rows: store.tasks } }), listPipelineResearchReports: async () => ({ data: { rows: store.liveReports } }),
    deletePipelineResearchReport: async id => { calls.push(id); await remove(id) },
    ElMessageBox: { confirm }, ElMessage: { success: msg => successes.push(msg), error: msg => errors.push(msg) }
  })
  scope.run(() => vm.runInContext(source + '\nglobalThis.actions = { deleteReport, deletingId }', context))
  return { store, user, calls, errors, successes, ...context.actions, close() { dispose(); scope.stop() } }
}
test('edit wording and delete eligibility preserve task/read-only safeguards', () => {
  assert.equal(reportRowActions(row)[1].label, '编辑')
  assert.equal(canDeleteResearchReport(row), true)
  assert.equal(canDeleteResearchReport({ ...row, kind: 'task' }), false)
  assert.equal(canDeleteResearchReport({ ...row, readOnly: true }), false)
})
test('cancel does not delete; confirmed deletion updates counts without removing source materials', async () => {
  const cancel = setup(async () => { throw 'cancel' })
  await cancel.deleteReport(row); assert.equal(cancel.calls.length, 0); assert.equal(cancel.store.liveReports.length, 2); cancel.close()
  const view = setup(async text => { assert.match(text, /测试报告/); assert.match(text, /引用的新闻、论文和上传资料不受影响/) })
  try {
    await view.deleteReport(row)
    assert.deepEqual(view.calls, ['40'])
    assert.equal(view.store.liveReports.length, 1); assert.equal(view.store.tasks.length, 1)
    assert.equal(view.store.basket[0].id, '26'); assert.equal(view.store.favoriteItems[0].id, '26')
    assert.equal(view.successes.length, 1)
  } finally { view.close() }
})
test('API failure preserves report and shows the server reason', async () => {
  const view = setup(async () => {}, async () => { throw { msg: '导出任务进行中' } })
  try { await view.deleteReport(row); assert.equal(view.store.liveReports.length, 2); assert.deepEqual(view.errors, ['导出任务进行中']); assert.equal(view.successes.length, 0) } finally { view.close() }
})
test('pending confirmation cannot delete after an account change and duplicate clicks are ignored', async () => {
  let resolve, dialogs = 0
  const view = setup(() => { dialogs++; return new Promise(yes => { resolve = yes }) })
  try {
    const pending = view.deleteReport(row); await view.deleteReport(row); assert.equal(dialogs, 1)
    view.user.id = '8'; view.store.workspaceEpoch++; resolve(); await pending
    assert.equal(view.calls.length, 0); assert.equal(view.deletingId.value, '')
  } finally { view.close() }
})
