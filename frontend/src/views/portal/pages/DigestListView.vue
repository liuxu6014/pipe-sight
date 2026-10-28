<template>
  <div class="ps-page ps-list-page">
    <div class="ps-toolbar ps-digest-toolbar"><div class="ps-search-inline"><Search /><input v-model.trim="keyword" aria-label="搜索简报或计划名称" placeholder="搜索简报或计划名称" /></div><template v-if="activeTab !== '自动任务'"><el-date-picker v-model="date" aria-label="简报覆盖周期" type="daterange" value-format="YYYY-MM-DD" start-placeholder="覆盖开始日期" end-placeholder="覆盖结束日期" /><el-select v-model="status" aria-label="简报状态" style="width: 130px"><el-option label="全部状态" value="all" /><el-option v-for="value in reportStatuses" :key="value" :label="value" :value="value" /></el-select></template><el-button v-if="keyword || date?.length || status !== 'all'" @click="resetFilters">清除筛选</el-button><el-button :loading="schedulesLoading" @click="refreshCurrent">刷新</el-button><el-button :icon="Plus" @click="editSchedule()">新建自动计划</el-button><el-button type="primary" :icon="Plus" @click="router.push('/portal/digests/create')">新建简报</el-button></div>
    <div v-if="currentError" class="ps-inline-state is-warning" role="alert"><span>{{ currentError }}</span><el-button plain @click="refreshCurrent">重试</el-button></div>
    <div class="ps-tabs-line"><button v-for="tab in tabs" :key="tab" type="button" :class="{ 'is-active': activeTab === tab }" @click="activeTab = tab">{{ tab }}</button></div>
    <section v-if="activeTab !== '自动任务'" class="ps-panel ps-digest-list ps-list-scroll" tabindex="0" aria-label="简报列表">
      <div v-if="filteredReports.length" class="ps-section-head"><h2>简报成果</h2></div>
      <el-table v-if="filteredReports.length" :data="pagedReports" style="width: 100%">
        <el-table-column label="简报名称" min-width="260"><template #default="{ row }"><button class="ps-table-title-button" type="button" :disabled="!row.path" @click="router.push(row.path)">{{ row.title }}</button></template></el-table-column>
        <el-table-column prop="type" label="类型" width="80" />
        <el-table-column prop="period" label="覆盖周期" min-width="180" />
        <el-table-column label="来源数" width="90"><template #default="{ row }">{{ row.sources ?? '未提供' }}</template></el-table-column>
        <el-table-column label="状态" width="130"><template #default="{ row }"><span class="ps-status-pill" :class="`is-${statusClass(row.status)}`">{{ row.status }}</span></template></el-table-column>
        <el-table-column prop="updatedAt" label="更新时间" width="170" />
        <el-table-column label="操作" width="160" fixed="right"><template #default="{ row: report }"><div class="ps-table-actions"><el-button type="primary" plain :disabled="!report.path" @click="router.push(report.path)">{{ report.hasOutput ? '打开简报' : '生成记录' }}</el-button><el-dropdown v-if="report.hasOutput" trigger="click"><el-button plain :aria-label="`${report.title}更多操作`"><MoreFilled /></el-button><template #dropdown><el-dropdown-menu><el-dropdown-item :disabled="exportingId === report.id" @click="exportDigest(report)">{{ exportingId === report.id ? '正在导出…' : report.requiresReview ? '导出草稿 Markdown' : '导出 Markdown' }}</el-dropdown-item><el-dropdown-item @click="openSources(report)">打开来源清单</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div></template></el-table-column>
      </el-table>
      <el-skeleton v-if="portalStore.dataLoading && !portalStore.dataLoaded" :rows="4" animated />
      <div v-else-if="!filteredReports.length && !currentError" class="ps-empty-state" role="status">暂无简报</div>
    </section>
    <section v-else class="ps-schedule-list ps-list-scroll" tabindex="0" aria-label="简报自动任务列表">
      <article v-for="schedule in pagedSchedules" :key="schedule.id" class="ps-panel ps-schedule-card" :aria-label="schedule.name">
        <header class="ps-schedule-card-head"><h2>{{ schedule.name }}</h2><el-tag effect="plain">{{ scheduleType(schedule.reportType) }}</el-tag><el-tag :type="schedule.enabled ? 'success' : 'info'">{{ schedule.enabled ? '已启用' : '已停用' }}</el-tag><el-tag :type="schedule.lastStatus === 'failed' ? 'danger' : schedule.hasResult ? 'success' : 'info'">{{ scheduleStatus(schedule) }}</el-tag></header>
        <p class="ps-schedule-cadence">{{ scheduleTimeDescription(schedule) }} · {{ scheduleHolidayPolicy(schedule) }}</p>
        <p class="ps-schedule-rules">{{ scheduleFilters(schedule) }}</p>
        <dl class="ps-schedule-metrics"><div><dt>最近执行</dt><dd>{{ formatBusinessTime(schedule.lastRunTime) || '暂无执行记录' }}</dd></div><div><dt>下次执行</dt><dd>{{ schedule.enabled ? (formatBusinessTime(schedule.nextRunTime) || '等待调度确认') : '计划已停用' }}</dd></div><div><dt>本次选材</dt><dd>{{ Number.isInteger(schedule.matchedCount) ? `${schedule.matchedCount} 篇` : '暂无选材记录' }}</dd></div></dl>
        <el-alert v-if="schedule.lastStatus === 'no_data'" class="ps-schedule-notice" title="无匹配资料，已跳过" description="本次周期内没有满足筛选条件的有效文章，未创建生成任务，也不会改用全部文章生成。" type="info" :closable="false" show-icon />
        <el-alert v-else-if="schedule.lastStatus === 'skipped'" class="ps-schedule-notice" title="已按节假日策略跳过" description="本次执行日属于配置的节假日，未创建生成任务。" type="info" :closable="false" show-icon />
        <el-alert v-else-if="schedule.lastStatus === 'failed'" class="ps-schedule-notice is-failure" title="执行失败" :description="schedule.lastError || '此次失败未记录具体原因，请打开任务进度查看或联系管理员检查日志。'" type="error" :closable="false" show-icon />
        <p v-else-if="!schedule.lastStatus || schedule.lastStatus === 'never'" class="ps-schedule-history-note">暂无执行记录。早期未留存的跳过结果无法追溯，后续执行会自动记录。</p>
        <div class="ps-schedule-actions"><el-button v-if="scheduleResultPath(schedule)" type="primary" @click="router.push(scheduleResultPath(schedule))">查看简报</el-button><el-button v-if="scheduleTaskPath(schedule)" plain @click="router.push(scheduleTaskPath(schedule))">任务进度</el-button><el-button plain @click="editSchedule(schedule)">编辑计划</el-button><el-button type="primary" plain :loading="runningScheduleId === schedule.id" :disabled="!schedule.enabled || !!runningScheduleId" @click="runSchedule(schedule)">立即补跑</el-button><el-button plain :loading="changingScheduleId === schedule.id" :disabled="!!changingScheduleId" @click="toggleSchedule(schedule)">{{ schedule.enabled ? '停用计划' : '启用计划' }}</el-button><el-button type="danger" plain :disabled="schedule.canDelete === false" :title="schedule.canDelete === false ? '已有生成历史，请停用计划，保留历史关联' : '删除未产生生成记录的计划'" @click="removeSchedule(schedule)">删除</el-button></div>
      </article>
      <el-skeleton v-if="schedulesLoading" :rows="4" animated />
      <div v-else-if="!filteredSchedules.length && !currentError" class="ps-empty-state" role="status">暂无自动任务</div>
    </section>
    <div v-if="listTotal && !currentError" class="ps-pagination" aria-label="情报简报列表分页"><el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[10, 20, 50]" :total="listTotal" :pager-count="5" layout="total, sizes, ->, prev, pager, next, jumper" background /></div>
    <DigestScheduleDialog v-model="scheduleDialog" :record="editingSchedule" @saved="scheduleSaved" />
  </div>
