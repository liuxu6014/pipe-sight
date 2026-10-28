<template>
  <div class="ps-page ps-task-detail-page">
    <div v-if="loading && !loaded" class="ps-detail-loading" aria-live="polite" aria-label="正在加载任务">
      <i></i><div><span></span><span></span><span></span></div>
    </div>
    <div v-else-if="loadError && !loaded" class="ps-inline-state is-warning" role="alert">
      <WarningFilled /><span>{{ loadError }}</span><el-button class="ps-ui-action" @click="loadTask">重新加载</el-button>
    </div>
    <template v-else-if="loaded">
    <header class="ps-task-toolbar"><div><el-button @click="router.push(taskHomePath)">返回{{ taskHomeLabel }}</el-button><span>任务进度</span></div><el-button :loading="loading" :disabled="acting" @click="loadTask">刷新状态</el-button></header>
    <div class="ps-task-scroll" tabindex="0" aria-label="任务详情">
    <div v-if="loadError" class="ps-inline-state is-warning" role="alert"><span>{{ loadError }}，当前显示最后一次读取的状态。</span><el-button class="ps-ui-action" @click="loadTask">重新加载</el-button></div>
    <section class="ps-panel ps-task-overview">
      <div class="ps-task-heading"><div><div class="ps-task-heading-label"><span>{{ reportTypeLabel }}</span><el-tag :type="task.status === 'completed' ? 'success' : ['failed', 'dead_letter'].includes(task.status) ? 'danger' : ['queued', 'running'].includes(task.status) ? 'primary' : 'info'" effect="light">{{ taskStateLabel }}</el-tag></div><h1>{{ task.title }}</h1><p>创建人：{{ task.owner || currentUserName }}<span>创建于 {{ formatBusinessTime(task.createdAt) || '创建时间未记录' }}</span></p></div><div class="ps-task-total"><strong>{{ progress }}<small>%</small></strong><span>{{ currentStageLabel }}</span></div></div>
      <el-progress :percentage="progress" :status="task.status === 'completed' ? 'success' : ['failed', 'dead_letter'].includes(task.status) ? 'exception' : undefined" :stroke-width="6" :show-text="false" />
      <div class="ps-task-refresh" aria-live="polite"><span>{{ loadError ? '自动更新已暂停' : terminalTaskStatuses.includes(task.status) ? '任务已结束，不再自动更新' : ['queued', 'running'].includes(task.status) ? '每 2 秒自动更新，离开当前标签页时暂停' : '状态未记录，请刷新确认' }}</span><time v-if="lastReadAt">最近读取 {{ lastReadAt }}</time></div>
    </section>
    <section v-if="failureNotice" class="ps-task-failure" role="status"><WarningFilled /><div><h2>{{ taskStateLabel }}</h2><p>{{ failureNotice }}</p><small>{{ canRetry ? '重新生成会新建一次任务并调用模型，原任务记录保留。也可复制任务，调整资料和大纲后再提交。' : '请联系管理员核对执行记录与模型配置，不会自动再次生成。' }}</small></div></section>
    <el-alert v-if="task.cancelRequested" title="正在停止任务" description="取消请求已提交，系统会在当前执行阶段结束后安全停止任务。" type="warning" :closable="false" show-icon />
    <el-alert v-else-if="task.requiresReview" title="当前是待复核草稿" :description="task.generationWarning || '该结果未完成全量模型生成，请配置可用模型或人工复核后再作为正式成果使用。'" type="warning" :closable="false" show-icon />
    <el-alert v-if="task.applyConflict" title="已保留当前报告内容" description="当前报告与本次生成结果不同。生成结果仍有记录，不会覆盖报告中的现有修改。" type="info" :closable="false" show-icon />
    <div class="ps-task-layout">
      <div class="ps-task-main">
      <section class="ps-panel ps-task-timeline"><div class="ps-section-head"><h2>生成阶段</h2></div><div class="ps-stage-list"><div v-for="stage in stageRows" :key="stage.key || stage.label" :class="{ 'is-complete': stage.status === 'completed', 'is-active': stage.status === 'running' }"><span><Check v-if="stage.status === 'completed'" /><Loading v-else-if="stage.status === 'running'" /><WarningFilled v-else-if="stage.status === 'failed'" /><i v-else></i></span><div><strong>{{ stage.label }}</strong><small>{{ stage.description || '以实际任务记录为准' }}</small></div><time>{{ stageStatusLabel(stage.status) }}</time></div></div></section>
      <section class="ps-panel ps-task-log"><div class="ps-section-head"><h2>执行记录</h2><span>{{ logs.length }} 条记录</span></div><ol class="ps-task-event-list"><li v-for="(log, index) in logs" :key="`${log.time}-${log.message}-${index}`"><span class="ps-task-event-dot" :class="`is-${log.type}`"></span><div><p>{{ log.message }}</p><time>{{ formatBusinessTime(log.time) || '时间未记录' }}</time></div></li></ol></section>
      </div>
      <aside class="ps-task-side">
        <section class="ps-panel"><h3>任务信息</h3><dl>
          <div><dt>使用模板</dt><dd>{{ templateName }}</dd></div>
          <div><dt>输入资料</dt><dd>{{ task.selectedItems?.length || 0 }} 条</dd></div>
          <div><dt>目标字数</dt><dd>{{ targetWords.toLocaleString() }} 字</dd></div>
          <div><dt>生成方式</dt><dd>{{ generationModeLabel }}</dd></div>
          <div><dt>执行尝试</dt><dd>{{ task.attemptCount ? `第 ${task.attemptCount} 次` : '未记录' }}</dd></div>
        </dl></section>
        <section class="ps-panel"><div class="ps-section-head"><h3>输入资料</h3></div><div class="ps-input-summary"><span>新闻资讯 <b>{{ materialCounts.news }}</b></span><span>论文 <b>{{ materialCounts.paper }}</b></span><span>上传资料 <b>{{ materialCounts.internal }}</b></span></div><p v-if="materialCounts.other" class="ps-material-note">另有 {{ materialCounts.other }} 条资料未记录类型</p><el-button plain type="primary" class="ps-task-material-button" @click="showMaterials = true">查看资料清单</el-button></section>
      </aside>
    </div>
    </div>
    <footer class="ps-task-footer"><span>{{ taskStateLabel }}</span><div><el-button v-if="canCancel" :loading="acting" @click="cancelTask">取消任务</el-button><el-button v-else-if="canRetry" :loading="acting" @click="retryTask">重新生成</el-button><span v-else-if="task.cancelRequested" class="ps-task-action-note">取消请求处理中</span><el-button @click="copyTask">复制任务</el-button><el-button type="primary" :disabled="!canOpenReport" @click="openReport">{{ isDigest ? '打开简报' : '打开报告' }}</el-button></div></footer>
    <el-dialog v-model="showMaterials" title="输入资料清单" width="min(680px, calc(100vw - 32px))"><p class="ps-material-note">以下为提交时的资料快照，不代表当前解析或访问状态。点击标题查看最新详情。</p><ol class="ps-task-materials"><li v-for="(item, index) in materialRows" :key="`${item.type}-${item.id}-${index}`"><span>{{ index + 1 }}</span><div><router-link v-if="item.path" :to="item.path">{{ item.title || '未命名资料' }}</router-link><strong v-else>{{ item.title || '未命名资料' }}</strong><small>{{ item.typeLabel }} · {{ item.sourceLabel }}</small></div></li></ol><PortalEmptyState v-if="!materialRows.length" title="没有输入资料" description="该任务没有记录输入资料清单。" /></el-dialog>
    </template>
  </div>
