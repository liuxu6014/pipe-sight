import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { formatReportDate, getReportStatusMeta } from '../src/utils/pipeline/reportPresentation.js'

test('report editor omits quality review UI and keeps three functional inspector tabs', () => {
  const source = readFileSync(new URL('../src/views/portal/pages/ReportEditorView.vue', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /质量问题|ps-completeness|mapQualityIssues|locateIssue|qualityIssues/)
  assert.match(source, /const rightTabs = \['引用来源', '版本记录', '导出记录'\]/)
  assert.match(source, /grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/)
})

test('formats a report date for the editorial masthead', () => {
  assert.equal(formatReportDate('2026-07-13'), '2026年07月13日')
})

test('ignores a report timestamp when building the edition date', () => {
  assert.equal(formatReportDate('2026-07-13 10:30:00'), '2026年07月13日')
})

test('maps a reviewing report to its readable status', () => {
  assert.deepEqual(getReportStatusMeta('reviewing'), { label: '审核中', type: 'warning' })
})

test('maps persisted report lifecycle statuses without falling back to draft', () => {
  assert.deepEqual(getReportStatusMeta('completed'), { label: '已生成', type: 'success' })
  assert.deepEqual(getReportStatusMeta('published'), { label: '已发布', type: 'success' })
  assert.deepEqual(getReportStatusMeta('archived'), { label: '已归档', type: 'info' })
  assert.deepEqual(getReportStatusMeta('failed'), { label: '生成失败', type: 'danger' })
})
