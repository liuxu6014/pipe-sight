import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'

test('intelligence search has one submit action and one content-type filter', () => {
  const source = readFileSync(new URL('../src/views/pipeline/intelligence/index.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'intelligence-filters' })
  const result = compileTemplate({ source: descriptor.template.content, filename: 'intelligence.vue', id: 'intelligence-filters', compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(result.errors, [])
  assert.equal((descriptor.template.content.match(/<el-select /g) || []).length, 1)
  assert.equal((descriptor.template.content.match(/native-type="submit"/g) || []).length, 1)
  assert.match(source, /@submit.prevent="handleQuery"/)
  assert.match(source, /v-model="queryParams.category" aria-label="内容类型"/)
  assert.doesNotMatch(source, /sourceType|>检索<|class="eyebrow"|class="summary"/)
  assert.match(source, /\.keyword-filter :deep\(\.el-input\) \{ width: 100%; \}/)
  assert.match(source, /function handleQuery\(\) \{ queryParams.pageNum = 1; getList\(\) \}/)
})

test('intelligence renders articles as a semantic list with content, metadata and pagination', () => {
  const source = readFileSync(new URL('../src/views/pipeline/intelligence/index.vue', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /<el-table/)
  assert.match(source, /<ul v-if="rows.length" class="intelligence-list" aria-label="情报列表">/)
  assert.match(source, /<li v-for="row in rows" :key="row.id" class="intelligence-item">/)
  for (const value of ['row.title', 'row.summary', 'row.source', 'row.tags', 'formatBusinessTime(row.publish_time)', 'categoryText(row.category)', '@click="openDetail(row)"', '@pagination="getList"']) assert.ok(source.includes(value))
  assert.match(source, /:aria-busy="loading"/)
  assert.match(source, /v-else-if="!loading" description="暂无匹配的情报"/)
  assert.match(source, /\.title-button \{[^}]*white-space: normal;[^}]*overflow-wrap: anywhere;/)
  assert.match(source, /\.row-summary \{[^}]*-webkit-line-clamp: 3;[^}]*overflow: hidden;/)
})
