import { ref } from 'vue'
import { decimalId } from './businessId.js'

export const exportStatusLabel = status => ({ queued: '排队中', running: '导出中', completed: '可下载', failed: '导出失败' })[status] || '状态未记录'
export const exportFormatLabel = format => ({ docx: 'Word', pdf: 'PDF' })[format] || '文件格式未记录'

// This reader never creates or retries an export; it only observes existing jobs.
export function createExportHistory(api, timers = globalThis) {
  const records = ref([]), loading = ref(false), error = ref(''), downloadError = ref(''), downloadingId = ref('')
  let context = {}, generation = 0, stopped = false, timer, failures = 0
  function clearTimer() { if (timer !== undefined) timers.clearTimeout(timer); timer = undefined }
  function schedule() {
    clearTimer()
    if (!stopped && context.enabled && (error.value || records.value.some(row => ['queued', 'running'].includes(row.status)))) {
      timer = timers.setTimeout(() => { timer = undefined; return refresh() }, Math.min(30000, 3000 * 2 ** Math.min(failures, 4)))
    }
  }
  async function refresh() {
    if (stopped || !context.enabled || loading.value || !decimalId(context.reportId)) return
    const token = generation, id = String(context.reportId)
    loading.value = true
    try {
      const response = await api.list(id)
      if (stopped || token !== generation) return
      const rows = response?.data?.rows
      if (!Array.isArray(rows) || rows.some(row => !row || !decimalId(row.exportId) || !['docx', 'pdf'].includes(row.format) || (row.reportId != null && String(row.reportId) !== id)) || new Set(rows.map(row => String(row.exportId))).size !== rows.length) throw new Error('导出记录返回格式无效，请重试')
      records.value = rows
      error.value = ''; failures = 0
    } catch (reason) {
      if (stopped || token !== generation) return
      failures++
      error.value = reason?.msg || reason?.message || '导出记录暂时无法加载，请重试'
    } finally {
      if (!stopped && token === generation) { loading.value = false; schedule() }
    }
  }
  async function configure(next) {
    generation++; clearTimer(); context = { ...next }
    records.value = []; loading.value = false; error.value = ''; downloadError.value = ''; downloadingId.value = ''; failures = 0
    if (!stopped && context.enabled) await refresh()
  }
  async function download(row) {
    if (stopped || !context.enabled || !context.canDownload || downloadingId.value) return
    const record = records.value.find(item => String(item.exportId) === String(row?.exportId))
    if (!record || record.status !== 'completed' || !['docx', 'pdf'].includes(record.format)) return
    const token = generation, id = String(record.exportId)
    downloadingId.value = id; downloadError.value = ''
    const title = String(context.title || '情报简报').replace(/[\\/:*?"<>|\u0000-\u001f]/g, '_').trim().slice(0, 150) || '情报简报'
    try {
      await api.download(id, `${title}.${record.format}`)
    } catch (reason) {
      if (!stopped && token === generation) downloadError.value = reason?.msg || reason?.message || '文件下载失败，请重试'
    } finally { if (!stopped && token === generation) downloadingId.value = '' }
  }
  function dispose() { stopped = true; generation++; clearTimer(); records.value = []; loading.value = false; error.value = ''; downloadError.value = ''; downloadingId.value = ''; context = {} }
  return { records, loading, error, downloadError, downloadingId, configure, refresh, download, dispose }
}