</template>

<script setup>
import { formatBusinessTime } from '@/utils/portal/businessTime'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Loading, WarningFilled } from '@element-plus/icons-vue'
import useUserStore from '@/store/modules/user'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import { cancelPipelineResearchJob, getPipelineResearchJob, retryPipelineResearchJob } from '@/api/pipeline/intelligence'
import { getPortalReportPath } from '../utils/routing'
import { getCitationPath } from '@/utils/portal/citationRouting'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const showMaterials = ref(false)
const acting = ref(false)
const loading = ref(false)
const loaded = ref(false)
const loadError = ref('')
const emptyTask = () => ({ title: '生成任务', status: '', progress: 0, stages: [], logs: [], selectedItems: [], config: {} })
const task = ref(emptyTask())
const lastReadAt = ref('')
let refreshTimer
let active = true
let requestEpoch = 0
const currentUserName = computed(() => userStore.nickName || userStore.name || '管网用户')
const templateName = computed(() => task.value.templateName || '模板名称未记录')
const progress = computed(() => { const value = Number(task.value.progress); return Number.isFinite(value) ? Math.min(100, Math.max(0, value)) : 0 })
const reportTypeLabel = computed(() => ({ research: '科研报告', 'research-demand': '科研需求报告', 'technology-route': '技术路线报告', 'project-demand': '科技项目需求填报表', daily: '日报', weekly: '周报', monthly: '月报' })[task.value.type] || task.value.type || '科研报告')
const isDigest = computed(() => ['daily', 'weekly', 'monthly', '日报', '周报', '月报'].includes(String(task.value.type || task.value.reportType || '')))
const taskHomePath = computed(() => isDigest.value ? '/portal/digests' : '/portal/research')
const taskHomeLabel = computed(() => isDigest.value ? '情报简报' : '科研工作台')
const taskStateLabel = computed(() => ({ completed: '生成完成', failed: '生成失败', dead_letter: '待人工处理', cancelled: '已取消', queued: '等待生成', running: task.value.cancelRequested ? '取消中' : '正在生成' })[task.value.status] || '状态未记录')
const failureNotice = computed(() => ['failed', 'dead_letter'].includes(task.value.status) ? task.value.errorMessage || '系统未记录具体失败原因，请联系管理员检查执行日志。' : '')
const terminalTaskStatuses = ['completed', 'failed', 'dead_letter', 'cancelled']
const canCancel = computed(() => ['queued', 'running'].includes(task.value.status) && !task.value.cancelRequested)
const canRetry = computed(() => ['failed', 'cancelled'].includes(task.value.status))
const canOpenReport = computed(() => canOpenTaskReport(task.value))
function canOpenTaskReport(task) { return Boolean(task.reportId) && task.status === 'completed' && task.reportStatus === 'completed' }
const stageRows = computed(() => {
  const rows = task.value.stages?.length ? task.value.stages : [{ key: 'execution', label: '任务执行', status: task.value.status === 'queued' ? 'waiting' : task.value.status, description: '以实际任务状态为准，未记录细分阶段' }]
  return rows.map(stage => terminalTaskStatuses.includes(task.value.status) && ['running', 'waiting', 'queued'].includes(stage.status)
    ? { ...stage, status: task.value.status === 'cancelled' ? 'cancelled' : 'unrecorded', description: '任务已结束，该阶段未记录最终结果' } : stage)
})
const currentStageLabel = computed(() => ({ completed: '任务完成', failed: '生成失败', cancelled: '任务已取消', dead_letter: '待人工处理', queued: '等待执行' })[task.value.status] || (task.value.status === 'running' ? stageRows.value.find(item => item.status === 'running')?.label || '后台执行中' : '状态未记录'))
const stageSummary = computed(() => ({ completed: '任务已完成', failed: '任务已失败', cancelled: '任务已停止', dead_letter: '待人工处理', queued: '任务等待执行', running: '任务状态自动刷新' })[task.value.status] || '任务状态未记录')
const logs = computed(() => task.value.logs?.length ? task.value.logs : [{ time: task.value.finishedAt || task.value.updatedAt || task.value.createdAt || '', type: task.value.status === 'failed' ? 'error' : 'info', message: `${taskStateLabel.value}；未记录详细执行日志。` }])
const targetWords = computed(() => (task.value.outline || []).reduce((sum, item) => sum + Number(item.words || item.targetWords || 0), 0))
const generationModeLabel = computed(() => ({ model: '模型生成', deterministic: '证据编排草稿', 'model-partial-fallback': '模型部分生成，待复核', 'deterministic-fallback': '模型失败，证据编排草稿' })[task.value.generationMode] || (task.value.status === 'completed' ? '已生成（方式未记录）' : '生成方式未记录'))
const materialRows = computed(() => (task.value.selectedItems || []).map(item => {
  const path = getCitationPath({ sourceId: item.id, type: item.type })
  const typedPath = getCitationPath({ sourceId: '1', type: item.type })
  const kind = typedPath?.startsWith('/portal/papers/') ? 'paper' : typedPath?.startsWith('/portal/news/') ? 'news' : typedPath?.startsWith('/portal/knowledge/') ? 'internal' : 'other'
  const source = item.source
  const sourceLabel = typeof source === 'string' ? source : source?.publisher || source?.journal || source?.filename || source?.name || '来源名称未记录'
  return { ...item, path, kind, sourceLabel, typeLabel: ({ paper: '论文摘要', news: '新闻资讯', internal: '上传资料', other: '类型未记录' })[kind] }
}))
const materialCounts = computed(() => materialRows.value.reduce((result, item) => { result[item.kind]++; return result }, { internal: 0, paper: 0, news: 0, other: 0 }))
function stageStatusLabel(status) { return ({ completed: '已完成', running: '进行中', cancelled: '已取消', failed: '失败', skipped: '未执行', waiting: '等待中', unrecorded: '结果未记录' })[status] || '状态未记录' }
async function loadTask() {
  if (!active || route.name !== 'PortalResearchTask' || loading.value || acting.value) return
  const id = String(route.params.id), epoch = requestEpoch
  loading.value = true
  loadError.value = ''
  try {
    const res = await getPipelineResearchJob(id)
    if (!active || epoch !== requestEpoch || id !== String(route.params.id)) return
    if (!res.data || typeof res.data !== 'object' || Array.isArray(res.data) || !res.data.status) throw new Error('任务状态返回格式无效')
    task.value = res.data
    loaded.value = true
    lastReadAt.value = new Date().toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
    if (terminalTaskStatuses.includes(task.value.status)) stopRefresh()
    else if (!refreshTimer) startRefresh()
  } catch (error) {
    if (!active || epoch !== requestEpoch) return
    loadError.value = error?.msg || error?.message || '任务状态加载失败，请确认后端服务和访问权限。'
    stopRefresh()
  } finally {
    if (epoch === requestEpoch) loading.value = false
  }
}
function stopRefresh() {
  if (!refreshTimer) return
  clearInterval(refreshTimer)
  refreshTimer = undefined
}
function startRefresh() {
  stopRefresh()
  if (!active || acting.value || loadError.value || document.hidden || !['queued', 'running'].includes(task.value.status)) return
  refreshTimer = setInterval(loadTask, 2000)
}
function openReport() {
  if (!canOpenReport.value) return
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
  const id = String(route.params.id), epoch = requestEpoch
  let commandEpoch = epoch
  acting.value = true
  try {
    await ElMessageBox.confirm('确认停止本次生成？已产生的模型调用费用不会退回，任务记录会保留。', '取消任务', { confirmButtonText: '停止本次', cancelButtonText: '继续生成', type: 'warning' })
    if (!active || epoch !== requestEpoch || !canCancel.value) return
    requestEpoch++; loading.value = false; stopRefresh()
    commandEpoch = requestEpoch
    const res = await cancelPipelineResearchJob(id)
    if (!active || commandEpoch !== requestEpoch) return
    if (!res.data?.status) throw new Error('取消结果未返回任务状态，请刷新确认')
    task.value = res.data
    if (terminalTaskStatuses.includes(task.value.status)) {
      stopRefresh()
      ElMessage.success('任务已取消')
    } else {
      ElMessage.success('取消请求已提交，任务将在当前阶段结束后停止')
    }
  } catch (error) {
    if (!active || commandEpoch !== requestEpoch || error === 'cancel' || error === 'close') return
    ElMessage.error(error?.msg || error?.message || '任务取消失败')
  } finally {
    if (active && commandEpoch === requestEpoch) { acting.value = false; startRefresh() }
  }
}
async function retryTask() {
  if (acting.value || !canRetry.value) return
  const id = String(route.params.id), epoch = requestEpoch
  let commandEpoch = epoch
  acting.value = true
  try {
    await ElMessageBox.confirm('将按原资料、大纲和配置新建生成任务，可能产生模型调用费用；原任务记录保留。确认重新生成？', '重新生成', { confirmButtonText: '确认重新生成', cancelButtonText: '暂不重试', type: 'warning' })
    if (!active || epoch !== requestEpoch || !canRetry.value) return
    requestEpoch++; loading.value = false; stopRefresh()
    commandEpoch = requestEpoch
    const res = await retryPipelineResearchJob(id)
    if (!active || commandEpoch !== requestEpoch) return
    if (!res.data?.status) throw new Error('重试结果未返回任务状态，请刷新确认')
    const newId = res.data?.jobId || res.data?.id
    if (newId && String(newId) !== id) await router.replace(`/portal/research/tasks/${newId}`)
    else task.value = res.data
    if (!active) return
    startRefresh()
    ElMessage.success('任务已按原配置重新加入生成队列')
  } catch (error) {
    if (!active || commandEpoch !== requestEpoch || error === 'cancel' || error === 'close') return
    ElMessage.error(error?.msg || error?.message || '重新生成失败')
  } finally {
    if (active && commandEpoch === requestEpoch) { acting.value = false; startRefresh() }
  }
}
function onVisibilityChange() {
  if (document.hidden) stopRefresh()
  else if (!terminalTaskStatuses.includes(task.value.status)) loadTask()
}
const stopRouteWatch = watch(() => route.name === 'PortalResearchTask' ? route.params.id : null, id => {
  requestEpoch++; stopRefresh(); loading.value = false; acting.value = false
  if (id == null) return
  loaded.value = false; loadError.value = ''; lastReadAt.value = ''; showMaterials.value = false; task.value = emptyTask()
  loadTask()
}, { flush: 'sync' })
onMounted(() => { loadTask(); document.addEventListener('visibilitychange', onVisibilityChange) })
onUnmounted(() => { active = false; requestEpoch++; stopRouteWatch(); stopRefresh(); document.removeEventListener('visibilitychange', onVisibilityChange) })
</script>

