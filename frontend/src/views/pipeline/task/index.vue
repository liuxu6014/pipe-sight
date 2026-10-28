<template>
 <div class="pipeline-page ws-list-page">
  <section class="page-heading"><div><h1>采集任务监控</h1></div><el-button v-if="canTaskList" type="primary" :icon="Refresh" :loading="loading" @click="loadTasks">刷新任务</el-button></section>
  <el-alert v-if="taskError" :title="taskError" type="warning" :closable="false" show-icon><template #default><el-button plain @click="loadTasks">重新加载</el-button></template></el-alert>
  <el-card shadow="never" class="table-card ws-list-panel">
   <el-table v-loading="loading" :data="rows" border height="100%">
    <el-table-column prop="name" label="任务名称" min-width="180" />
    <el-table-column prop="source" label="来源" min-width="140" />
    <el-table-column label="来源开关" width="110"><template #default="{ row }">{{ sourceEnabled(row) ? '启用' : '停用' }}</template></el-table-column>
    <el-table-column label="运行状态" width="120"><template #default="{ row }"><el-tag :type="statusType(row.status)">{{ collectionStatusText(row.status) }}</el-tag></template></el-table-column>
    <el-table-column label="读取 / 保存 / 失败" width="180"><template #default="{ row }">{{ row.fetchedCount ?? row.fetched_count ?? '—' }} / {{ row.savedCount ?? row.saved_count ?? '—' }} / {{ row.failedCount ?? row.failed_count ?? '—' }}</template></el-table-column>
    <el-table-column label="最新消息" min-width="220"><template #default="{ row }">{{ row.error || row.latestMessage || row.latest_message || '—' }}</template></el-table-column>
    <el-table-column label="下次采集" width="180"><template #default="{ row }">{{ formatBusinessTime(row.nextRunAt || row.next_run_at || row.next_run_time) || '仅手动 / 未启用' }}</template></el-table-column>
    <el-table-column label="操作" width="280" fixed="right"><template #default="{ row }">
     <el-button v-if="canTaskRun" plain type="primary" :disabled="!sourceEnabled(row) || active(row.status) || Boolean(actionId)" @click="handleRunTask(row)">立即采集</el-button>
     <el-button v-if="canTaskRun && ['queued','running','stopping'].includes(row.status)" plain type="warning" :disabled="row.status === 'stopping' || Boolean(actionId)" @click="handleStop(row)">{{ row.status === 'stopping' ? '正在停止' : row.status === 'queued' ? '取消排队' : '停止本次' }}</el-button>
     <el-button v-if="canTaskRun && row.status === 'failed'" plain type="warning" :disabled="!sourceEnabled(row) || Boolean(actionId)" @click="handleRetry(row)">失败重试</el-button>
     <el-button plain type="primary" :icon="Document" @click="showTaskLog(row)">详情</el-button>
    </template></el-table-column>
   </el-table>
  </el-card>
  <el-dialog v-model="detailVisible" title="采集运行详情" width="680px">
   <el-skeleton v-if="detailLoading" :rows="5" animated />
   <el-alert v-else-if="detailError" :title="detailError" type="warning" :closable="false"><template #default><el-button plain @click="loadDetail">重新加载详情</el-button></template></el-alert>
   <el-descriptions v-else-if="detail" :column="2" border>
    <el-descriptions-item label="运行编号">{{ detail.id || detail.runId || detail.run_id }}</el-descriptions-item>
    <el-descriptions-item label="来源">{{ detail.sourceName || detail.source_name || detail.sourceId || detail.source_id }}</el-descriptions-item>
    <el-descriptions-item label="重试父运行"><el-button v-if="detail.parentId || detail.parent_id" plain type="primary" @click="openParentRun(detail.parentId || detail.parent_id)">{{ detail.parentId || detail.parent_id }}</el-button><span v-else>无（原始运行）</span></el-descriptions-item>
    <el-descriptions-item label="触发方式">{{ triggerText(detail.triggerType || detail.trigger_type) }}</el-descriptions-item>
    <el-descriptions-item label="运行状态">{{ collectionStatusText(detail.status) }}</el-descriptions-item>
    <el-descriptions-item label="读取 / 保存 / 失败">{{ detail.fetchedCount ?? detail.fetched_count }} / {{ detail.savedCount ?? detail.saved_count }} / {{ detail.failedCount ?? detail.failed_count }}</el-descriptions-item>
    <el-descriptions-item label="停止请求">{{ formatBusinessTime(detail.stopRequestedAt || detail.stop_requested_at) || '—' }}</el-descriptions-item>
    <el-descriptions-item label="结束时间">{{ formatBusinessTime(detail.finishedAt || detail.finished_at) || '尚未结束' }}</el-descriptions-item>
    <el-descriptions-item label="错误信息" :span="2">{{ detail.error || '暂无错误' }}</el-descriptions-item>
   </el-descriptions>
  </el-dialog>
 </div>