</template>

<script setup>
import { formatBusinessTime } from '@/utils/portal/businessTime'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MoreFilled, Plus, Search } from '@element-plus/icons-vue'
import usePortalStore from '@/store/modules/portal'
import { exportPipelineResearchReport } from '@/api/pipeline/intelligence'
import { deletePipelineDigestSchedule, listPipelineDigestSchedules, runPipelineDigestSchedule, updatePipelineDigestSchedule } from '@/api/pipeline/intelligence'
import { periodOverlaps } from '../utils/workspace'
import { hasReportOutput } from '@/utils/portal/personalReports'
import DigestScheduleDialog from '../components/DigestScheduleDialog.vue'
import { readScheduleForm, scheduleSummary } from '@/utils/portal/digestScheduleEditor'

const router = useRouter()
const route = useRoute()
const portalStore = usePortalStore()
const keyword = ref('')
const date = ref([])
const status = ref('all')
const activeTab = ref(route.query.tab === 'schedules' ? '自动任务' : '全部')
const scheduleDialog = ref(false), editingSchedule = ref(null)
function editSchedule(row = null) { editingSchedule.value = row; scheduleDialog.value = true }
async function scheduleSaved() { activeTab.value = '自动任务'; await loadSchedules() }
function scheduleTimeDescription(row) { return scheduleSummary(readScheduleForm(row)) }
const exportingId = ref('')
const schedules = ref([])
const schedulesLoading = ref(false)
const schedulesError = ref('')
let disposed = false, scheduleRequest = 0, refreshTimer
const currentError = computed(() => activeTab.value === '自动任务' ? schedulesError.value : portalStore.sectionErrors.digests || portalStore.sectionErrors.reports)
const digestRows = computed(() => portalStore.digestReports.map(item => ({ ...item, ...digestReportState(item) })))
const reportStatuses = computed(() => [...new Set(digestRows.value.map(item => item.status).filter(Boolean))])
const runningScheduleId = ref('')
const changingScheduleId = ref('')
const tabs = ['全部', '日报', '周报', '月报', '自动任务']
const filteredReports = computed(() => digestRows.value.filter(item => {
  const matchesDate = periodOverlaps(item, date.value)
  return (activeTab.value === '全部' || item.type === activeTab.value) && (status.value === 'all' || item.status === status.value) && (!keyword.value || item.title.includes(keyword.value)) && matchesDate
}))
const filteredSchedules = computed(() => schedules.value.filter(item => !keyword.value || item.name.includes(keyword.value)))
const currentPage = ref(1)
const pageSize = ref(10)
const listTotal = computed(() => activeTab.value === '自动任务' ? filteredSchedules.value.length : filteredReports.value.length)
const pagedReports = computed(() => filteredReports.value.slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value))
const pagedSchedules = computed(() => filteredSchedules.value.slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value))
watch([keyword, date, status, activeTab, pageSize], () => { currentPage.value = 1 }, { deep: true })
watch(listTotal, count => { currentPage.value = Math.min(currentPage.value, Math.max(1, Math.ceil(count / pageSize.value))) })
function typeClass(value) { return ({ '日报': 'daily', '周报': 'weekly', '月报': 'monthly', '自动任务': 'auto' })[value] || 'daily' }
function statusClass(value) { return ({ '已完成': 'success', '待审核': 'warning', '草稿': 'muted', '运行中': 'running' })[value] || 'muted' }
function scheduleType(value) { return ({ daily: '日报', weekly: '周报', monthly: '月报' })[value] || value }
function scheduleStatus(schedule) { return ({ never: '暂无执行记录', queued: '等待生成', running: '生成中', completed: schedule.hasResult ? '已生成' : '任务完成，正文待确认', no_data: '无匹配资料，已跳过', skipped: '按节假日策略跳过', failed: '执行失败', cancelled: '已取消' })[schedule.lastStatus] || '暂无执行记录' }
function scheduleHolidayPolicy(schedule) { return schedule.config?.holiday_policy === 'skip' ? '节假日跳过' : '节假日照常执行' }
function scheduleResultPath(schedule) { return schedule.hasResult && /^[1-9]\d*$/.test(String(schedule.latestReportId || '')) ? `/portal/digests/${schedule.latestReportId}` : '' }
function scheduleTaskPath(schedule) { return /^[1-9]\d*$/.test(String(schedule.latestTaskId || '')) ? `/portal/research/tasks/${schedule.latestTaskId}` : '' }
function scheduleFilters(schedule) {
  const config = schedule.config || {}
  const sources = (config.source_types || []).map(value => ({ website: '新闻网站', wechat: '微信公众号' })[value] || value)
  return `关键词：${(config.keywords || []).join('、') || '不限'}；类别：${(config.category_names || []).join('、') || '不限'}；来源：${sources.join('、') || '不限'}`
}
function digestReportState(report) {
  if (hasReportOutput(report)) return { hasOutput: true, path: `/portal/digests/${report.id}`, status: report.status }
  const task = (portalStore.tasks || []).find(item => String(item.reportId) === String(report.id))
  return {
    hasOutput: false,
    path: task ? `/portal/research/tasks/${task.id}` : '',
    status: ({ queued: '排队中', running: '生成中', failed: '生成失败', dead_letter: '待人工处理', cancelled: '已取消', completed: '正文未就绪' })[task?.status] || '暂无正文',
  }
}
function resetFilters() { keyword.value = ''; date.value = []; status.value = 'all' }
function refreshCurrent() { return activeTab.value === '自动任务' ? loadSchedules() : portalStore.hydrate(true) }
function openSources(report) { router.push({ path: `/portal/digests/${report.id}`, query: { panel: 'sources' } }) }
async function exportDigest(report) {
  if (!hasReportOutput(report)) return ElMessage.warning('当前简报暂无正文，请先查看生成记录')
  exportingId.value = report.id
  try {
    const res = await exportPipelineResearchReport(report.id, { allowDraft: report.requiresReview })
    const blob = new Blob([res.data.content], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = res.data.fileName || `${report.title}.md`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    ElMessage.success(res.data.isDraft ? '草稿已导出' : '情报简报已导出')
  } catch (error) {
    ElMessage.error('导出失败，请确认报告已保存且后端服务可用')
  } finally {
    exportingId.value = ''
  }
}
async function loadSchedules() {
  if (schedulesLoading.value) return
  const request = ++scheduleRequest, account = portalStore.workspaceEpoch
  schedulesLoading.value = true
  schedulesError.value = ''
  try {
    const res = await listPipelineDigestSchedules()
    if (disposed || request !== scheduleRequest || account !== portalStore.workspaceEpoch) return
    schedules.value = res.data?.rows || []
  } catch (error) {
    if (disposed || request !== scheduleRequest || account !== portalStore.workspaceEpoch) return
    schedulesError.value = error?.msg || '自动计划加载失败，请重试'
  } finally {
    if (request === scheduleRequest) { schedulesLoading.value = false; queueScheduleRefresh() }
  }
}
function queueScheduleRefresh() {
  clearTimeout(refreshTimer)
  if (disposed || activeTab.value !== '自动任务' || schedulesError.value) return
  if (!schedules.value.some(item => item.enabled || ['queued','running'].includes(item.lastStatus))) return
  refreshTimer = setTimeout(() => { if (typeof document === 'undefined' || !document.hidden) loadSchedules(); else queueScheduleRefresh() }, 15000)
}
watch(activeTab, queueScheduleRefresh)
watch(() => portalStore.workspaceEpoch, () => { scheduleRequest++; schedules.value = []; schedulesLoading.value = false; schedulesError.value = ''; clearTimeout(refreshTimer) })
onBeforeUnmount(() => { disposed = true; scheduleRequest++; clearTimeout(refreshTimer) })
async function toggleSchedule(schedule) {
  if (changingScheduleId.value) return
  changingScheduleId.value = schedule.id
  try {
    const res = await updatePipelineDigestSchedule(schedule.id, { enabled: !schedule.enabled })
    Object.assign(schedule, res.data || {})
    ElMessage.success(schedule.enabled ? '自动计划已启用' : '自动计划已停用')
    await loadSchedules()
  } catch (error) {
    ElMessage.error(error?.msg || '自动计划状态更新失败')
  } finally {
    changingScheduleId.value = ''
  }
}
async function runSchedule(schedule) {
  if (!schedule.enabled || runningScheduleId.value) return
  try {
    await ElMessageBox.confirm(`补跑“${schedule.name}”将按计划规则创建任务，请先确认对应周期是否已有成果。不会覆盖现有人工修改。`, '确认补跑', { type: 'warning', confirmButtonText: '提交补跑', cancelButtonText: '取消' })
  } catch { return }
  runningScheduleId.value = schedule.id
  try {
    const res = await runPipelineDigestSchedule(schedule.id)
    Object.assign(schedule, res.data || {})
    ElMessage.success('自动计划已进入补跑队列')
  } catch (error) {
    ElMessage.error(error?.msg || '自动计划补跑提交失败')
  } finally {
    runningScheduleId.value = ''
  }
}
async function removeSchedule(schedule) {
  if (schedule.canDelete === false) return ElMessage.warning('计划已有生成历史，请停用，不能删除历史关联')
  try {
    await ElMessageBox.confirm(`删除“${schedule.name}”后不再派发新任务，已生成简报不会删除。`, '删除自动计划', { type: 'warning', confirmButtonText: '删除计划', cancelButtonText: '取消' })
  } catch { return }
  try {
    await deletePipelineDigestSchedule(schedule.id)
    schedules.value = schedules.value.filter(item => item.id !== schedule.id)
    ElMessage.success('自动计划已删除')
  } catch (error) {
    ElMessage.error(error?.msg || '自动计划删除失败')
  }
}
onMounted(loadSchedules)
</script>

<style scoped>
.ps-schedule-list { display: grid; grid-template-columns: minmax(0, 1fr); align-content: start; gap: 12px; }
.ps-schedule-card { min-width: 0; padding: 18px 20px; }
.ps-schedule-card-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.ps-schedule-card-head h2 { flex: 1 1 240px; margin: 0; font-size: 17px; overflow-wrap: anywhere; }
.ps-schedule-cadence, .ps-schedule-rules, .ps-schedule-history-note { margin: 10px 0 0; color: var(--ps-muted); font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.ps-schedule-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 14px 0; }
.ps-schedule-metrics dt { color: var(--ps-muted); font-size: 12px; margin-bottom: 6px; }
.ps-schedule-metrics dd { margin: 0; overflow-wrap: anywhere; font-size: 14px; }
.ps-schedule-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
.ps-schedule-actions :deep(.el-button) { margin-left: 0; }
.ps-schedule-notice { margin-top: 12px; }
.is-failure :deep(.el-alert__description) { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.7; }
@media (max-width: 560px) { .ps-schedule-card { padding: 14px; } .ps-schedule-metrics { grid-template-columns: minmax(0, 1fr); } }
@media (min-width: 1051px) {
  .ps-digest-toolbar > .ps-search-inline { flex: 1 1 160px; }
  .ps-digest-toolbar :deep(.el-date-editor) { flex: 0 1 260px; width: 260px; }
  .ps-digest-toolbar > .el-select { flex: 0 0 110px; width: 110px !important; }
  .ps-digest-toolbar > .el-button { margin-left: 0; }
}
</style>
