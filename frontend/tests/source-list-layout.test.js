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
  for (const field of ['row.name', 'typeText(row.type)', 'sourceEnabled(row)', 'sourceFrequencyText(sourceCron(row))', 'row.lastRunAt']) assert.ok(descriptor.template.content.includes(field))
  for (const handler of ['openFrequencyDialog(row)', 'toggleSource(row)']) assert.ok(descriptor.template.content.includes(handler))
  const actions = descriptor.template.content.match(/<div class="source-list-actions"[\s\S]*?<\/div>/)[0]
  assert.equal((actions.match(/<el-button /g) || []).length, 1)
  assert.equal((actions.match(/<el-switch /g) || []).length, 1)
  assert.match(actions, /:model-value="sourceEnabled\(row\)"/)
  assert.match(actions, /@change="toggleSource\(row\)"/)
  assert.match(actions, /:disabled="busy"/)
  assert.match(descriptor.template.content, /新增公众号/)
  assert.doesNotMatch(source, /runSource|runPipelineTask|立即采集|翻译模型|sourceForm\.sourceType/)
  assert.match(source, /v-if="!loading && !rows.length" description="暂无数据源"/)
  assert.match(source, /:aria-busy="loading"/)
})
