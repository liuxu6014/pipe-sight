import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const reportPage = readFileSync(new URL('../src/views/pipeline/report/index.vue', import.meta.url), 'utf8')

test('uses a wrapped report navigation layout on narrow screens', () => {
  assert.match(reportPage, /@media \(max-width: 640px\) \{[\s\S]*?\.report-section-nav \{[^}]*overflow-x: visible;/)
  assert.match(reportPage, /\.report-section-nav button \{[^}]*min-width: 0;/)
})
