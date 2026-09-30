import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const apiSource = readFileSync(new URL('../src/api/pipeline/manuscript.js', import.meta.url), 'utf8')
const pageSource = readFileSync(new URL('../src/views/pipeline/manuscript/index.vue', import.meta.url), 'utf8')
const routerSource = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const dashboardSource = readFileSync(new URL('../src/views/pipeline/dashboard/index.vue', import.meta.url), 'utf8')

test('manuscript api maps to migrated generation endpoints', () => {
  assert.match(apiSource, /url:\s*'\/manuscript\/generate'/)
  assert.match(apiSource, /url:\s*'\/manuscript\/jobs'/)
  assert.match(apiSource, /\/manuscript\/jobs\/\$\{jobId\}\/export/)
  assert.match(apiSource, /url:\s*'\/manuscript\/titles\/suggest'/)
})

test('manuscript page can generate, suggest titles and export markdown', () => {
  assert.match(pageSource, /generateManuscript/)
  assert.match(pageSource, /suggestManuscriptTitles/)
  assert.match(pageSource, /exportManuscript/)
  assert.match(pageSource, /downloadMarkdown/)
})

test('manuscript page has a direct router entry', () => {
  assert.match(routerSource, /path:\s*'\/pipeline\/manuscript'/)
  assert.match(routerSource, /PipelineManuscript/)
})

test('pipeline dashboard links to manuscript generation', () => {
  assert.match(dashboardSource, /\$router\.push\('\/pipeline\/manuscript'\)/)
})
