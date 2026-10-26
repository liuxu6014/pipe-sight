import test from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import * as ids from '../src/utils/portal/businessId.js'
import { formatBusinessTime, businessTimeInstant, normalizeBusinessTimes, calendarDate, parseCalendarDate } from '../src/utils/portal/businessTime.js'
import { sortResearchReports } from '../src/views/portal/utils/reportList.js'
import { sortByActivity, publicationDate } from '../src/views/portal/utils/workspace.js'
import { newsDate, cleanResultMeta } from '../src/utils/portal/discovery.js'

test('Beijing wall time keeps its clock while aware ISO converts exactly once', () => {
  assert.equal(formatBusinessTime('2026-10-25 14:30:00'), '2026-10-25 14:30:00')
  assert.equal(formatBusinessTime('2026-10-25T14:30:00.123'), '2026-10-25 14:30:00')
  assert.equal(formatBusinessTime('2026-10-25T06:30:00.999Z'), '2026-10-25 14:30:00')
  assert.equal(formatBusinessTime('2026-10-25T14:30:00+08:00'), '2026-10-25 14:30:00')
  assert.equal(formatBusinessTime('2026-10-25T23:30:00-07:00'), '2026-10-26 14:30:00')
  assert.equal(formatBusinessTime(formatBusinessTime('2026-10-25T06:30:00Z')), '2026-10-25 14:30:00')
})

test('partial publication dates and missing/invalid dates are never invented', () => {
  for (const value of ['2026', '2026-10', '2026-10-25', '时间未提供', '2026-02-30 12:00:00', '2026-02-30T12:00:00Z']) assert.equal(formatBusinessTime(value), value)
  assert.equal(formatBusinessTime(null), '')
  assert.equal(calendarDate('2026'), '')
  assert.equal(calendarDate('2026-02-30'), '')
  assert.equal(calendarDate('2026-02-30T12:00:00Z'), '')
  assert.ok(Number.isNaN(businessTimeInstant('invalid')))
})

test('API display normalization touches business audit times but not operational instants or frozen JSON', () => {
  const input = { data: { rows: [{ id: '9007199254740993', created_at: '2026-10-25T06:30:00Z', updatedAt: '2026-10-25 14:30:00', nextRunAt: '2026-10-25T08:00:00Z', lease_expires_at: '2026-10-25T09:00:00Z', published_date: '2026-10', config_snapshot: { created_at: '2020-01-01T00:00:00Z', content: '用户正文' } }] } }
  const row = normalizeBusinessTimes(input).data.rows[0]
  assert.equal(row.created_at, '2026-10-25 14:30:00')
  assert.equal(row.updatedAt, '2026-10-25 14:30:00')
  assert.equal(row.nextRunAt, input.data.rows[0].nextRunAt)
  assert.equal(row.lease_expires_at, input.data.rows[0].lease_expires_at)
  assert.deepEqual(row.config_snapshot, input.data.rows[0].config_snapshot)
  assert.equal(row.id, '9007199254740993')
  assert.equal(input.data.rows[0].created_at, '2026-10-25T06:30:00Z')
})

test('wall-time sorting treats equivalent naive Beijing and UTC instants equally', () => {
  assert.equal(businessTimeInstant('2026-10-25 14:30:00'), businessTimeInstant('2026-10-25T06:30:00Z'))
  assert.equal(calendarDate('2026-10-25T18:30:00Z'), '2026-10-26')
})

test('display, sorting and date-picker round trips are invariant across browser time zones', () => {
  const url = new URL('../src/utils/portal/businessTime.js', import.meta.url).href
  const sortUrl = new URL('../src/views/portal/utils/reportList.js', import.meta.url).href
  const program = `import { formatBusinessTime, businessTimeInstant, calendarDate, parseCalendarDate } from ${JSON.stringify(url)}; import { sortResearchReports } from ${JSON.stringify(sortUrl)}; console.log(JSON.stringify([formatBusinessTime('2026-10-25 14:30:00'),formatBusinessTime('2026-10-25T06:30:00Z'),businessTimeInstant('2026-10-25 14:30:00'),calendarDate(new Date(2026,9,25)),calendarDate(parseCalendarDate('2026-10-25')),calendarDate('2026-10-25T18:30:00Z'),sortResearchReports([{id:'1',updatedAt:'2026-10-25 14:00:00'},{id:'2',updatedAt:'2026-10-25T06:30:00Z'}]).map(row=>row.id)]));`
  let expected
  for (const TZ of ['UTC', 'Asia/Shanghai', 'America/Los_Angeles', 'Pacific/Honolulu', 'Pacific/Kiritimati']) {
    const run = spawnSync(process.execPath, ['--input-type=module', '-e', program], { env: { ...process.env, TZ }, encoding: 'utf8' })
    assert.equal(run.status, 0, run.stderr)
    const result = JSON.parse(run.stdout)
    assert.equal(result[3], '2026-10-25')
    assert.equal(result[4], '2026-10-25')
    assert.deepEqual(result[6], ['2', '1'])
    if (expected) assert.deepEqual(result, expected, TZ)
    expected = result
  }
})

test('actual business API boundary formats audit times without changing outbound data or operational wire times', async () => {
  const source = readFileSync(new URL('../src/api/pipeline/request.js', import.meta.url), 'utf8').replace(/^import .*\n/gm, '').replace('export default async function pipelineRequest', 'return async function pipelineRequest')
  const calls = []
  const api = new Function('request', 'normalizeBusinessTimes', ...Object.keys(ids), source)(async options => {
    calls.push(options)
    return { data: { rows: [{ id: '9007199254740993', createdAt: '2026-10-25T06:30:00Z', updated_at: '2026-10-25 14:30:00', finishedAt: '2026-10-25T06:30:00Z' }] } }
  }, normalizeBusinessTimes, ...Object.values(ids))
  const data = { templateId: '42', requirements: '原始正文 2026-10-25T06:30:00Z', options: { timestamp: '2026-10-25T06:30:00Z' } }
  const response = await api({ url: '/pipeline/research/jobs', method: 'post', data })
  assert.equal(response.data.rows[0].createdAt, '2026-10-25 14:30:00')
  assert.equal(response.data.rows[0].updated_at, '2026-10-25 14:30:00')
  assert.equal(response.data.rows[0].finishedAt, '2026-10-25T06:30:00Z')
  assert.deepEqual(calls[0].data, data)
})

test('business lists sort mixed wire formats while news offsets and partial paper dates display accurately', () => {
  const rows = [{ id: '1', updatedAt: '2026-10-25 14:00:00' }, { id: '2', updatedAt: '2026-10-25T06:30:00Z' }, { id: '3', updated_at: '2026-10-25 15:00:00' }]
  assert.deepEqual(sortResearchReports(rows).map(row => row.id), ['3', '2', '1'])
  assert.deepEqual(sortByActivity(rows).map(row => row.id), ['3', '2', '1'])
  assert.equal(rows[0].id, '1')
  assert.equal(newsDate('2026-10-25T18:30:00Z'), '2026-10-26 02:30:00')
  assert.equal(cleanResultMeta('来源 · 2026-10-25T18:30:00Z'), '来源 · 2026-10-26 02:30:00')
  assert.equal(publicationDate('2026-10-25T18:30:00Z'), '2026-10-26')
  for (const value of ['2026', '2026-10', '2026-10-25']) assert.equal(publicationDate(value), value)
})
