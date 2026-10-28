import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { effectScope, reactive, ref, watch } from 'vue'
import { createExportHistory } from '../src/utils/portal/exportHistory.js'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'
import { exportFormatLabel, exportStatusLabel } from '../src/utils/portal/exportHistory.js'

const source = readFileSync(new URL('../src/views/portal/components/ReportExportHistory.vue', import.meta.url), 'utf8')
const setup = source.split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
const settled = () => new Promise(resolve => setImmediate(resolve))
function component() {
  const props = reactive({ reportId: '40', readOnly: false, refreshKey: 0, title: '测试' })
  const store = reactive({ workspaceEpoch: 1 })
  const listeners = new Map(), calls = []
  const document = { hidden: false, addEventListener: (event, fn) => listeners.set(event, fn), removeEventListener: event => listeners.delete(event) }
  let unmount
  const scope = effectScope()
  const context = vm.createContext({
    ref, watch, defineProps: () => props, usePortalStore: () => store, document, createExportHistory,
    listPipelineResearchReportExports: async id => { calls.push(id); return { data: { rows: [{ exportId: '81', reportId: id, format: 'docx', status: 'completed' }] } } },
    downloadPipelineResearchReportExport() {}, onMounted: fn => fn(), onBeforeUnmount: fn => { unmount = fn }
  })
  scope.run(() => vm.runInContext(`${setup}\nglobalThis.page = { history }`, context))
  return { props, store, calls, listeners, document, ...context.page, close() { unmount(); scope.stop() } }
}
test('history component clears account-scoped records and never reads exports in read-only inspection', async () => {
  const view = component()
  try {
    await settled()
    assert.equal(view.history.records.value.length, 1)
    view.props.readOnly = true
    view.store.workspaceEpoch++
    await settled()
    assert.equal(view.history.records.value.length, 0)
    assert.equal(view.calls.length, 1)
  } finally { view.close() }
})
test('history component pauses while the document is hidden and refreshes on return', async () => {
  const view = component()
  await settled()
  view.document.hidden = true; view.listeners.get('visibilitychange')()
  await settled()
  assert.equal(view.history.records.value.length, 0)
  view.document.hidden = false; view.listeners.get('visibilitychange')()
  await settled()
  assert.equal(view.calls.length, 2)
  view.close()
  assert.equal(view.listeners.size, 0)
})

test('shared history identifies reports and shows export format and time without a version concept', async () => {
  const template = source.split('<template>')[1].split('</template>\n\n<script setup>')[0]
  const render = new Function('Vue', compile(template, { mode: 'function', prefixIdentifiers: true }).code)(Vue)
  const app = Vue.createSSRApp({ render, setup: () => ({
    subject: '报告', loading: false, readOnly: false, error: '', downloadError: '', downloadingId: '',
    records: [{ exportId: '81', format: 'docx', status: 'completed', reportVersionNo: 2, createdAt: '2026-10-27 12:00:00' }],
    history: { refresh() {}, download() {} }, exportFormatLabel, exportStatusLabel, formatBusinessTime: value => value
  }) })
  app.component('el-button', { template: '<button><slot /></button>' })
  app.component('ElButton', { template: '<button><slot /></button>' })
  const html = await renderToString(app)
  assert.match(html, /aria-label="报告导出记录"/)
  assert.match(html, /Word/)
  assert.match(html, /2026-10-27 12:00:00/)
  assert.doesNotMatch(html, /版本|V2/)
})
