import test from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { parseTime } from '../src/utils/ruoyi.js'

function formatInTimezone(timezone, cases) {
  const helper = new URL('../src/utils/ruoyi.js', import.meta.url).href
  const script = `import { parseTime } from ${JSON.stringify(helper)}; const cases = ${JSON.stringify(cases)}; console.log(JSON.stringify(cases.map(([value, pattern]) => parseTime(value, pattern))))`
  const result = spawnSync(process.execPath, ['--input-type=module', '-e', script], {
    env: { ...process.env, TZ: timezone }, encoding: 'utf8'
  })
  assert.equal(result.status, 0, result.stderr)
  return JSON.parse(result.stdout)
}

test('shared formatter preserves ISO offsets, Z and fractional seconds', () => {
  const inputs = [
    ['2026-11-19T10:20:30.654321+08:00'],
    ['2026-11-19T02:20:30.654Z'],
    ['2026-11-19T02:20:30+00:00'],
    ['2026-11-19T00:15:00.123456+08:00'],
    ['2026-11-19T07:50:30.1+05:30']
  ]
  assert.deepEqual(formatInTimezone('UTC', inputs), [
    '2026-11-19 02:20:30', '2026-11-19 02:20:30', '2026-11-19 02:20:30',
    '2026-11-18 16:15:00', '2026-11-19 02:20:30'
  ])
  assert.deepEqual(formatInTimezone('Asia/Shanghai', inputs), [
    '2026-11-19 10:20:30', '2026-11-19 10:20:30', '2026-11-19 10:20:30',
    '2026-11-19 00:15:00', '2026-11-19 10:20:30'
  ])
})

test('legacy date-only and local date-time inputs stay in local time', () => {
  const inputs = [
    ['2026-11-19'], ['2026/11/19'], ['2026-11-19 10:20:30'],
    ['2026/11/19 10:20:30.123'], ['2026-11-19T10:20:30.123456'],
    ['2026/11/22 00:05:09', '{y}年{m}月{d}日 星期{a} {h}:{i}:{s}']
  ]
  for (const timezone of ['UTC', 'Asia/Shanghai', 'America/Los_Angeles']) {
    assert.deepEqual(formatInTimezone(timezone, inputs), [
      '2026-11-19 00:00:00', '2026-11-19 00:00:00', '2026-11-19 10:20:30',
      '2026-11-19 10:20:30', '2026-11-19 10:20:30', '2026年11月22日 星期日 00:05:09'
    ])
  }
})

test('seconds, milliseconds and Date objects retain their existing formatting', () => {
  const inputs = [[1609459200], ['1609459200'], [1609459200000], ['1609459200000']]
  assert.deepEqual(formatInTimezone('UTC', inputs), Array(4).fill('2021-01-01 00:00:00'))
  assert.deepEqual(formatInTimezone('Asia/Shanghai', inputs), Array(4).fill('2021-01-01 08:00:00'))
  const value = new Date(2026, 10, 19, 10, 20, 30)
  assert.equal(parseTime(value), '2026-11-19 10:20:30')
  assert.equal(parseTime(value, '{y}/{m}/{d}'), '2026/11/19')
})

test('missing, malformed and impossible dates never become zero-filled fake dates', () => {
  for (const value of [undefined, null, '', '   ', false, true, {}, [], NaN, Infinity, new Date(NaN),
    'not a date', '2026-13-19', '2026-02-30', '2026-11-19 25:00:00',
    '2026-02-30T10:20:30+08:00', '2026-11-19T10:20:30+99:00']) {
    assert.equal(parseTime(value), null, String(value))
  }
  assert.equal(parseTime(), null)
  assert.equal(parseTime('2024-02-29', '{y}-{m}-{d}'), '2024-02-29')
})
