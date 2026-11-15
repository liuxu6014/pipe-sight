import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'

const source = readFileSync(new URL('../src/views/pipeline/report/index.vue', import.meta.url), 'utf8')
const router = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')

test('digest management shares the compact full-width report management layout', () => {
  assert.match(router, /path: '\/pipeline\/digest',[\s\S]*?component: \(\) => import\('@\/views\/pipeline\/report\/index.vue'\)/)
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'report-management-layout' })
  const result = compileTemplate({ source: descriptor.template.content, filename: 'report-management.vue', id: 'report-management-layout', compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(result.errors, [])
  assert.match(source, /reportKind === 'digest' \? '简报列表' : '报告列表'/)
  assert.match(source, /<div class="report-list-header">\s*<span>序号<\/span>\s*<span>\{\{ reportKind === 'digest' \? '简报信息' : '报告信息' \}\}<\/span>\s*<span>操作<\/span>/)
  assert.match(source, /class="panel-card report-list-card ws-list-panel"/)
  assert.match(source, /class="panel-card report-filter-card"/)
  assert.match(source, /class="report-management-scope" aria-live="polite"/)
  assert.doesNotMatch(descriptor.template.content, /eyebrow|科研报告记录|当前成果状态与输出记录|正文与原始证据的访问权限分别校验/)
  assert.match(source, /v-if="reportKind === 'digest' && reportPeriod\(row\)">覆盖周期/)
  assert.match(source, /@click="openReport\(row\)"/)
  assert.match(source, /v-hasPermi="\['pipeline:report:export'\]"/)
})

test('report entries use a list with status, timestamp and actions', () => {
  assert.doesNotMatch(source, /<el-table\b/)
  assert.match(source, /<li v-for="\(row, index\) in pagedRows" :key="row.id"/)
  assert.match(source, /class="report-list-index">\{\{ pageOffset \+ index \+ 1 \}\}/)
  assert.match(source, /<pagination\s+v-if="total"\s+v-model:page="page"\s+v-model:limit="pageSize"\s+:total="total"/)
  assert.match(source, /usePagedResults\(listPipelineAdminReports, params/)
  assert.doesNotMatch(source, /filteredRows\.value\.slice/)
  assert.match(source, /<h2>\{\{ row.title \}\}<\/h2>/)
  assert.match(source, /getReportStatusMeta\(row.status\).label/)
  assert.match(source, /更新于 \{\{ row.updated_at \|\| row.updatedAt \}\}/)
})
