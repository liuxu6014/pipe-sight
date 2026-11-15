import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'

const source = readFileSync(new URL('../src/views/pipeline/source/index.vue', import.meta.url), 'utf8')

test('source management uses a paged Element Plus list with permission-guarded inline actions', () => {
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'source-list' })
  const result = compileTemplate({ source: descriptor.template.content, filename: 'source-list.vue', id: 'source-list', compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(result.errors, [])
  assert.match(source, /<el-table[^>]*:data="pagedRows" row-key="id"[^>]*aria-label="数据源列表"[^>]*:aria-busy="loading"/)
  for (const label of ['数据源名称', '来源类型', '采集频率', '最后采集', '是否启用']) {
    assert.match(source, new RegExp(`<el-table-column[^>]*label="${label}"`))
  }
  assert.match(source, /<\/el-table>\s*<pagination v-model:page="page" v-model:limit="pageSize" :total="filteredRows.length"/)
  const actions = descriptor.template.content.match(/<div class="source-list-actions"[\s\S]*?<\/div>/)[0]
  assert.equal((actions.match(/<el-button /g) || []).length, 1)
  assert.equal((actions.match(/<el-switch /g) || []).length, 1)
  assert.match(actions, /v-if="canSourceSave && !isExternalSource\(row\)"/)
  assert.match(actions, /:model-value="sourceEnabled\(row\)"/)
  assert.match(actions, /@change="toggleSource\(row\)"/)
  assert.match(actions, /:disabled="!canSourceSave \|\| busy"/)
  assert.match(source, /v-if="canSourceSave"[^>]*@click="openCreateDialog">新增数据源/)
  assert.match(source, /:empty-text="loading \? '正在加载数据源…' : activeType === 'all' \? '暂无数据源'/)
  assert.doesNotMatch(source, /立即采集|翻译模型/)
  assert.match(source, /v-if="canSourceRun && !isExternalSource\(row\)"[^>]*@click="runSource\(row\)">试采/)
  assert.match(source, /<el-select v-model="sourceForm.sourceType"/)
})
