import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { computed, ref, reactive, watch, effectScope } from 'vue'
import { decimalId } from '../src/utils/portal/businessId.js'
import { createSavedSearchRepository, normalizeSearchFilters, searchFilterChips, withoutSearchFilter } from '../src/utils/portal/savedSearches.js'

function setup(confirm = async () => {}) {
  const values = new Map(), events = []
  const storage = { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value) }
  const user = reactive({ id: '7' })
  const props = reactive({ kind: 'news', query: { q: '检测', source: '全部', tag: [] } })
  let unmount
  const scope = effectScope()
  const source = readFileSync(new URL('../src/views/portal/components/SavedSearchBar.vue', import.meta.url), 'utf8')
    .split('<script setup>')[1].split('</script>')[0].replace(/^import .*\n/gm, '')
  const context = vm.createContext({ computed, ref, watch, decimalId, createSavedSearchRepository, normalizeSearchFilters, searchFilterChips, withoutSearchFilter,
    defineProps: () => props, defineEmits: () => (...args) => events.push(args), useUserStore: () => user,
    onMounted() {}, onBeforeUnmount(fn) { unmount = fn }, window: { localStorage: storage, removeEventListener() {} },
    ElMessage: { success() {} }, ElMessageBox: { confirm },
  })
  scope.run(() => vm.runInContext(`${source}\nglobalThis.state = { saved, name, error, queryState, canSave, saveCurrent, applyEntry, removeEntry }`, context))
  return { state: context.state, storage, user, props, events, close() { unmount(); scope.stop() } }
}

test('saving is explicit; account switch clears visible conditions immediately', () => {
  const view = setup()
  try {
    assert.equal(view.state.saved.value.length, 0)
    view.state.name.value = '检测资料'
    view.state.saveCurrent()
    assert.equal(view.state.saved.value.length, 1)
    view.state.applyEntry(view.state.saved.value[0])
    assert.equal(view.events[0][0], 'apply')
    assert.equal(view.events[0][1].q, '检测')
    view.user.id = '8'
    assert.equal(view.state.saved.value.length, 0)
    view.user.id = '7'
    assert.equal(view.state.saved.value.length, 1)
  } finally { view.close() }
})

test('storage failure retains the current list and exposes a failure instead of success', () => {
  const view = setup()
  try {
    view.state.name.value = '检测资料'; view.state.saveCurrent()
    view.storage.setItem = () => { throw new Error('quota') }
    view.props.query.q = '新关键词'
    view.state.saveCurrent()
    assert.equal(view.state.saved.value.length, 1)
    assert.match(view.state.error.value, /无法保存/)
    view.props.query.source = '非法来源'
    assert.equal(view.state.canSave.value, false)
    assert.match(view.state.queryState.value.error, /不可用/)
  } finally { view.close() }
})

test('a pending removal cannot delete a previous accounts conditions after switching users', async () => {
  let resolve
  const view = setup(() => new Promise(yes => { resolve = yes }))
  try {
    view.state.name.value = '检测资料'; view.state.saveCurrent()
    const pending = view.state.removeEntry(view.state.saved.value[0])
    view.user.id = '8'
    resolve(); await pending
    view.user.id = '7'
    assert.equal(view.state.saved.value.length, 1)
  } finally { view.close() }
})
