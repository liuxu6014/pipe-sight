import test from 'node:test'
import assert from 'node:assert/strict'
import { effectScope, ref } from 'vue'
import { resolveBasketSelection, useBasketSelection } from '../src/utils/portal/basketSelection.js'

test('explicit report selection never falls back to the whole basket', () => {
  const basket = [{ id: 'a' }, { id: 'b' }, { id: 'c' }]
  assert.deepEqual(resolveBasketSelection(basket, ['a', 'c', 'a']).items.map(x => x.id), ['a', 'c'])
  assert.equal(resolveBasketSelection(basket, ['missing']).items.length, 0)
  assert.equal(resolveBasketSelection(basket, ['missing']).missing, 1)
  assert.equal(resolveBasketSelection(basket, undefined).items.length, 3)
  assert.equal(resolveBasketSelection(basket, '').items.length, 0)
})

test('basket supports single/multiple selection and selects only filtered rows', () => {
  const scope = effectScope()
  const basket = ref([{ id: 'a' }, { id: 'b' }, { id: 'c' }])
  const visible = ref(basket.value)
  const epoch = ref(1)
  const state = scope.run(() => useBasketSelection(() => basket.value, () => visible.value, () => epoch.value))
  try {
    assert.equal(state.selectedItems.value.length, 0)
    state.toggle('a', true)
    state.toggle('a', true)
    state.toggle('b', true)
    assert.deepEqual(state.selectedIds.value, ['a', 'b'])
    state.toggle('a', false)
    visible.value = [basket.value[2]]
    state.toggleVisible(true)
    assert.deepEqual(state.selectedItems.value.map(x => x.id), ['b', 'c'])
    assert.equal(state.allVisible.value, true)
    state.toggleVisible(false)
    assert.deepEqual(state.selectedIds.value, ['b'])
    basket.value = [basket.value[0], basket.value[2]]
    assert.equal(state.selectedItems.value.length, 0)
    state.toggle('c', true)
    epoch.value++
    assert.equal(state.selectedItems.value.length, 0)
  } finally { scope.stop() }
})
