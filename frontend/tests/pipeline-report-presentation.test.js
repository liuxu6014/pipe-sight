import test from 'node:test'
import assert from 'node:assert/strict'
import { formatReportDate, getReportStatusMeta } from '../src/utils/pipeline/reportPresentation.js'

test('formats a report date for the editorial masthead', () => {
  assert.equal(formatReportDate('2026-07-13'), '2026年07月13日')
})

test('ignores a report timestamp when building the edition date', () => {
  assert.equal(formatReportDate('2026-07-13 10:30:00'), '2026年07月13日')
})

test('maps a reviewing report to its readable status', () => {
  assert.deepEqual(getReportStatusMeta('reviewing'), { label: '审核中', type: 'warning' })
})
