import test from 'node:test'
import assert from 'node:assert/strict'
import { buildPersonalReports } from '../src/utils/portal/personalReports.js'

test('completed task and owned output appear once, without leaking another users reports', () => {
  const rows = buildPersonalReports({ userId: 7, reports: [{ id: '3001', ownerId: 7, title: '报告', reportType: 'research-demand' }, { id: '3008', ownerId: 8 }], tasks: [{ id: '3002', reportId: '3001', status: 'completed' }] })
  assert.equal(rows.length, 1)
  assert.equal(rows[0].status, 'generated')
  assert.equal(rows[0].path, '/portal/research/reports/3001')
  assert.equal(rows[0].taskPath, '/portal/research/tasks/3002')
})

test('all pending and failed attempts remain reachable, including completed outputs not yet synced', () => {
  const tasks = ['queued', 'running', 'failed', 'dead_letter', 'cancelled', 'completed'].map((status, index) => ({ id: String(4001 + index), status, type: '科研生成', progress: 130 }))
  const rows = buildPersonalReports({ reports: [], tasks, userId: 7 })
  assert.deepEqual(Object.fromEntries(rows.map(x => [x.id, x.status])), { 4001: 'active', 4002: 'active', 4003: 'failed', 4004: 'failed', 4005: 'cancelled', 4006: 'generated' })
  assert.equal(rows.find(x => x.id === '4002').progress, 100)
  assert.equal(rows.find(x => x.id === '4003').path, '/portal/research/tasks/4003')
  assert.equal(rows.find(x => x.id === '4006').hasOutput, false)
})

test('digest outputs route to digest editor, repeated outputs deduplicate but failed retries stay visible', () => {
  const report = { id: '3005', ownerId: 7, reportType: 'weekly', status: '草稿' }
  const rows = buildPersonalReports({ reports: [report, report], tasks: [{ id: '3006', reportId: '3005', status: 'completed', reportType: 'weekly' }, { id: '3007', reportId: '3005', status: 'failed', reportType: 'weekly' }], userId: 7 })
  assert.equal(rows.length, 2)
  assert.equal(rows.find(x => x.kind === 'report').path, '/portal/digests/3005')
  assert.equal(rows.find(x => x.kind === 'task').status, 'failed')
})
