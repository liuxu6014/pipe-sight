<template>
  <div class="ps-page ps-list-page ps-digest-page">
    <div class="ps-toolbar ps-digest-toolbar"><div class="ps-search-inline"><Search /><input v-model.trim="keyword" aria-label="搜索简报或计划名称" placeholder="搜索简报或计划名称" /></div><template v-if="activeTab !== '自动任务'"><el-date-picker v-model="date" aria-label="简报覆盖周期" type="daterange" value-format="YYYY-MM-DD" start-placeholder="覆盖开始日期" end-placeholder="覆盖结束日期" /><el-select v-model="status" aria-label="简报状态" style="width: 130px"><el-option label="全部状态" value="all" /><el-option v-for="value in reportStatuses" :key="value" :label="value" :value="value" /></el-select></template><el-button v-if="hasActiveFilters" @click="resetFilters">清除筛选</el-button><el-button :icon="Plus" @click="editSchedule()">新建自动计划</el-button><el-button type="primary" :icon="Plus" @click="router.push('/portal/digests/create')">新建简报</el-button></div>
    <div v-if="currentError" class="ps-inline-state is-warning" role="alert"><span>{{ currentError }}</span><el-button plain @click="refreshCurrent">重试</el-button></div>
    <div class="ps-tabs-line ps-segmented-row"><el-segmented v-model="activeTab" :options="tabs" aria-label="简报与自动计划"  /></div>
    <section v-if="activeTab !== '自动任务'" ref="listRegion" class="ps-panel ps-digest-list ps-list-scroll" tabindex="0" aria-label="简报列表">
      <el-table v-if="filteredReports.length" :data="pagedReports" row-key="id" :max-height="listHeight" style="width: 100%" class="ps-digest-records-table">
        <el-table-column header-align="center" label="简报名称" min-width="320"><template #default="{ row }">
          <div class="ps-digest-identity">
            <el-icon class="ps-digest-file-icon" aria-hidden="true"><Document /></el-icon>
            <div class="ps-digest-title-copy">
              <el-link underline="hover" :href="$router.resolve(row.path || '/portal').href" class="ps-digest-title-link" :disabled="!row.path" @click.prevent="router.push(row.path)">{{ row.title }}</el-link>
              <small v-if="row.sources != null">{{ row.sources }} 条来源</small>
            </div>
          </div>
        </template></el-table-column>
        <el-table-column header-align="center" align="center" label="类型" width="90"><template #default="{ row }"><el-tag effect="plain" :type="scheduleType(row.reportType || row.type) === '月报' ? 'success' : 'primary'">{{ scheduleType(row.reportType || row.type) }}</el-tag></template></el-table-column>
        <el-table-column header-align="center" prop="period" label="覆盖周期" width="220"><template #default="{ row }"><span class="ps-digest-period">{{ row.period }}</span></template></el-table-column>
        <el-table-column header-align="center" label="状态" width="104"><template #default="{ row }"><el-tag :type="({ success: 'success', warning: 'warning', running: 'primary' })[statusClass(row.status)] || 'info'">{{ row.status }}</el-tag></template></el-table-column>
        <el-table-column header-align="center" prop="updatedAt" label="更新时间" width="180"><template #default="{ row }"><time>{{ row.updatedAt }}</time></template></el-table-column>
        <el-table-column header-align="center" label="操作" width="232" align="right">
          <template #default="{ row: report }">
            <div class="ps-digest-row-actions">
              <el-button type="primary" plain :disabled="!report.path" @click="router.push(report.path)">{{ report.hasOutput ? '查看' : '生成记录' }}</el-button>
              <template v-if="report.hasOutput">
                <el-button plain :loading="exportingId === report.id" :disabled="Boolean(exportingId)" :title="report.requiresReview ? '导出草稿 Markdown' : '导出 Markdown'" @click="exportDigest(report)">导出</el-button>
                <el-button plain @click="openSources(report)">来源</el-button>
              </template>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <el-skeleton v-if="portalStore.dataLoading && !portalStore.dataLoaded" :rows="4" animated />
      <div v-else-if="!filteredReports.length && !currentError" class="ps-empty-state" role="status">暂无简报</div>
    </section>
    <section v-else ref="listRegion" class="ps-panel ps-digest-list ps-schedule-list ps-list-scroll" tabindex="0" aria-label="简报自动任务列表">
      <el-table v-if="pagedSchedules.length" :data="pagedSchedules" row-key="id" :max-height="listHeight" class="ps-digest-records-table ps-schedule-table" style="width: 100%">
        <el-table-column label="计划名称与筛选条件" min-width="320" header-align="center">
          <template #default="{ row: schedule }">
            <div class="ps-schedule-identity"><h2>{{ schedule.name }}</h2><el-tag :type="schedule.enabled ? 'success' : 'info'">{{ schedule.enabled ? '已启用' : '已停用' }}</el-tag></div>
            <p class="ps-schedule-rules">{{ scheduleFilters(schedule) }}</p>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="80" align="center" header-align="center"><template #default="{ row: schedule }"><el-tag effect="plain">{{ scheduleType(schedule.reportType) }}</el-tag></template></el-table-column>
        <el-table-column label="执行时间" width="220" header-align="center">
          <template #default="{ row: schedule }"><div class="ps-schedule-timing"><span>{{ scheduleTimeDescription(schedule) }}</span><small>{{ scheduleHolidayPolicy(schedule) }}</small></div></template>
        </el-table-column>
        <el-table-column label="最近执行结果" min-width="280" header-align="center">
          <template #default="{ row: schedule }">
            <div class="ps-schedule-result-head"><el-tag :type="schedule.lastStatus === 'failed' ? 'danger' : schedule.hasResult ? 'success' : 'info'">{{ scheduleStatus(schedule) }}</el-tag><span v-if="Number.isInteger(schedule.matchedCount)" class="ps-schedule-count">选材 {{ schedule.matchedCount }} 篇</span></div>
            <time v-if="schedule.lastRunTime" class="ps-schedule-last-run">{{ formatBusinessTime(schedule.lastRunTime) }}</time>
            <p v-if="schedule.lastStatus === 'no_data'" class="ps-schedule-result-note">本周期无匹配的有效文章，未创建生成任务。</p>
            <p v-else-if="schedule.lastStatus === 'skipped'" class="ps-schedule-result-note">执行日属于配置的节假日，未创建生成任务。</p>
            <p v-else-if="schedule.lastStatus === 'failed'" class="ps-schedule-result-note is-failure" role="status">{{ schedule.lastError || '此次失败未记录具体原因，请打开任务进度查看或联系管理员检查日志。' }}</p>
          </template>
        </el-table-column>
        <el-table-column label="下次执行" width="180" header-align="center"><template #default="{ row: schedule }"><span class="ps-schedule-next-run">{{ schedule.enabled ? (formatBusinessTime(schedule.nextRunTime) || '等待调度确认') : '计划已停用' }}</span></template></el-table-column>
        <el-table-column label="操作" width="260" header-align="center" align="right">
          <template #default="{ row: schedule }">
            <div class="ps-schedule-actions">
              <el-button v-if="scheduleTaskPath(schedule)" plain @click="router.push(scheduleTaskPath(schedule))">任务进度</el-button>
              <el-button plain @click="editSchedule(schedule)">{{ isDaily(schedule) ? '查看计划' : '编辑计划' }}</el-button>
              <template v-if="!isDaily(schedule)">
                <el-button type="primary" plain :loading="runningScheduleId === schedule.id" :disabled="!schedule.enabled || !!runningScheduleId" @click="runSchedule(schedule)">立即补跑</el-button>
                <el-switch :model-value="schedule.enabled" :loading="changingScheduleId === schedule.id" :disabled="!!changingScheduleId" :aria-label="`${schedule.name}自动计划开关`" active-text="启用" inactive-text="停用" @change="toggleSchedule(schedule)" />
              </template>
              <el-button
                type="danger"
                plain
                :loading="deletingScheduleId === schedule.id"
                :disabled="schedule.canDelete !== true || !!deletingScheduleId"
                :title="schedule.canDelete === true ? '删除自动计划' : '已有生成历史，无法删除'"
                @click="removeSchedule(schedule)"
              >删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <el-skeleton v-if="schedulesLoading && !schedules.length" :rows="4" animated />
      <div v-else-if="!filteredSchedules.length && !currentError && !schedulesLoading" class="ps-empty-state" role="status">暂无自动任务</div>
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
import { Document, Plus, Search } from '@element-plus/icons-vue'
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
const listRegion = ref(null)
const listHeight = ref()
let listResizeObserver
watch(listRegion, element => {
  listResizeObserver?.disconnect()
  if (!element || typeof ResizeObserver === 'undefined') return
  listResizeObserver = new ResizeObserver(([entry]) => {
    listHeight.value = Math.max(1, Math.floor(entry.contentRect.height))
  })
  listResizeObserver.observe(element)
}, { flush: 'post' })
const keyword = ref('')
const date = ref([])
const status = ref('all')
const activeTab = ref(route.query.tab === 'schedules' ? '自动任务' : '全部')
const hasActiveFilters = computed(() => Boolean(keyword.value
  || (activeTab.value !== '自动任务' && (date.value?.length || status.value !== 'all'))))
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
const digestRows = computed(() => portalStore.digestReports
  .filter(item => ['周报', '月报'].includes(scheduleType(item.reportType || item.type)))
  .map(item => ({ ...item, ...digestReportState(item) })))
