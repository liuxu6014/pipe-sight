<template>
  <div class="ps-page">
    <div v-if="loading && !loaded" class="ps-detail-loading" aria-live="polite" aria-label="正在加载任务">
      <i></i><div><span></span><span></span><span></span></div>
    </div>
    <div v-else-if="loadError && !loaded" class="ps-inline-state is-warning" role="alert">
      <WarningFilled /><span>{{ loadError }}</span><button type="button" @click="loadTask">重新加载</button>
    </div>
    <template v-else-if="loaded">
    <div class="ps-breadcrumb"><button type="button" @click="router.push(taskHomePath)">{{ taskHomeLabel }}</button><span>/</span><b>任务进度</b></div>
    <div v-if="loadError" class="ps-inline-state is-warning" role="alert"><span>{{ loadError }}，当前显示最后一次读取的状态。</span><button type="button" @click="loadTask">重新加载</button></div>
    <section class="ps-task-hero"><div><span class="ps-task-state" :class="`is-${task.status}`"><i></i>{{ task.statusLabel || taskStateLabel }}</span><h1>{{ task.title }}</h1><p>{{ reportTypeLabel }} · 创建人：{{ task.owner || currentUserName }} · 创建于 {{ task.createdAt || '创建时间待补充' }}</p></div><div class="ps-task-total"><strong>{{ progress }}%</strong><span>当前阶段：{{ currentStageLabel }}</span></div></section>
    <el-alert v-if="task.cancelRequested" title="正在停止任务" description="取消请求已提交，系统会在当前执行阶段结束后安全停止任务。" type="warning" :closable="false" show-icon />
    <el-alert v-else-if="task.requiresReview" title="当前是待复核草稿" :description="task.generationWarning || '该结果未完成全量模型生成，请配置可用模型或人工复核后再作为正式成果使用。'" type="warning" :closable="false" show-icon />
    <el-alert v-if="task.applyConflict" title="生成结果与当前报告内容不同" description="报告可能已被编辑。本次任务结果仍已保存，不会自动覆盖报告中的现有修改。" type="warning" :closable="false" show-icon />
    <el-progress :percentage="progress" :stroke-width="10" :show-text="false" class="ps-task-main-progress" />
    <div class="ps-task-layout">
      <section class="ps-panel ps-task-timeline"><div class="ps-section-head"><div><h2>生成阶段</h2></div><span>{{ stageSummary }}</span></div><div class="ps-stage-list"><div v-for="stage in stageRows" :key="stage.key || stage.label" :class="{ 'is-complete': stage.status === 'completed', 'is-active': stage.status === 'running' }"><span><Check v-if="stage.status === 'completed'" /><Loading v-else-if="stage.status === 'running'" /><WarningFilled v-else-if="stage.status === 'failed'" /><i v-else></i></span><div><strong>{{ stage.label }}</strong><small>{{ stage.description || '以实际任务记录为准' }}</small></div><time>{{ stageStatusLabel(stage.status) }}</time></div></div></section>
      <aside class="ps-task-side"><section class="ps-panel"><h3>任务信息</h3><dl><div><dt>使用模板</dt><dd>{{ templateName }}</dd></div><div><dt>输入资料</dt><dd>{{ task.selectedItems?.length || 0 }} 条</dd></div><div><dt>目标字数</dt><dd>{{ targetWords.toLocaleString() }} 字</dd></div><div><dt>生成方式</dt><dd>{{ generationModeLabel }}</dd></div><div><dt>执行尝试</dt><dd>第 {{ task.attemptCount || 0 }} 次</dd></div><div><dt>引用检查</dt><dd>{{ task.config?.citation_check === false || task.config?.citationCheck === false ? '未开启' : '已开启' }}</dd></div></dl><p v-if="task.errorMessage" class="ps-task-error">{{ task.errorMessage }}</p></section><section class="ps-panel"><h3>输入资料摘要</h3><div class="ps-input-summary"><span>内部资料 <b>{{ materialCounts.internal }}</b></span><span>论文 <b>{{ materialCounts.paper }}</b></span><span>新闻资讯 <b>{{ materialCounts.news }}</b></span></div><el-button text type="primary" @click="showMaterials = true">查看资料清单</el-button></section><div class="ps-task-actions"><el-button v-if="canCancel" :loading="acting" @click="cancelTask">取消任务</el-button><el-button v-else-if="canRetry" :loading="acting" @click="retryTask">重新生成</el-button><span v-else-if="task.cancelRequested" class="ps-task-action-note">取消请求处理中</span><el-button @click="copyTask">复制任务</el-button></div></aside>
      <section class="ps-panel ps-task-log"><div class="ps-section-head"><div><h2>执行记录</h2></div><span>{{ terminalTaskStatuses.includes(task.status) ? taskStateLabel : '自动更新' }}</span></div><div class="ps-log-list"><div v-for="log in logs" :key="`${log.time}-${log.message}`"><time>{{ formatBusinessTime(log.time) }}</time><span :class="`is-${log.type}`"></span><p>{{ log.message }}</p></div></div></section>
    </div>
    <div class="ps-sticky-actions"><el-button @click="router.push('/portal/research')">返回工作台</el-button><el-button type="primary" :disabled="!task.reportId" @click="openReport">打开报告</el-button></div>
    <el-dialog v-model="showMaterials" title="输入资料清单" width="680px"><div class="ps-source-check" v-for="item in task.selectedItems || []" :key="item.id"><CircleCheckFilled /><span><strong>{{ item.title }}</strong><small>{{ item.type }} · {{ item.source || '平台知识库' }}</small></span></div><PortalEmptyState v-if="!task.selectedItems?.length" title="没有输入资料" description="该任务没有关联可用资料。" /></el-dialog>
    </template>
  </div>