</template>
<script setup>
import { formatBusinessTime } from '@/utils/portal/businessTime'
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Refresh } from '@element-plus/icons-vue'
import { checkPermi } from '@/utils/permission'
import { getPipelineCollectionRun, listPipelineTasks, runPipelineTask, retryPipelineTask, stopPipelineCollectionRun } from '@/api/pipeline/intelligence'
import { sourceEnabled, runId, collectionStatusText, stopResultMessage } from '@/utils/pipeline/compactContract'
defineOptions({ name: 'PipelineTask' })
const loading = ref(false), taskError = ref(''), rows = ref([]), actionId = ref('')
const detailVisible = ref(false), detailLoading = ref(false), detailError = ref(''), detail = ref(null), selectedRunId = ref('')
const canTaskList = computed(() => checkPermi(['pipeline:task:list']))
const canTaskRun = computed(() => checkPermi(['pipeline:task:run']))
const active = status => ['queued', 'running', 'stopping'].includes(status)
const statusType = status => ({ success: 'success', failed: 'danger', stopping: 'warning', running: 'primary', queued: 'primary' })[status] || 'info'
const triggerText = trigger => ({ manual: '手动', schedule: '定时', retry: '失败重试' })[trigger] || trigger
let stopped = false, timer, detailRequest = 0
function scheduleRefresh() {
 clearTimeout(timer)
 if (!stopped && (taskError.value || rows.value.some(row => active(row.status)) || (detailVisible.value && (detailError.value || active(detail.value?.status))))) {
  timer = setTimeout(async () => { await loadTasks(true); if (!stopped && detailVisible.value) await loadDetail(true); scheduleRefresh() }, 3000)
 }
}
async function loadTasks(background = false) {
 if (!canTaskList.value || stopped || loading.value) return
 loading.value = true
 try {
  const res = await listPipelineTasks()
  if (stopped) return
  if (!Array.isArray(res.data?.rows)) throw new Error('采集任务返回格式无效')
  rows.value = res.data.rows; taskError.value = ''
 } catch (error) { if (!stopped) taskError.value = error?.msg || error?.message || '采集任务加载失败，请重试' }
 finally { loading.value = false; if (!background) scheduleRefresh() }
}
async function handleRunTask(row) {
 if (!canTaskRun.value || actionId.value || !sourceEnabled(row) || active(row.status)) return
 actionId.value = row.id
 try { const res = await runPipelineTask(row.sourceId || row.source_id || row.id); ElMessage.success(res.msg || '采集请求已提交'); await loadTasks() }
 catch (error) { ElMessage.error(error?.msg || error?.message || '采集请求失败') }
 finally { actionId.value = '' }
}
async function handleStop(row) {
 const id = runId(row)
 if (!canTaskRun.value || actionId.value || !id || !['queued','running'].includes(row.status)) return
 actionId.value = id
 try { const res = await stopPipelineCollectionRun(id); ElMessage.info(stopResultMessage(res.data)); await loadTasks(); if (detailVisible.value) await loadDetail() }
 catch (error) { ElMessage.error(error?.msg || error?.message || '停止请求失败') }
 finally { actionId.value = ''; scheduleRefresh() }
}
async function handleRetry(row) {
 const id = runId(row)
 if (!canTaskRun.value || actionId.value || !id || row.status !== 'failed' || !sourceEnabled(row)) return
 actionId.value = id
 try { const res = await retryPipelineTask(id); ElMessage.success(res.msg || '已提交重试请求，原失败记录保留'); await loadTasks() }
 catch (error) { ElMessage.error(error?.msg || error?.message || '创建重试运行失败') }
 finally { actionId.value = '' }
}
async function loadDetail(background = false) {
 const id = selectedRunId.value, request = ++detailRequest
 if (!id || stopped) return
 if (!background) detailLoading.value = true
 try { const res = await getPipelineCollectionRun(id); if (!stopped && request === detailRequest) { detail.value = res.data; detailError.value = '' } }
 catch (error) { if (!stopped && request === detailRequest) detailError.value = error?.msg || error?.message || '运行详情加载失败' }
 finally { if (request === detailRequest) detailLoading.value = false; if (!background) scheduleRefresh() }
}
async function openParentRun(id) {
 selectedRunId.value = id; detail.value = null; detailError.value = ''
 await loadDetail()
}
async function showTaskLog(row) {
 const id = runId(row)
 if (!id) return ElMessage.info('暂无运行记录')
 selectedRunId.value = id; detail.value = null; detailError.value = ''; detailVisible.value = true
 await loadDetail()
}
watch(detailVisible, value => { if (!value) { detailRequest++; detailLoading.value = false }; scheduleRefresh() })
onMounted(loadTasks)
onBeforeUnmount(() => { stopped = true; detailRequest++; clearTimeout(timer) })
</script>
<style scoped>
.table-card { overflow: hidden; }
</style>
