import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'

const source = readFileSync(new URL('../src/views/pipeline/source/index.vue', import.meta.url), 'utf8')

test('source management renders semantic list rows with inline actions instead of a grid table', () => {
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'source-list' })
  const result = compileTemplate({ source: descriptor.template.content, filename: 'source-list.vue', id: 'source-list', compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(result.errors, [])
  assert.match(source, /<ul class="source-list" aria-label="数据源列表">/)
  assert.match(source, /<li v-for="row in rows" :key="row.id" class="source-list-item">/)
  assert.doesNotMatch(descriptor.template.content, /<el-table/)
  for (const field of ['row.name', 'typeText(row.type)', 'sourceEnabled(row)', 'row.cron', 'row.lastRunAt']) assert.ok(descriptor.template.content.includes(field))
  for (const handler of ['openSourceDialog(row)', 'runSource(row)', 'toggleSource(row)']) assert.ok(descriptor.template.content.includes(handler))
  assert.match(source, /:disabled="!sourceEnabled\(row\) \|\| Boolean\(runningSourceId\)"/)
  assert.match(source, /v-if="!loading && !rows.length" description="暂无数据源"/)
  assert.match(source, /:aria-busy="loading"/)
})