</template>

<script setup>
import { formatBusinessTime } from '@/utils/portal/businessTime'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Check, CircleCheckFilled, Loading, WarningFilled } from '@element-plus/icons-vue'
import useUserStore from '@/store/modules/user'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import { cancelPipelineResearchJob, getPipelineResearchJob, retryPipelineResearchJob } from '@/api/pipeline/intelligence'
import { getPortalReportPath } from '../utils/routing'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const showMaterials = ref(false)
const acting = ref(false)
const loading = ref(false)
const loaded = ref(false)
const loadError = ref('')
const task = ref({ title: '科研生成任务', status: 'running', progress: 0, stages: [], logs: [], selectedItems: [], config: {} })
let refreshTimer
let active = true
const currentUserName = computed(() => userStore.nickName || userStore.name || '管网用户')
const templateName = computed(() => task.value.templateName || '模板名称未记录')
const progress = computed(() => Number(task.value.progress || 0))
const reportTypeLabel = computed(() => ({ research: '科研报告', 'research-demand': '科研需求报告', 'technology-route': '技术路线报告', 'project-demand': '科技项目需求填报表', daily: '日报', weekly: '周报', monthly: '月报' })[task.value.type] || task.value.type || '科研报告')
const isDigest = computed(() => ['daily', 'weekly', 'monthly', '日报', '周报', '月报'].includes(String(task.value.type || task.value.reportType || '')))
const taskHomePath = computed(() => isDigest.value ? '/portal/digests' : '/portal/research')
const taskHomeLabel = computed(() => isDigest.value ? '情报简报' : '科研工作台')
const taskStateLabel = computed(() => ({ completed: '生成完成', failed: '生成失败', dead_letter: '待人工处理', cancelled: '已取消', queued: '等待生成', running: task.value.cancelRequested ? '取消中' : '正在生成' })[task.value.status] || '正在生成')
const terminalTaskStatuses = ['completed', 'failed', 'dead_letter', 'cancelled']
const canCancel = computed(() => ['queued', 'running'].includes(task.value.status) && !task.value.cancelRequested)
const canRetry = computed(() => ['failed', 'cancelled'].includes(task.value.status))
const stageRows = computed(() => task.value.stages?.length ? task.value.stages : [{ key: 'execution', label: '任务执行', status: task.value.status === 'queued' ? 'waiting' : task.value.status, description: '以实际任务状态为准，未记录细分阶段' }])
const currentStageLabel = computed(() => ({ completed: '任务完成', failed: '生成失败', cancelled: '任务已取消', dead_letter: '待人工处理', queued: '等待执行' })[task.value.status] || stageRows.value.find(item => item.status === 'running')?.label || '后台执行中')
const stageSummary = computed(() => ({ completed: '任务已完成', failed: '任务已失败', cancelled: '任务已停止', dead_letter: '待人工处理', queued: '任务等待执行' })[task.value.status] || '任务状态自动刷新')
const logs = computed(() => task.value.logs?.length ? task.value.logs : [{ time: task.value.finishedAt || task.value.updatedAt || task.value.createdAt || '', type: task.value.status === 'failed' ? 'error' : 'info', message: `${taskStateLabel.value}；未记录详细执行日志。` }])
const targetWords = computed(() => (task.value.outline || []).reduce((sum, item) => sum + Number(item.words || item.targetWords || 0), 0))
const generationModeLabel = computed(() => ({ model: '模型生成', deterministic: '证据编排草稿', 'model-partial-fallback': '模型部分生成，待复核', 'deterministic-fallback': '模型失败，证据编排草稿' })[task.value.generationMode] || (task.value.status === 'completed' ? '已生成（方式未记录）' : '生成方式未记录'))
const materialCounts = computed(() => (task.value.selectedItems || []).reduce((result, item) => { const type = String(item.type || ''); if (type === 'paper' || type.includes('论文')) result.paper += 1; else if (['article', 'news', 'wechat'].includes(type) || type.includes('资讯') || type.includes('新闻')) result.news += 1; else result.internal += 1; return result }, { internal: 0, paper: 0, news: 0 }))
function stageStatusLabel(status) { return ({ completed: '已完成', running: '进行中', cancelled: '已取消', failed: '失败', skipped: '未执行', waiting: '等待中' })[status] || '状态未记录' }
async function loadTask() {
  if (!active || loading.value) return
  loading.value = true
  loadError.value = ''
  try {
    const res = await getPipelineResearchJob(String(route.params.id))
    if (!active) return
    if (!res.data) throw new Error('empty task response')
    task.value = res.data
    loaded.value = true
    if (terminalTaskStatuses.includes(task.value.status)) stopRefresh()
    else if (!refreshTimer) startRefresh()
  } catch (error) {
    if (!active) return
    loadError.value = error?.msg || '任务状态加载失败，请确认后端服务和访问权限。'
    ElMessage.warning('暂时无法读取任务状态，请确认后端和数据库已启动')
    stopRefresh()
  } finally {
    loading.value = false
  }
}
function stopRefresh() {
  if (!refreshTimer) return
  clearInterval(refreshTimer)
  refreshTimer = undefined
}
function startRefresh() {
  if (!active) return
  stopRefresh()
  refreshTimer = setInterval(loadTask, 2000)
}
function openReport() {
  if (!task.value.reportId) return
  router.push(getPortalReportPath({ id: task.value.reportId, reportType: task.value.type }))
}
function copyTask() {
  router.push({
    path: isDigest.value ? '/portal/digests/create' : '/portal/research/create',
    query: { sourceTask: String(route.params.id) }
  })
}
async function cancelTask() {
  if (acting.value || !canCancel.value) return
  acting.value = true
  try {
    const res = await cancelPipelineResearchJob(String(route.params.id))
    if (!active) return
    task.value = res.data
    if (terminalTaskStatuses.includes(task.value.status)) {
      stopRefresh()
      ElMessage.success('任务已取消')
    } else {
      startRefresh()
      ElMessage.success('取消请求已提交，任务将在当前阶段结束后停止')
    }
  } catch (error) {
    if (!active) return
    ElMessage.error(error?.msg || '任务取消失败')
  } finally {
    acting.value = false
  }
}
async function retryTask() {
  if (acting.value) return
  acting.value = true
  try {
    const res = await retryPipelineResearchJob(String(route.params.id))
    if (!active) return
    task.value = res.data
    const newId = res.data?.jobId || res.data?.id
    if (newId && String(newId) !== String(route.params.id)) await router.replace(`/portal/research/tasks/${newId}`)
    if (!active) return
    startRefresh()
    ElMessage.success('任务已按原配置重新加入生成队列')
  } catch (error) {
    if (!active) return
    ElMessage.error(error?.msg || '重新生成失败')
  } finally {
    acting.value = false
  }
}
onMounted(() => { loadTask(); startRefresh() })
onUnmounted(() => { active = false; stopRefresh() })
</script>
