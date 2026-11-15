import { onBeforeUnmount, ref, watch } from 'vue'

// Invalidate immediately on account/query changes, even during the debounce.
export function usePagedResults(load, params, epoch, page, enabled) {
  const rows = ref([]), total = ref(0), error = ref(''), loading = ref(false)
  let request = 0, timer, stopped = false
  async function refresh() {
    clearTimeout(timer)
    const current = ++request
    if (enabled && !enabled.value) { loading.value = false; return }
    loading.value = true
    error.value = ''
    try {
      const response = await load(params.value)
      if (stopped || current !== request) return
      if (!Array.isArray(response.data?.rows) || !Number.isFinite(Number(response.data?.total))) throw new Error('列表响应无效')
      total.value = Number(response.data.total)
      const maximum = Math.max(1, Math.ceil(total.value / params.value.pageSize))
      if (page && page.value > maximum) { page.value = maximum; return }
      rows.value = response.data.rows
    } catch (failure) {
      if (!stopped && current === request) error.value = failure?.msg || failure?.message || '列表加载失败，请重试'
    } finally { if (current === request) loading.value = false }
  }
  watch([params, epoch, () => enabled?.value ?? true], (value, previous) => {
    ++request
    clearTimeout(timer)
    rows.value = []; total.value = 0; error.value = ''; loading.value = true
    if (enabled && !enabled.value) { loading.value = false; return }
    if (previous?.length && value[0].keyword !== previous[0]?.keyword) timer = setTimeout(refresh, 180)
    else void refresh()
  }, { immediate: true, deep: true, flush: 'sync' })
  onBeforeUnmount(() => { stopped = true; request++; clearTimeout(timer) })
  return { rows, total, error, loading, refresh, invalidate: () => { request++; clearTimeout(timer); loading.value = false } }
}
