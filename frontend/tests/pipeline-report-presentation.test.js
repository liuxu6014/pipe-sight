import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { canExportReport, formatReportDate, getReportStatusMeta } from '../src/utils/pipeline/reportPresentation.js'

test('report editor keeps source and export records without user-facing versions', () => {
  const source = readFileSync(new URL('../src/views/portal/pages/ReportEditorView.vue', import.meta.url), 'utf8')
  const template = source.split('<script setup>')[0]
  // Keep the generic quality/version inspector absent. Recorded deterministic
  // outline warnings are supported; report-quality-status.test.js exercises
  // their live, stale and missing-check behavior.
  assert.doesNotMatch(source, /质量问题|ps-completeness|mapQualityIssues|locateIssue/)
  assert.doesNotMatch(template, /qualityIssues|qualityScore|qualityStatus|质量评分|title="事实核验通过"|title="质量检查已通过"/)
  assert.match(template, /class="ps-outline-check-status"[^>]*:title="outlineCheckLabel"[^>]*:description="outlineCheckDescription"[^>]*type="warning"/)
  assert.match(source, /modelSnapshot\?\.checks\?\.outline/)
  assert.match(source, /const rightTabs = \['引用来源', '导出记录'\]/)
  assert.doesNotMatch(source.split('<script setup>')[0], /版本|report\.version/)
  assert.match(source, /grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/)
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
  assert.deepEqual(getReportStatusMeta('queued'), { label: '排队中', type: 'primary' })
  assert.deepEqual(getReportStatusMeta('running'), { label: '生成中', type: 'primary' })
})

test('management export requires saved output rather than a task status', () => {
  for (const status of ['draft', 'queued', 'running', 'failed', 'completed']) {
    assert.equal(canExportReport({ status, hasOutput: false }), false)
  }
  assert.equal(canExportReport(null), false)
  assert.equal(canExportReport({ status: 'completed' }), false)
  // A failed retry must not hide a previously saved result.
  assert.equal(canExportReport({ status: 'failed', hasOutput: true }), true)
  assert.equal(canExportReport({ status: 'completed', hasOutput: true }), true)
})

test('management export prevents empty output and duplicate concurrent downloads', () => {
  const source = readFileSync(new URL('../src/views/pipeline/report/index.vue', import.meta.url), 'utf8')
  assert.match(source, /:disabled="!canExportReport\(row\) \|\| Boolean\(downloadingReportId\)"/)
  assert.match(source, /if \(!canExportReport\(row\) \|\| downloadingReportId.value\) return/)
})
