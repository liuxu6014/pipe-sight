import test from 'node:test'
import assert from 'node:assert/strict'
import { reportRowActions, templatePreview, createResearchRefresh } from '../src/utils/portal/researchWorkspace.js'

test('report actions separate reading and editing; failed attempts link to existing task recovery', () => {
  const row = { kind: 'report', hasOutput: true, path: '/portal/research/reports/40', status: 'generated' }
  assert.deepEqual(reportRowActions(row).map(item => item.path), [row.path, `${row.path}?mode=edit`])
  assert.equal(reportRowActions(row)[0].label, '查看')
  assert.equal(reportRowActions({ ...row, readOnly: true }).length, 1)
  assert.equal(reportRowActions({ ...row, path: '', hasOutput: false }).length, 0)
  assert.equal(reportRowActions({ kind: 'task', status: 'failed', path: '/portal/research/tasks/12' })[0].label, '查看原因 / 重试')
})

test('template preview uses real section descriptions and word targets without exposing prompt', () => {
  const result = templatePreview({ name: '项目需求', prompt: '管理员私有提示词', modelConfigured: false,
    sections: [{ title: '问题', words: 800, description: '具体问题' }, { title: '经费', words: 150 }] })
  assert.equal(result.words, 950)
  assert.equal(result.sections[0].description, '具体问题')
  assert.equal(result.modelLabel, '文本模型未就绪')
  assert.ok(!JSON.stringify(result).includes('管理员私有提示词'))
})

test('targeted refresh coalesces requests, preserves failed datasets and ignores logout results', async () => {
  let resolve, calls = 0
  const store = { workspaceEpoch: 0, liveReports: [{ id: '40' }], tasks: [], sectionErrors: {} }
  const refresh = createResearchRefresh({ store, loadReports: async () => { throw new Error('offline') },
    loadJobs: () => { calls++; return new Promise(yes => { resolve = yes }) } })
  const first = refresh.run()
  const second = refresh.run()
  assert.equal(calls, 1)
  resolve({ data: { rows: [{ id: '12', type: 'research', status: 'running', progress: 35 }] } })
  await Promise.all([first, second])
  assert.equal(store.tasks[0].progress, 35)
  assert.equal(store.liveReports[0].id, '40')
  assert.ok(store.sectionErrors.reports)
  const pending = refresh.run()
  store.workspaceEpoch++
  resolve({ data: { rows: [{ id: '99', status: 'completed' }] } })
  await pending
  assert.equal(store.tasks[0].id, '12')
  refresh.stop()
})

test('disposed refresh cannot inject a late response or interpret malformed data as empty', async () => {
  let resolve
  const store = { workspaceEpoch: 0, liveReports: [{ id: '40' }], tasks: [{ id: '12' }], sectionErrors: {} }
  const refresh = createResearchRefresh({ store, loadReports: async () => ({ data: { rows: 'invalid' } }),
    loadJobs: () => new Promise(yes => { resolve = yes }) })
  const pending = refresh.run()
  refresh.stop()
  resolve({ data: { rows: [{ id: '99' }] } })
  await pending
  assert.equal(store.tasks[0].id, '12')
  assert.equal(store.liveReports[0].id, '40')
})
