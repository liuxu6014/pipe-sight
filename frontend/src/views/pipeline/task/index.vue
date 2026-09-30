<template>
  <div class="pipeline-page">
    <section class="page-heading">
      <div>
        <p class="eyebrow">后台管理 · 数据采集</p>
        <h1>采集任务监控</h1>
        <p class="summary">跟踪采集任务运行、清洗进度、异常信息和下一次调度时间。</p>
      </div>
      <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadTasks">刷新任务</el-button>
    </section>

    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="rows" border>
        <el-table-column prop="name" label="任务名称" min-width="180" />
        <el-table-column prop="source" label="来源" width="180" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" effect="light">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="采集进度" min-width="160">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :status="row.status === 'warning' ? 'warning' : undefined" />
          </template>
        </el-table-column>
        <el-table-column prop="handoff_status" label="外部处理" min-width="190">
          <template #default="{ row }">
            <div class="handoff-cell">
              <el-tag :type="handoffType(row.handoff_status)" effect="light">
                {{ handoffText(row.handoff_status) }}
              </el-tag>
              <el-progress
                v-if="row.handoff_count"
                :percentage="row.handoff_progress"
                :stroke-width="6"
                :show-text="false"
              />
              <small v-if="row.handoff_count">
                {{ row.handoff_processed_count }}/{{ row.handoff_count }} 条
              </small>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="latest_message" label="最新消息" min-width="240" show-overflow-tooltip />
        <el-table-column prop="next_run_time" label="下次运行" width="180" />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :icon="VideoPlay"
              :loading="runningTaskId === row.id"
              @click="handleRunTask(row)"
            >
              运行
            </el-button>
            <el-button
              link
              type="primary"
              :disabled="!row.latest_run_id"
              :loading="handoffTaskId === row.id"
              @click="handleHandoff(row)"
            >
              提交处理
            </el-button>
            <el-button
              link
              type="primary"
              :disabled="!row.latest_run_id || !row.handoff_count"
              :loading="syncTaskId === row.id"
              @click="handleSync(row)"
            >
              同步结果
            </el-button>
            <el-button link type="primary" :icon="Document" @click="showTaskLog(row)">日志</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Refresh, VideoPlay } from '@element-plus/icons-vue'
import {
  dispatchPipelineHandoff,
  listPipelineTasks,
  runPipelineTask,
  syncPipelineHandoff
} from '@/api/pipeline/intelligence'

defineOptions({ name: 'PipelineTask' })

const loading = ref(false)
const runningTaskId = ref('')
const handoffTaskId = ref('')
const syncTaskId = ref('')
const rows = ref([])

function statusText(status) {
  return {
    waiting: '待运行',
    queued: '排队中',
    running: '运行中',
    success: '成功',
    warning: '需关注',
    failed: '失败',
    cancelled: '已取消'
  }[status] || status
}

function statusType(status) {
  return {
    queued: 'primary',
    running: 'primary',
    success: 'success',
    warning: 'warning',
    failed: 'danger'
  }[status] || 'info'
}

function handoffText(status) {
  return {
    pending: '待提交',
    dispatched: '已提交',
    processing: '处理中',
    completed: '处理完成',
    partial: '部分完成',
    failed: '处理失败'
  }[status] || status
}

function handoffType(status) {
  return {
    dispatched: 'primary',
    processing: 'primary',
    completed: 'success',
    partial: 'warning',
    failed: 'danger'
  }[status] || 'info'
}

async function loadTasks() {
  loading.value = true
  try {
    const res = await listPipelineTasks()
    rows.value = res.data.rows
  } catch (error) {
    ElMessage.warning('暂时无法获取采集任务')
  } finally {
    loading.value = false
  }
}

async function handleRunTask(row) {
  runningTaskId.value = row.id
  try {
    const res = await runPipelineTask(row.id)
    ElMessage.success(`${res.data.name}已提交执行`)
    await loadTasks()
  } catch (error) {
    ElMessage.warning('任务运行失败，请稍后重试')
  } finally {
    runningTaskId.value = ''
  }
}

async function handleHandoff(row) {
  if (!row.latest_run_id) return
  handoffTaskId.value = row.id
  try {
    const res = await dispatchPipelineHandoff(row.latest_run_id)
    ElMessage.success(`已提交 ${res.data.handoff_count} 条资讯处理`)
    await loadTasks()
  } catch (error) {
    ElMessage.error(error?.msg || '提交外部处理失败')
  } finally {
    handoffTaskId.value = ''
  }
}

async function handleSync(row) {
  if (!row.latest_run_id) return
  syncTaskId.value = row.id
  try {
    const res = await syncPipelineHandoff(row.latest_run_id)
    ElMessage.success(`已同步 ${res.data.processed_count} 条处理结果`)
    await loadTasks()
  } catch (error) {
    ElMessage.error(error?.msg || '同步外部处理结果失败')
  } finally {
    syncTaskId.value = ''
  }
}

function showTaskLog(row) {
  ElMessage.info(row.latest_message || '暂无日志')
}

onMounted(loadTasks)
</script>

<style scoped>
.table-card {
  overflow: hidden;
}

.handoff-cell {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 6px 10px;
}

.handoff-cell small {
  grid-column: 2;
  color: var(--el-text-color-secondary);
}
</style>
