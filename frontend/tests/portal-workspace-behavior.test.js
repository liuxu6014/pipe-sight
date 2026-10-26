import test from 'node:test'
import assert from 'node:assert/strict'
import { unfinishedTasks, ownedReports, publicationDate, periodOverlaps } from '../src/views/portal/utils/workspace.js'

test('ongoing work retains failed jobs but excludes finished and cancelled work', () => {
  const tasks = [{ id: 'done', status: 'completed' }, { id: 'cancel', status: 'cancelled' },
    { id: 'old', status: 'queued', updatedAt: '2026-10-01 12:00:00' },
    { id: 'failed', status: 'failed', updatedAt: '2026-10-13 12:00:00' }]
  assert.deepEqual(unfinishedTasks(tasks).map(x => x.id), ['failed', 'old'])
  assert.equal(tasks.length, 4)
})

test('personal recent results cannot include another author’s published report', () => {
  const reports = [{ id: 'public', ownerId: 2 }, { id: 'mine', ownerId: 1 }, { id: 'job-result' }, { id: 'unknown' }]
  assert.deepEqual(ownedReports(reports, [{ reportId: 'job-result' }], '1').map(x => x.id), ['mine', 'job-result'])
  assert.deepEqual(ownedReports(reports, [], '').map(x => x.id), [])
})

test('publication dates preserve year precision and missing dates', () => {
  assert.equal(publicationDate('2026'), '2026')
  assert.equal(publicationDate('2026-10-13 09:00'), '2026-10-13')
  assert.equal(publicationDate(''), '日期未提供')
})

test('digest date filtering uses coverage overlap, not its last edit time', () => {
  const report = { period: '2026-09-28 至 2026-10-04', updatedAt: '2026-10-13' }
  assert.equal(periodOverlaps(report, ['2026-10-01', '2026-10-02']), true)
  assert.equal(periodOverlaps(report, ['2026-10-13', '2026-10-13']), false)
  assert.equal(periodOverlaps({ updatedAt: '2026-10-01' }, ['2026-10-01', '2026-10-01']), false)
})
