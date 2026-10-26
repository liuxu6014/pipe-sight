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
  assert.match(source, /reportKind === 'digest' \? '简报管理' : '报告管理'/)
  assert.match(source, /\.pipeline-report-page \.report-review-table\s*\{\s*width: 100%; margin: 0; padding: 0;/)
  assert.match(source, /class="panel-card report-filter-card"/)
  assert.match(source, /class="report-management-scope" aria-live="polite"/)
  assert.doesNotMatch(descriptor.template.content, /eyebrow|科研报告记录|当前成果状态与输出记录|正文与原始证据的访问权限分别校验/)
  assert.match(source, /v-if="reportKind === 'digest'" prop="period"/)
  assert.match(source, /@click="openReport\(row\)"/)
  assert.match(source, /v-hasPermi="\['pipeline:report:export'\]"/)
})

test('digest columns reserve space for status and timestamp without a fixed action overlay', () => {
  assert.match(source, /prop="updated_at" label="更新时间" width="180"/)
  assert.match(source, /prop="status" label="业务状态" :width="reportKind === 'digest' \? 105 : 120"/)
  assert.match(source, /label="操作" :width="reportKind === 'digest' \? 210 : 250" :fixed="reportKind === 'digest' \? false : 'right'"/)
  assert.match(source, /prop="title" label="成果名称" :min-width="reportKind === 'digest' \? 200 : 260"/)
})
