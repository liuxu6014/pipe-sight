import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { displayId, requireBusinessId } from './businessId.js'
import { useRoute, useRouter } from 'vue-router'

export function readListQuery(query, defaults, { pageSizes = [10, 20, 50], maxPage = Infinity } = {}) {
  const values = {}
  for (const [key, fallback] of Object.entries(defaults)) {
    const raw = query[key]
    if (Array.isArray(fallback)) values[key] = raw == null ? [...fallback] : (Array.isArray(raw) ? raw : [raw]).map(String)
    else if (typeof fallback === 'number') {
      const number = Number(raw)
      values[key] = Number.isSafeInteger(number) && number > 0 ? number : fallback
    } else values[key] = typeof raw === 'string' ? raw : fallback
  }
  if ('page' in values) values.page = Math.min(values.page, maxPage)
  if ('size' in values && !pageSizes.includes(values.size)) values.size = defaults.size
  return values
}

// Store only list controls in the URL; returning from a detail restores the query.
export function useListQuery(defaults, options = {}) {
  const route = useRoute()
  const router = useRouter()
  const path = route.path
  const query = reactive(readListQuery(route.query, defaults, options))
  let restored = ''
  watch(() => route.fullPath, () => {
    if (route.path !== path) return
    const next = readListQuery(route.query, defaults, options)
    if (JSON.stringify(next) === JSON.stringify(query)) return
    restored = JSON.stringify(next)
    Object.assign(query, next)
  })
  watch(() => JSON.stringify(query), (value, previous) => {
    if (route.path !== path) return
    if (value === restored) { restored = ''; return }
    const before = JSON.parse(previous)
    if (Object.keys(defaults).some(key => !['page', 'view'].includes(key) && JSON.stringify(query[key]) !== JSON.stringify(before[key]))) query.page = 1
    const next = { ...route.query }
    for (const [key, fallback] of Object.entries(defaults)) {
      delete next[key]
      if (JSON.stringify(query[key]) !== JSON.stringify(fallback)) next[key] = Array.isArray(query[key]) ? query[key] : String(query[key])
    }
    router.replace({ path, query: next, hash: route.hash }).catch(() => {})
  })
  return query
}

// Invalidate immediately, including during debounce, so stale responses cannot win.
export function useListRequest(params, request) {
  const data = ref(null)
  const loading = ref(false)
  const loadError = ref('')
  let generation = 0
  let timer
  let stopped = false
  async function run(snapshot, token) {
    try {
      const response = await request(snapshot)
      if (!stopped && token === generation) data.value = response.data || {}
    } catch (error) {
      if (!stopped && token === generation) loadError.value = error?.msg || error?.message || '请求失败，请稍后重试'
    } finally {
      if (!stopped && token === generation) loading.value = false
    }
  }
  function schedule(snapshot, delay = 0) {
    const token = ++generation
    clearTimeout(timer)
    data.value = null
    loadError.value = ''
    loading.value = true
    if (delay) timer = setTimeout(() => run(snapshot, token), delay)
    else return run(snapshot, token)
  }
  watch(params, (next, previous) => schedule(next, previous && next.keyword !== previous.keyword ? 250 : 0), { immediate: true, deep: true })
  onBeforeUnmount(() => { stopped = true; generation += 1; clearTimeout(timer) })
  return { data, loading, loadError, reload: () => schedule(params()) }
}

export function validPage(total, size, page, maxPage = Infinity) {
  return Math.min(Math.max(1, Math.ceil(total / size)), Math.max(1, page), maxPage)
}

export function materialBasketReason(item) {
  if (item.allowAiUse === false || item.allow_ai_use === false) return '该资料未允许用于 AI，请先查看授权范围'
  if ((item.scanStatus && item.scanStatus !== 'clean') || (item.scan_status && item.scan_status !== 'clean')) return '资料尚未通过安全检查'
  if (!['已解析', 'indexed'].includes(item.status)) return '资料尚未解析就绪，请在详情查看处理状态'
  return ''
}

// The existing store infers types from its initial catalog. List pages know the
// actual resource type, even for a later page or a global-search-only result.
export function useListWorkspace(store, { save, remove }) {
  const pending = ref(new Set())
  const inBasket = item => store.basket.some(entry => displayId(entry.id) === displayId(item.id))
  const busy = item => pending.value.has(displayId(item.id))
  async function persist(item, itemType, action = 'basket', toggle = false) {
    if (!item?.id || busy(item)) return 'pending'
    item = { ...item, id: requireBusinessId(item.id) }
    if (action === 'basket' && inBasket(item) && !toggle) return 'exists'
    const epoch = store.workspaceEpoch
    pending.value = new Set([...pending.value, item.id])
    try {
      const undoFavorite = action === 'favorite' && store.isFavorite(item.id)
      const undoBasket = action === 'basket' && toggle && inBasket(item)
      const title = item.titleZh || item.title || item.name || ''
      const snapshot = { title }
      for (const field of ['summary', 'abstract', 'source', 'sourceType', 'category', 'status', 'updatedAt', 'time', 'journal', 'year', 'authors', 'institutions', 'tags', 'doi', 'publishedDate', 'sourceUrl', 'format', 'owner', 'permission']) {
        if (item[field] != null) snapshot[field] = item[field]
      }
      if (undoBasket) await remove('basket', item.id)
      else if (undoFavorite) await remove('favorite', item.id)
      else await save({ itemId: item.id, itemType, action, title, snapshot })
      if (epoch !== store.workspaceEpoch) return 'stale'
      const entry = { ...snapshot, id: item.id, type: itemType }
      if (action === 'basket') {
        if (undoBasket) store.basket = store.basket.filter(saved => saved.id !== item.id)
        else if (!inBasket(item)) store.basket.push(entry)
      } else if (undoFavorite) {
        store.favorites = store.favorites.filter(id => id !== item.id)
        store.favoriteItems = store.favoriteItems.filter(saved => saved.id !== item.id)
      } else {
        if (!store.isFavorite(item.id)) store.favorites.push(item.id)
        store.favoriteItems = [...store.favoriteItems.filter(saved => saved.id !== item.id), entry]
      }
      return undoFavorite || undoBasket ? 'removed' : 'saved'
    } finally {
      const next = new Set(pending.value)
      next.delete(item.id)
      pending.value = next
    }
  }
  const toggleBasket = (item, itemType) => persist(item, itemType, 'basket', true)
  return { inBasket, busy, persist, toggleBasket, pendingCount: computed(() => pending.value.size) }
}
