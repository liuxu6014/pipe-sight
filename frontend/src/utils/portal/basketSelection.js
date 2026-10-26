import { computed, ref, watch } from 'vue'
import { displayId, decimalId } from './businessId.js'

export function resolveBasketSelection(basket, query) {
  if (query === undefined) return { items: basket.map(item => ({ ...item, id: displayId(item.id) })), missing: 0, upgraded: basket.some(item => !decimalId(item.id)) }
  const ids = [...new Set((Array.isArray(query) ? query : [query]).filter(id => typeof id === 'string' && id.trim()))]
  const byId = new Map(basket.map(item => [displayId(item.id), { ...item, id: displayId(item.id) }]))
  return { items: ids.map(id => byId.get(id)).filter(Boolean), missing: ids.filter(id => !byId.has(id)).length, upgraded: ids.some(id => !decimalId(id)) }
}

export function useBasketSelection(getBasket, getVisible, getEpoch) {
  const selectedIds = ref([])
  const selectedItems = computed(() => getBasket().filter(item => selectedIds.value.includes(displayId(item.id))))
  const visibleSelected = computed(() => getVisible().filter(item => selectedIds.value.includes(displayId(item.id))).length)
  const allVisible = computed(() => getVisible().length > 0 && visibleSelected.value === getVisible().length)
  const indeterminate = computed(() => visibleSelected.value > 0 && !allVisible.value)
  function toggle(id, checked) {
    id = displayId(id)
    if (!getBasket().some(item => displayId(item.id) === id)) return
    selectedIds.value = checked ? [...new Set([...selectedIds.value, id])] : selectedIds.value.filter(value => value !== id)
  }
  function toggleVisible(checked) { getVisible().forEach(item => toggle(item.id, checked)) }
  watch(() => getBasket().map(item => displayId(item.id)), ids => {
    selectedIds.value = selectedIds.value.filter(id => ids.includes(id))
  }, { flush: 'sync' })
  watch(getEpoch, () => { selectedIds.value = [] }, { flush: 'sync' })
  return { selectedIds, selectedItems, allVisible, indeterminate, toggle, toggleVisible }
}
