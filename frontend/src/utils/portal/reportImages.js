import { ref, watch, onScopeDispose } from 'vue'

const pending = status => ['queued', 'running'].includes(status)
const imageTypes = new Set(['image/png', 'image/jpeg', 'image/webp', 'image/gif'])
export const imageStatusLabel = status => ({ queued: '排队中', running: '生成中', completed: '已生成', failed: '生成失败' })[status] || status

export function useReportImages(reportId, api, { epoch = () => 0, urls = URL, timers = globalThis } = {}) {
  const images = ref([]), loading = ref(false), loadError = ref(''), actionError = ref('')
  let stopped = false, generation = 0, timer
  const objectUrls = new Set()
  function release(url) { if (objectUrls.delete(url)) urls.revokeObjectURL(url) }
  function clear() { for (const url of [...objectUrls]) release(url) }
  function schedule() {
    timers.clearTimeout(timer)
    if (!stopped && reportId() && (loadError.value || images.value.some(row => pending(row.status)))) {
      timer = timers.setTimeout(() => load(), 3000)
    }
  }
  async function readImage(row, token) {
    if (stopped || row.status !== 'completed' || row.imageUrl || row.imageLoading) return
    if (!row.url) { row.imageError = '资源未返回文件地址，请刷新后重试'; return }
    row.imageLoading = true; row.imageError = ''
    try {
      const blob = await api.getImage(row.id)
      if (stopped || token !== generation || !images.value.includes(row)) return
      if (!blob || !blob.size || !imageTypes.has(blob.type?.split(';')[0])) throw new Error('返回内容不是有效图片，请检查资源状态或访问权限')
      const url = urls.createObjectURL(blob)
      objectUrls.add(url); row.imageUrl = url
      row.extension = ({ 'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/gif': 'gif' })[blob.type.split(';')[0]]
    } catch (error) { if (!stopped && token === generation) row.imageError = error?.msg || error?.message || '图片读取失败，请重试' }
    finally { if (!stopped && token === generation) row.imageLoading = false }
  }
  async function load() {
    if (stopped || loading.value || !reportId()) return
    const token = generation, id = String(reportId())
    loading.value = true
    try {
      const response = await api.getMetadata(id)
      if (stopped || token !== generation) return
      const data = response.data
      if (String(data?.reportId) !== id || !Array.isArray(data.images) || data.images.some(row => !row.id || !['queued', 'running', 'completed', 'failed'].includes(row.status)) || new Set(data.images.map(row => row.id)).size !== data.images.length) throw new Error('配图资源返回格式无效，请重试')
      const previous = new Map(images.value.map(row => [row.id, row]))
      const retained = new Set()
      images.value = data.images.map(row => {
        const old = previous.get(row.id)
        const imageUrl = row.status === 'completed' ? old?.imageUrl || '' : ''
        if (imageUrl) retained.add(imageUrl)
        return { ...row, imageUrl, extension: old?.extension || 'png', imageLoading: false, imageError: '', retrying: old?.retrying || false }
      })
      for (const url of [...objectUrls]) if (!retained.has(url)) release(url)
      loadError.value = ''
      await Promise.all(images.value.map(row => readImage(row, token)))
    } catch (error) { if (!stopped && token === generation) loadError.value = error?.msg || error?.message || '配图加载失败，请重试' }
    finally { if (!stopped && token === generation) { loading.value = false; schedule() } }
  }
  async function retry(row) {
    if (stopped || row.status !== 'failed' || row.retrying) return
    const token = generation
    row.retrying = true; actionError.value = ''
    try {
      await api.retry(row.id)
      if (!stopped && token === generation) await load()
    } catch (error) { if (!stopped && token === generation) actionError.value = error?.msg || error?.message || '配图重试请求失败，请检查后台模型配置' }
    finally { if (!stopped && token === generation) { row.retrying = false; const current = images.value.find(item => item.id === row.id); if (current) current.retrying = false } }
  }
  function reloadImage(row) { release(row.imageUrl); row.imageUrl = ''; return readImage(row, generation) }
  watch(() => [reportId(), epoch()], () => {
    generation++; timers.clearTimeout(timer); clear()
    images.value = []; loading.value = false; loadError.value = ''; actionError.value = ''
    void load()
  }, { immediate: true })
  onScopeDispose(() => { stopped = true; generation++; timers.clearTimeout(timer); clear() })
  return { images, loading, loadError, actionError, load, retry, reloadImage }
}
