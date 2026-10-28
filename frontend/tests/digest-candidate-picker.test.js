import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import { effectScope, reactive, watch } from 'vue'
import { createDigestCandidateSearch } from '../src/utils/portal/digestCandidates.js'

const source = readFileSync(new URL('../src/views/portal/components/DigestCandidatePicker.vue', import.meta.url), 'utf8')
const setup = source.split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
const settled = () => new Promise(resolve => setImmediate(resolve))
function picker() {
  const props = reactive({ enabled: true, readOnly: false, selectedIds: ['1'] })
  const store = reactive({ workspaceEpoch: 1 }), events = [], calls = []
  let unmount
  const scope = effectScope()
  const context = vm.createContext({
    watch, createDigestCandidateSearch, defineProps: () => props, defineEmits: () => (event, row) => events.push({ event, row }), usePortalStore: () => store,
    onBeforeUnmount: fn => { unmount = fn },
    listPipelineIntelligence: async params => { calls.push(params); return { data: { rows: [{ id: String((params.pageNum - 1) * params.pageSize + 1), title: '合成资讯', category: 'news' }], total: 30 } } }
  })
  scope.run(() => vm.runInContext(`${setup}\nglobalThis.page = { search, select }`, context))
  return { props, store, events, calls, ...context.page, close() { unmount(); scope.stop() } }
}
test('the picker emits only current-page additions and preserves already-added flags across pages', async () => {
  const view = picker()
  try {
    await settled()
    view.select(view.search.rows.value[0])
    assert.equal(view.events.length, 0)
    const old = view.search.rows.value[0]
    await view.search.setPage(3)
    view.select(old)
    assert.equal(view.events.length, 0)
    view.select(view.search.rows.value[0])
    assert.equal(view.events[0].row.id, '21')
    view.props.selectedIds.push('21')
    view.select(view.search.rows.value[0])
    await view.search.setPage(1)
    view.select(view.search.rows.value[0])
    assert.equal(view.events.length, 1)
  } finally { view.close() }
})
test('hidden or read-only candidate panels do not fetch, and an account change clears query state', async () => {
  const view = picker()
  try {
    await settled()
    view.search.query.keyword = 'old private query'
    view.props.enabled = false
    await settled()
    assert.equal(view.search.rows.value.length, 0)
    view.props.readOnly = true; view.props.enabled = true
    view.store.workspaceEpoch++
    await settled()
    assert.equal(view.calls.length, 1)
    assert.equal(view.search.query.keyword, '')
  } finally { view.close() }
})