const reportStatuses = computed(() => [...new Set(digestRows.value.map(item => item.status).filter(Boolean))])
const runningScheduleId = ref('')
const changingScheduleId = ref('')
const deletingScheduleId = ref('')
const tabs = ['全部', '周报', '月报', '自动任务']
function isDaily(row) { return ['daily', '日报'].includes(row?.reportType || row?.type) }
const filteredReports = computed(() => digestRows.value.filter(item => {
  const matchesDate = periodOverlaps(item, date.value)
  return (activeTab.value === '全部' || scheduleType(item.reportType || item.type) === activeTab.value) && (status.value === 'all' || item.status === status.value) && (!keyword.value || item.title.includes(keyword.value)) && matchesDate
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
onBeforeUnmount(() => { listResizeObserver?.disconnect(); disposed = true; scheduleRequest++; clearTimeout(refreshTimer) })
async function toggleSchedule(schedule) {
  if (isDaily(schedule) || changingScheduleId.value) return
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
  if (isDaily(schedule) || !schedule.enabled || runningScheduleId.value) return
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
  if (deletingScheduleId.value || schedule.canDelete !== true) return
  const account = portalStore.workspaceEpoch
  deletingScheduleId.value = schedule.id
  try {
    try {
      await ElMessageBox.confirm(`删除“${schedule.name}”后将停止派发，确定删除？`, '删除自动计划', {
        type: 'warning', confirmButtonText: '删除计划', cancelButtonText: '取消',
      })
    } catch { return }
    if (disposed || account !== portalStore.workspaceEpoch) return
    await deletePipelineDigestSchedule(schedule.id)
    if (disposed || account !== portalStore.workspaceEpoch) return
    // Invalidate a list request started before the deletion was acknowledged.
    scheduleRequest++
    schedulesLoading.value = false
    schedules.value = schedules.value.filter(item => item.id !== schedule.id)
    queueScheduleRefresh()
    ElMessage.success('自动计划已删除')
  } catch (error) {
    if (!disposed && account === portalStore.workspaceEpoch) ElMessage.error(error?.msg || '自动计划删除失败')
  } finally {
    deletingScheduleId.value = ''
  }
}
onMounted(loadSchedules)
</script>

<style scoped>
.ps-digest-page .ps-digest-list { padding: 0; border: 0; border-radius: 0; background: transparent; overflow: hidden; }
.ps-digest-page > .ps-pagination { margin: 0; padding: 12px 16px; border: 1px solid var(--ps-line); border-radius: 10px; background: #fff; }
.ps-digest-records-table { border: 1px solid var(--ps-line); border-radius: 10px; }
.ps-digest-records-table :deep(th.el-table__cell) { padding-block: 10px; color: var(--ps-muted); font-size: 12px; font-weight: 500; }
.ps-digest-records-table :deep(.cell) { padding-inline: 16px; }
.ps-digest-records-table :deep(.el-table__inner-wrapper::before) { display: none; }
.ps-digest-identity { display: flex; align-items: flex-start; gap: 12px; min-width: 0; }
.ps-digest-file-icon { flex: 0 0 36px; width: 36px; height: 40px; margin-top: 2px; border-radius: 8px; background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-size: 20px; }
.ps-digest-title-copy { flex: 1; min-width: 0; display: flex; flex-direction: column; align-items: flex-start; gap: 6px; }
.ps-digest-title-link { max-width: 100%; color: var(--ps-ink); font-size: 15px; font-weight: 600; line-height: 1.6; text-align: left; white-space: normal; overflow-wrap: anywhere; }
.ps-digest-title-link:hover { color: var(--el-color-primary); }
.ps-digest-title-copy small { color: var(--ps-muted); font-size: 12px; line-height: 1.5; }
.ps-digest-records-table time, .ps-digest-period { color: var(--ps-muted); font-size: 13px; font-variant-numeric: tabular-nums; }
.ps-digest-records-table time, .ps-digest-period { white-space: nowrap; }
.ps-digest-row-actions { display: flex; align-items: center; justify-content: flex-end; flex-wrap: nowrap; gap: 8px; }
.ps-digest-row-actions > .el-button { margin: 0; flex-shrink: 0; }
.ps-schedule-table :deep(td.el-table__cell) { padding-block: 14px; vertical-align: top; }
.ps-schedule-table :deep(.cell) { overflow-wrap: anywhere; }
.ps-schedule-identity { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.ps-schedule-identity h2 { margin: 0; color: var(--ps-ink); font-size: 15px; font-weight: 600; line-height: 1.6; overflow-wrap: anywhere; }
.ps-schedule-rules { margin: 8px 0 0; color: var(--ps-muted); font-size: 12px; line-height: 1.7; overflow-wrap: anywhere; }
.ps-schedule-timing { display: flex; flex-direction: column; gap: 6px; font-size: 13px; line-height: 1.6; }
.ps-schedule-timing small { color: var(--ps-muted); font-size: 12px; }
.ps-schedule-result-head { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; }
.ps-schedule-count { color: var(--ps-muted); font-size: 12px; }
.ps-schedule-last-run { display: block; margin-top: 6px; }
.ps-schedule-result-note { margin: 6px 0 0; color: var(--ps-muted); font-size: 12px; line-height: 1.7; white-space: pre-wrap; overflow-wrap: anywhere; }
.ps-schedule-result-note.is-failure { color: var(--el-color-danger-dark-2); padding: 6px 8px; border-radius: 4px; background: var(--el-color-danger-light-9); }
.ps-schedule-next-run { color: var(--ps-muted); font-size: 13px; font-variant-numeric: tabular-nums; }
.ps-schedule-actions { display: flex; justify-content: flex-end; align-items: center; flex-wrap: wrap; gap: 8px; }
.ps-schedule-actions > .el-button, .ps-schedule-actions > .el-switch { margin: 0; }
@media (min-width: 1051px) {
  .ps-digest-toolbar > .ps-search-inline { flex: 1 1 160px; }
  .ps-digest-toolbar :deep(.el-date-editor) { flex: 0 1 260px; width: 260px; }
  .ps-digest-toolbar > .el-select { flex: 0 0 110px; width: 110px !important; }
  .ps-digest-toolbar > .el-button { margin-left: 0; }
}
</style>
