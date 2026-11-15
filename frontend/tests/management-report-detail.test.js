import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'

const filename = new URL('../src/views/pipeline/report/components/ReportDetailDialog.vue', import.meta.url)
const source = readFileSync(filename, 'utf8')
const { descriptor } = parse(source)
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
const settle = async () => { await nextTick(); await new Promise(setImmediate); await nextTick() }

function harness(load) {
  const props = reactive({ modelValue: true, reportId: '203' })
  const context = vm.createContext({ computed, ref, watch, onBeforeUnmount() {}, defineProps: () => props, defineEmits: () => () => {}, getPipelineResearchReport: load, isDigestType: type => ['weekly', 'monthly', 'daily'].includes(type) })
  const script = descriptor.scriptSetup.content.replace(/^import .*$/gm, '')
  const scope = effectScope()
  scope.run(() => vm.runInContext(`${script}\nglobalThis.view = { report, loading, loadError, sections, isDigest, loadDetail }`, context))
  return { props, view: context.view, stop: () => scope.stop() }
}

test('management report dialog compiles as a read-only reader', () => {
  const script = compileScript(descriptor, { id: 'management-report-detail' })
  const template = compileTemplate({ source: descriptor.template.content, filename: filename.pathname, id: 'management-report-detail', compilerOptions: { bindingMetadata: script.bindings } })
  assert.deepEqual(template.errors, [])
})

test('late detail responses cannot replace the report currently being inspected', async () => {
  const first = deferred(), second = deferred(), calls = []
  const { props, view, stop } = harness(id => { calls.push(id); return id === '203' ? first.promise : second.promise })
  try {
    props.reportId = '204'
    await settle()
    second.resolve({ data: { id: '204', title: '月报', type: 'monthly', content: '月报正文' } })
    await settle()
    first.resolve({ data: { id: '203', title: '旧报告', content: '旧正文' } })
    await settle()
    assert.deepEqual(calls, ['203', '204'])
    assert.equal(view.report.value.title, '月报')
    assert.equal(view.sections.value[0].content, '月报正文')
    assert.equal(view.isDigest.value, true)
  } finally { stop() }
})

test('closing the reader clears content and ignores the outstanding request', async () => {
  const pending = deferred()
  const { props, view, stop } = harness(() => pending.promise)
  try {
    props.modelValue = false
    await settle()
    pending.resolve({ data: { id: '203', title: '已关闭报告', content: '正文' } })
    await settle()
    assert.equal(view.report.value, null)
    assert.equal(view.loading.value, false)
  } finally { stop() }
})

test('detail errors remain retryable and a mismatched report is never displayed', async () => {
  let attempt = 0
  const { view, stop } = harness(async () => ({ data: { id: ++attempt === 1 ? '204' : '203', content: '正确正文' } }))
  try {
    await settle()
    assert.match(view.loadError.value, /编号不匹配/)
    assert.equal(view.report.value, null)
    await view.loadDetail()
    assert.equal(view.loadError.value, '')
    assert.equal(view.sections.value[0].content, '正确正文')
  } finally { stop() }
})
