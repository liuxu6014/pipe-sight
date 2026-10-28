<template>
  <section class="ps-export-history" :aria-label="`${subject}导出记录`" :aria-busy="loading">
    <div class="ps-export-history-head"><strong>{{ records.length ? `${records.length} 条记录` : '导出状态' }}</strong><el-button plain :loading="loading" :disabled="readOnly" @click="history.refresh">刷新</el-button></div>
    <p v-if="readOnly" class="ps-export-note">导出文件由{{ subject }}所有者查看和下载。</p>
    <template v-else>
      <p class="ps-export-note">文件保留提交导出时的内容，不一定包含后续修改。处理进度自动更新，无需重复提交。</p>
      <p v-if="error" class="ps-export-error" role="alert">{{ error }}；正在自动重试。</p>
      <p v-if="downloadError" class="ps-export-error" role="alert">{{ downloadError }}</p>
      <p v-if="loading && !records.length" role="status">正在读取导出记录…</p>
      <ul v-else-if="records.length" class="ps-export-history-list">
        <li v-for="record in records" :key="record.exportId">
          <div><strong>{{ exportFormatLabel(record.format) }}</strong><span :class="`is-${record.status}`">{{ exportStatusLabel(record.status) }}</span></div>
          <time>{{ formatBusinessTime(record.createdAt) || '提交时间未记录' }}</time>
          <p v-if="record.errorMessage" class="ps-export-error">{{ record.errorMessage }}</p>
          <el-button v-if="record.status === 'completed'" plain type="primary" :loading="downloadingId === String(record.exportId)" :disabled="Boolean(downloadingId)" :aria-label="`下载 ${exportFormatLabel(record.format)} 文件`" @click="history.download(record)">下载文件</el-button>
          <small v-else-if="record.status === 'failed'">核对失败原因后，可从顶部重新导出。</small>
        </li>
      </ul>
      <p v-else-if="!error" class="ps-export-note">尚无导出记录，可从顶部选择 Word 或 PDF。</p>
    </template>
  </section>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { createExportHistory, exportFormatLabel, exportStatusLabel } from '@/utils/portal/exportHistory'
import { formatBusinessTime } from '@/utils/portal/businessTime'
import { listPipelineResearchReportExports, downloadPipelineResearchReportExport } from '@/api/pipeline/intelligence'
import usePortalStore from '@/store/modules/portal'

const props = defineProps({ subject: { type: String, default: '简报' }, reportId: { type: String, required: true }, title: { type: String, default: '' }, readOnly: Boolean, refreshKey: { type: Number, default: 0 } })
const store = usePortalStore()
const visible = ref(!document.hidden)
const history = createExportHistory({ list: listPipelineResearchReportExports, download: downloadPipelineResearchReportExport })
const { records, loading, error, downloadError, downloadingId } = history
watch(() => [props.reportId, props.readOnly, store.workspaceEpoch, visible.value], () => history.configure({
  reportId: props.reportId, epoch: store.workspaceEpoch, enabled: visible.value && !props.readOnly, canDownload: !props.readOnly, title: props.title
}), { immediate: true, flush: 'sync' })
watch(() => props.refreshKey, () => history.refresh())
function onVisibility() { visible.value = !document.hidden }
onMounted(() => document.addEventListener('visibilitychange', onVisibility))
onBeforeUnmount(() => { history.dispose(); document.removeEventListener('visibilitychange', onVisibility) })
</script>

<style scoped>
.ps-export-history-head, .ps-export-history-list li > div { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.ps-export-history-head strong { font-size: 14px; }
.ps-export-note, .ps-export-history-list time, .ps-export-history-list small { color: var(--ps-muted); font-size: 12px; line-height: 1.65; }
.ps-export-history-list { padding: 0; margin: 12px 0 0; list-style: none; }
.ps-export-history-list li { padding: 14px 0; border-top: 1px solid var(--ps-line-soft); overflow-wrap: anywhere; }
.ps-export-history-list strong { font-size: 14px; }
.ps-export-history-list span { font-size: 12px; color: var(--ps-muted); }
.ps-export-history-list time, .ps-export-history-list small { display: block; margin-top: 6px; }
.ps-export-history-list .is-completed { color: var(--ps-green); }
.ps-export-history-list .is-failed, .ps-export-error { color: var(--ps-danger); }
.ps-export-error { font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
</style>
