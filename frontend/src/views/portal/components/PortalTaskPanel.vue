<template>
  <el-drawer v-model="store.taskPanelVisible" title="生成队列" size="min(480px, 100vw)" class="ps-task-drawer">
    <div class="ps-task-panel-head">
      <p>{{ runningCount }} 个生成中 · {{ queuedCount }} 个排队中</p>
      <el-button plain @click="monitor.refresh()">刷新</el-button>
      <el-button plain type="primary" @click="openAllTasks">查看全部</el-button>
    </div>
    <p class="ps-queue-hint">任务在后台持续生成，可以切换页面继续其他操作。</p>
    <el-alert v-if="queueError" :title="queueError" type="warning" :closable="false" show-icon />
    <div class="ps-task-list">
      <el-button :auto-insert-space="false" v-for="task in orderedTasks" :key="task.id" native-type="button" class="ps-task-row ps-ui-control" @click="openTask(task)">
        <span class="ps-task-status" :class="`is-${task.status}`"></span>
        <span class="ps-task-copy">
          <strong>{{ task.title }}</strong>
          <small>{{ task.type }} · {{ task.statusLabel }} · {{ task.updatedAt }}</small>
          <el-progress v-if="task.status === 'running'" :percentage="task.progress" :stroke-width="5" :show-text="false" />
          <small v-if="task.status === 'completed'">查看生成结果</small>
        </span>
        <ArrowRight />
      </el-button>
      <p v-if="!orderedTasks.length" class="ps-inspector-empty">当前没有生成任务</p>
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElButton, ElNotification } from 'element-plus'
import { ArrowRight } from '@element-plus/icons-vue'
import usePortalStore from '@/store/modules/portal'
import useUserStore from '@/store/modules/user'
import { createGenerationMonitor } from '@/utils/portal/generationMonitor'
import { getPipelineResearchJob, listPipelineResearchJobs } from '@/api/pipeline/intelligence'
import { getPortalReportPath, getPortalTaskPath } from '../utils/routing'

const router = useRouter()
const store = usePortalStore()
const user = useUserStore()
const queueError = ref('')
const notices = new Set()
let storage
try { storage = localStorage } catch { /* In-memory tracking remains available. */ }
const monitor = createGenerationMonitor({
  listJobs: listPipelineResearchJobs,
  getJob: getPipelineResearchJob,
  updateTasks: tasks => store.setGenerationTasks(tasks),
  onCompleted: notifyCompleted,
  onError: message => { queueError.value = message },
  storage
})
const runningCount = computed(() => store.tasks.filter(task => task.status === 'running').length)
const queuedCount = computed(() => store.tasks.filter(task => task.status === 'queued').length)
const orderedTasks = computed(() => [...store.tasks].sort((a, b) => {
  const rank = { running: 0, queued: 1 }
  const difference = (rank[a.status] ?? 2) - (rank[b.status] ?? 2)
  if (difference) return difference
  return a.status === 'queued'
    ? String(a.createdAt).localeCompare(String(b.createdAt))
    : String(b.updatedAt).localeCompare(String(a.updatedAt))
}))

watch([() => user.id, () => store.workspaceEpoch], ([id]) => {
  for (const notice of notices) notice.close()
  notices.clear()
  queueError.value = ''
  monitor.start(id)
}, { immediate: true })
watch([() => store.tasks, () => store.submittedTaskIds], ([tasks, submitted]) => {
  monitor.observe(tasks, submitted)
  const terminal = new Set(tasks.filter(task => ['completed', 'failed', 'cancelled'].includes(task.status)).map(task => String(task.id)))
  const pending = submitted.filter(id => !terminal.has(id))
  if (pending.length !== submitted.length) store.submittedTaskIds = pending
}, { deep: true })
function notifyCompleted(task) {
  const owner = String(user.id)
  const notice = ElNotification({
    title: '生成完成', type: 'success', duration: 0, position: 'bottom-right',
    message: h('div', { class: 'ps-generation-notice' }, [
      h('p', task.title),
      h(ElButton, { type: 'primary', plain: true, onClick: async () => {
        if (String(user.id) !== owner) return
        const failure = await router.push(getPortalReportPath({ id: task.reportId, reportType: task.reportType || task.type }))
        if (!failure) notice.close()
      } }, () => '查看生成结果')
    ]),
    onClose: () => notices.delete(notice)
  })
  notices.add(notice)
}
function openAllTasks() {
  store.taskPanelVisible = false
  router.push('/portal/me/reports')
}
function openTask(task) {
  store.taskPanelVisible = false
  router.push(task.status === 'completed' && task.reportStatus === 'completed'
    ? getPortalReportPath({ id: task.reportId, reportType: task.reportType })
    : getPortalTaskPath(task))
}
function refreshVisibleQueue() {
  if (!document.hidden) void monitor.refresh()
}
onMounted(() => {
  document.addEventListener('visibilitychange', refreshVisibleQueue)
  window.addEventListener('focus', refreshVisibleQueue)
})
onBeforeUnmount(() => {
  document.removeEventListener('visibilitychange', refreshVisibleQueue)
  window.removeEventListener('focus', refreshVisibleQueue)
  monitor.stop()
  for (const notice of notices) notice.close()
})
</script>

<style scoped>
.ps-queue-hint { margin: 0 0 16px; color: var(--ps-muted); font-size: 13px; line-height: 1.6; }
:global(.ps-generation-notice p) { margin: 0 0 12px; line-height: 1.6; overflow-wrap: anywhere; }
</style>