<style scoped>
:global(.ps-portal-main:has(> .ps-task-detail-page)) { height: 100dvh; min-height: 0; display: flex; flex-direction: column; overflow: hidden; box-sizing: border-box; }
.ps-task-detail-page { flex: 1 1 0; min-height: 0; min-width: 0; width: calc(100% - 32px); max-width: none; display: flex; flex-direction: column; padding: 12px 0; gap: 12px; }
.ps-task-toolbar, .ps-task-toolbar > div, .ps-task-footer, .ps-task-footer > div { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.ps-task-toolbar, .ps-task-footer { flex-shrink: 0; }
.ps-task-toolbar > div > span { color: var(--ps-muted); font-size: 14px; }
.ps-task-scroll { flex: 1 1 0; min-height: 0; min-width: 0; overflow-y: auto; scrollbar-gutter: stable; display: flex; flex-direction: column; gap: 12px; padding: 1px; }
.ps-task-scroll > * { flex-shrink: 0; }
.ps-task-scroll .ps-panel { padding: 20px; }
.ps-task-heading { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 16px; }
.ps-task-heading > div:first-child { min-width: 0; }
.ps-task-heading-label { display: flex; align-items: center; gap: 10px; color: var(--ps-muted); font-size: 13px; }
.ps-task-heading h1 { margin: 10px 0 8px; font-size: 22px; line-height: 1.45; color: var(--ps-ink); overflow-wrap: anywhere; }
.ps-task-heading p { display: flex; flex-wrap: wrap; gap: 6px 16px; margin: 0; color: var(--ps-muted); font-size: 13px; }
.ps-task-total { flex-shrink: 0; gap: 2px; }
.ps-task-total strong { color: var(--ps-blue); font-size: 30px; line-height: 1.2; }
.ps-task-total strong small { margin-left: 2px; font-size: 16px; }
.ps-task-total > span { color: var(--ps-muted); font-size: 13px; }
.ps-task-refresh { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 6px 12px; margin-top: 10px; color: var(--ps-muted); font-size: 12px; line-height: 1.6; }
.ps-task-layout { grid-template-columns: minmax(0, 1fr) minmax(260px, 320px); gap: 12px; }
.ps-task-main, .ps-task-side { min-width: 0; display: flex; flex-direction: column; gap: 12px; }
.ps-task-timeline { grid-row: auto; }
.ps-task-scroll .ps-section-head { margin-bottom: 18px; }
.ps-task-scroll h2, .ps-task-scroll h3 { margin: 0; font-size: 15px; font-weight: 600; }
.ps-task-side > .ps-panel > h3 { margin-bottom: 8px; }
.ps-stage-list > div { min-height: 64px; grid-template-columns: 30px minmax(0, 1fr) auto; gap: 10px; }
.ps-stage-list > div:last-child { min-height: 34px; }
.ps-stage-list > div > span { width: 28px; height: 28px; }
.ps-stage-list > div::before { left: 13px; top: 28px; }
.ps-stage-list small { line-height: 1.6; overflow-wrap: anywhere; }
.ps-stage-list time { display: block; white-space: nowrap; padding-top: 3px; font-size: 12px; }
.ps-task-side dl div { align-items: flex-start; gap: 16px; padding: 11px 0; }
.ps-task-side dl div:last-child { border-bottom: 0; padding-bottom: 0; }
.ps-task-side dt { flex-shrink: 0; }
.ps-task-side dd { overflow-wrap: anywhere; line-height: 1.6; }
.ps-input-summary { gap: 8px; }
.ps-input-summary span { gap: 5px; }
.ps-input-summary b { font-size: 24px; font-weight: 600; }
.ps-task-material-button { margin-top: 14px; width: 100%; }
.ps-task-event-list { list-style: none; margin: 0; padding: 0; }
.ps-task-event-list li { display: flex; gap: 10px; padding: 0 0 16px; }
.ps-task-event-list li:last-child { padding-bottom: 0; }
.ps-task-event-dot { width: 7px; height: 7px; flex-shrink: 0; margin-top: 7px; border-radius: 50%; background: var(--ps-muted); }
.ps-task-event-dot.is-success { background: var(--ps-green); }
.ps-task-event-list p { margin: 0 0 4px; color: var(--ps-ink-2); font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.ps-task-event-list time { color: var(--ps-muted); font-size: 12px; }
.ps-task-footer { border: 1px solid var(--ps-line); border-radius: var(--ps-radius); background: #fff; padding: 12px 16px; }
.ps-task-footer > span { color: var(--ps-muted); font-size: 13px; }
.ps-task-toolbar :deep(.el-button), .ps-task-footer :deep(.el-button) { margin-left: 0; }
.ps-task-scroll :deep(.el-alert) { border: 1px solid var(--ps-line); border-radius: var(--ps-radius); }
.ps-task-scroll :deep(.el-alert__title) { color: var(--ps-ink-2); }
.ps-task-scroll :deep(.el-alert__description) { color: var(--ps-muted); line-height: 1.6; }
.ps-task-failure { display: flex; gap: 12px; padding: 16px 20px; border: 1px solid #f1d4ca; background: #fff8f5; color: #8b3b24; }
.ps-task-failure > svg { width: 22px; flex-shrink: 0; align-self: flex-start; }
.ps-task-failure h2 { margin: 0 0 6px; font-size: 16px; }
.ps-task-failure p { margin: 0 0 8px; line-height: 1.65; white-space: pre-wrap; overflow-wrap: anywhere; }
.ps-task-failure small { line-height: 1.6; }
.ps-task-log .ps-log-list > div { grid-template-columns: minmax(100px, 145px) 12px minmax(0, 1fr); }
.ps-log-list time, .ps-log-list p { overflow-wrap: anywhere; }
.ps-material-note { margin: 0 0 12px; color: var(--ps-muted); line-height: 1.6; }
.ps-task-materials { list-style: none; padding: 0; margin: 0; max-height: 55vh; overflow: auto; }
.ps-task-materials li { display: flex; gap: 12px; padding: 14px 0; border-bottom: 1px solid var(--ps-line-soft); }
.ps-task-materials li > span { color: var(--ps-muted); min-width: 20px; }
.ps-task-materials li > div { min-width: 0; }
.ps-task-materials a, .ps-task-materials strong { font-size: 14px; line-height: 1.6; overflow-wrap: anywhere; }
.ps-task-materials a { color: var(--ps-blue); }
.ps-task-materials small { display: block; color: var(--ps-muted); margin-top: 5px; overflow-wrap: anywhere; }
@media (max-width: 900px) { .ps-task-layout { grid-template-columns: minmax(0, 1fr); } .ps-task-side { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); align-items: start; } }
@media (max-width: 560px) {
  .ps-task-detail-page { width: calc(100% - 20px); padding: 10px 0; gap: 10px; }
  .ps-task-scroll .ps-panel { padding: 16px; }
  .ps-task-heading { align-items: flex-start; gap: 10px; }
  .ps-task-heading h1 { font-size: 18px; }
  .ps-task-total strong { font-size: 24px; }
  .ps-task-total > span { max-width: 76px; text-align: right; }
  .ps-task-side { display: flex; }
  .ps-task-footer { padding: 10px; }
  .ps-task-footer > span { display: none; }
  .ps-task-footer > div { width: 100%; justify-content: flex-end; }
  .ps-task-footer :deep(.el-button) { min-height: 40px; }
}
@media (prefers-reduced-motion: reduce) { .ps-stage-list > div.is-active > span svg { animation: none; } }
</style>
