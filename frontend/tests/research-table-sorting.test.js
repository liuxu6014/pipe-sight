import { bindListQuery } from '../src/utils/portal/listQuery.js'
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import * as vue from 'vue'
import { usePagedResults } from '../src/utils/portal/usePagedResults.js'
import { reportSummaryRow } from '../src/utils/portal/reportSummary.js'

const settle = async () => { await vue.nextTick(); await new Promise(setImmediate); await vue.nextTick() }

test('clicking table headers requests server sorting before pagination and returns to page one', async () => {
  const scope = vue.effectScope()
  const reports = Array.from({ length: 23 }, (_, index) => ({
    id: String(index), title: `报告${String(index).padStart(2, '0')}`, status: 'completed', listStatus: 'generated',
    hasOutput: true, type: 'research', ownerId: 7,
    updatedAt: `2026-10-${String(index + 1).padStart(2, '0')} 08:00:00`
  }))
  const original = JSON.stringify(reports), requests = []
  // The endpoint owns filtering, ordering and slicing. The component receives
  // only the current page, so a client-only sort cannot accidentally pass.
  async function listPipelineResearchReports(params) {
    requests.push({ ...params })
    const rows = reports.filter(row => !params.keyword || row.title.includes(params.keyword))
      .filter(row => !params.status || row.listStatus === params.status)
      .sort((a, b) => {
        const direction = ['title-desc', 'updated-desc'].includes(params.sort) ? -1 : 1
        const field = params.sort.startsWith('title') ? 'title' : 'updatedAt'
        return direction * a[field].localeCompare(b[field])
      })
    const start = (params.pageNum - 1) * params.pageSize
    return { data: { rows: rows.slice(start, start + params.pageSize), total: rows.length } }
  }
  const store = vue.reactive({ tasks: [], researchReports: [], workspaceEpoch: 0, sectionErrors: {} })
  const context = vm.createContext({
    ...vue, bindListQuery, usePagedResults, reportSummaryRow, onMounted() {}, onBeforeUnmount() {}, clearTimeout, setTimeout,
    useRoute: () => ({ query: {} }), useRouter: () => ({ replace: async () => {} }), usePortalStore: () => store, useUserStore: () => ({ id: '7' }),
    buildPersonalReports: ({ reports }) => reports, isDigestType: () => false,
    createResearchRefresh: () => ({ invalidate() {}, run() {}, stop() {} }),
    listPipelineResearchJobs() {}, listPipelineResearchReports
  })
  const source = readFileSync(new URL('../src/views/portal/pages/ResearchWorkbenchView.vue', import.meta.url), 'utf8')
  const script = source.split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
  scope.run(() => vm.runInContext(`${script}\nglobalThis.view = { changeReportSort, pagedReports, total, currentPage, pageSize, keyword, status, sort }`, context))
  const view = context.view
  const ids = () => Array.from(view.pagedReports.value, row => row.id)
  try {
    await settle()
    assert.deepEqual(ids(), ['22', '21', '20', '19', '18', '17', '16', '15', '14', '13'])
    assert.equal(view.total.value, 23)
    assert.equal(requests.at(-1).sort, 'updated-desc')
    assert.equal(requests.at(-1).pageSize, 10)
    view.currentPage.value = 3
    await settle()
    assert.deepEqual(ids(), ['2', '1', '0'])
    assert.equal(requests.at(-1).pageNum, 3)
    view.changeReportSort({ prop: 'updatedAt', order: 'ascending' })
    await settle()
    assert.equal(view.currentPage.value, 1)
    assert.equal(requests.at(-1).sort, 'updated-asc')
    assert.equal(requests.at(-1).pageNum, 1)
    assert.deepEqual(ids(), ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'])
    view.currentPage.value = 3
    await settle()
    assert.deepEqual(ids(), ['20', '21', '22'])
    view.changeReportSort({ prop: 'title', order: 'descending' })
    await settle()
    assert.equal(view.currentPage.value, 1)
    assert.equal(requests.at(-1).sort, 'title-desc')
    assert.deepEqual(ids(), ['22', '21', '20', '19', '18', '17', '16', '15', '14', '13'])
    view.changeReportSort({ prop: 'title', order: 'ascending' })
    await settle()
    assert.equal(ids()[0], '0')
    assert.equal(requests.at(-1).sort, 'title')
    view.keyword.value = '报告1'
    await new Promise(resolve => setTimeout(resolve, 210))
    await settle()
    assert.deepEqual(ids(), ['10', '11', '12', '13', '14', '15', '16', '17', '18', '19'])
    assert.equal(view.total.value, 10)
    assert.equal(requests.at(-1).keyword, '报告1')
    assert.equal(requests.at(-1).pageNum, 1)
    assert.equal(JSON.stringify(reports), original)
    assert.deepEqual(Array.from(store.researchReports), [])
    // The account epoch starts a replacement request; page-level timer cleanup
    // must not invalidate that request before its response arrives.
    store.workspaceEpoch++
    await settle()
    assert.equal(ids().length, 10)
    assert.equal(view.total.value, 10)
  } finally { scope.stop() }
})

test('summary DTOs retain readable type, task state and task links without report bodies', () => {
  for (const type of ['weekly', 'monthly']) {
    const row = reportSummaryRow({ id: '1001', jobId: '2001', type, hasOutput: false, listStatus: 'active', status: 'queued' })
    assert.equal(row.typeLabel, '情报简报')
    assert.equal(row.statusLabel, '排队中')
    assert.equal(row.path, '/portal/research/tasks/2001')
  }
  const running = reportSummaryRow({ id: '1002', jobId: '2002', type: 'research-demand', hasOutput: false, listStatus: 'active', status: 'running' })
  assert.equal(running.typeLabel, '科研报告')
  assert.equal(running.statusLabel, '生成中')
  const generated = reportSummaryRow({ id: '1003', jobId: '2003', type: 'research-demand', hasOutput: true, listStatus: 'generated', status: 'completed' })
  assert.equal(generated.statusLabel, '已生成')
  assert.equal(generated.path, '/portal/research/reports/1003')
  for (const [state, label] of [['failed', '生成失败'], ['cancelled', '已取消'], ['unavailable', '暂无正文']]) {
    assert.equal(reportSummaryRow({ id: '1004', listStatus: state }).statusLabel, label)
  }
})
