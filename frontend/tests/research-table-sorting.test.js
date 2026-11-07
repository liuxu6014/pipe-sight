import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import * as vue from 'vue'
import { sortResearchReports } from '../src/views/portal/utils/reportList.js'

test('table sort changes reorder all reports before pagination and return to page one', async () => {
  const scope = vue.effectScope()
  const reports = Array.from({ length: 23 }, (_, index) => ({
    id: String(index), title: `报告${String(index).padStart(2, '0')}`, status: 'generated',
    updatedAt: index === 22 ? '' : `2026-10-${String(index + 1).padStart(2, '0')}`
  }))
  const original = JSON.stringify(reports)
  const store = vue.reactive({ tasks: [], researchReports: reports, workspaceEpoch: 0, sectionErrors: {} })
  const context = vm.createContext({
    ...vue, onMounted() {}, onBeforeUnmount() {}, clearTimeout() {},
    useRoute: () => ({ query: {} }), useRouter: () => ({}), usePortalStore: () => store, useUserStore: () => ({ id: '7' }),
    buildPersonalReports: ({ reports }) => reports, isDigestType: () => false, sortResearchReports,
    createResearchRefresh: () => ({ invalidate() {}, run() {}, stop() {} }),
    listPipelineResearchJobs() {}, listPipelineResearchReports() {}
  })
  const source = readFileSync(new URL('../src/views/portal/pages/ResearchWorkbenchView.vue', import.meta.url), 'utf8')
  const script = source.split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
  scope.run(() => vm.runInContext(`${script}\nglobalThis.view = { changeReportSort, pagedReports, currentPage, keyword, status, sort }`, context))
  const view = context.view
  const ids = () => Array.from(view.pagedReports.value, row => row.id)
  try {
    assert.deepEqual(ids(), ['21', '20', '19', '18', '17', '16', '15', '14', '13', '12'])
    view.currentPage.value = 3
    view.changeReportSort({ prop: 'updatedAt', order: 'ascending' }); await vue.nextTick()
    assert.equal(view.currentPage.value, 1)
    assert.deepEqual(ids(), ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'])
    view.currentPage.value = 3
    assert.deepEqual(ids(), ['20', '21', '22'])
    view.changeReportSort({ prop: 'title', order: 'descending' }); await vue.nextTick()
    assert.equal(view.currentPage.value, 1)
    assert.deepEqual(ids(), ['22', '21', '20', '19', '18', '17', '16', '15', '14', '13'])
    view.changeReportSort({ prop: 'title', order: 'ascending' }); await vue.nextTick()
    assert.equal(ids()[0], '0')
    view.keyword.value = '报告1'; await vue.nextTick()
    assert.deepEqual(ids(), ['10', '11', '12', '13', '14', '15', '16', '17', '18', '19'])
    assert.equal(JSON.stringify(reports), original)
  } finally { scope.stop() }
})
