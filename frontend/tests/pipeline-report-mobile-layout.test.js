import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const reportPage = readFileSync(new URL('../src/views/pipeline/report/index.vue', import.meta.url), 'utf8')

test('management report list wraps filters instead of showing an editorial landing page', () => {
  assert.match(reportPage, /@media \(max-width: 640px\) \{[\s\S]*?\.report-management-filters > \* \{[^}]*min-width: 0;/)
  assert.match(reportPage, /:data="filteredRows"/)
  assert.doesNotMatch(reportPage, /report-masthead|report-reading|本期主报告/)
})
