<template>
  <div class="ps-page">
    <div class="ps-toolbar ps-digest-toolbar"><div class="ps-search-inline"><Search /><input v-model.trim="keyword" aria-label="搜索简报或计划名称" placeholder="搜索简报或计划名称" /></div><template v-if="activeTab !== '自动任务'"><el-date-picker v-model="date" aria-label="简报覆盖周期" type="daterange" value-format="YYYY-MM-DD" start-placeholder="覆盖开始日期" end-placeholder="覆盖结束日期" /><el-select v-model="status" aria-label="简报状态" style="width: 130px"><el-option label="全部状态" value="all" /><el-option v-for="value in reportStatuses" :key="value" :label="value" :value="value" /></el-select></template><el-button v-if="keyword || date?.length || status !== 'all'" @click="resetFilters">清除筛选</el-button><el-button type="primary" :icon="Plus" @click="router.push('/portal/digests/create')">新建简报</el-button></div>
    <div v-if="currentError" class="ps-inline-state is-warning" role="alert"><span>{{ currentError }}</span><el-button text @click="refreshCurrent">重试</el-button></div>
    <div class="ps-tabs-line"><button v-for="tab in tabs" :key="tab" type="button" :class="{ 'is-active': activeTab === tab }" @click="activeTab = tab">{{ tab }}</button></div>
    <section v-if="activeTab !== '自动任务'" class="ps-panel ps-digest-list">
      <div v-if="filteredReports.length" class="ps-section-head"><h2>简报成果</h2></div>
      <el-table v-if="filteredReports.length" :data="pagedReports" style="width: 100%">
        <el-table-column label="简报名称" min-width="260"><template #default="{ row }"><button class="ps-table-title-button" type="button" @click="router.push(`/portal/digests/${row.id}`)">{{ row.title }}</button><small class="ps-table-subtitle">{{ row.version }}</small></template></el-table-column>
        <el-table-column prop="type" label="类型" width="80" />
        <el-table-column prop="period" label="覆盖周期" min-width="180" />
        <el-table-column label="来源数" width="90"><template #default="{ row }">{{ row.sources ?? '未提供' }}</template></el-table-column>
        <el-table-column label="状态" width="130"><template #default="{ row }"><span class="ps-status-pill" :class="`is-${statusClass(row.status)}`">{{ row.status }}</span></template></el-table-column>
        <el-table-column prop="updatedAt" label="更新时间" width="170" />
        <el-table-column label="操作" width="160" fixed="right"><template #default="{ row: report }"><div class="ps-table-actions"><el-button type="primary" text @click="router.push(`/portal/digests/${report.id}`)">打开简报</el-button><el-dropdown trigger="click"><el-button text :aria-label="`${report.title}更多操作`"><MoreFilled /></el-button><template #dropdown><el-dropdown-menu><el-dropdown-item :disabled="exportingId === report.id" @click="exportDigest(report)">{{ exportingId === report.id ? '正在导出…' : report.requiresReview ? '导出草稿 Markdown' : '导出 Markdown' }}</el-dropdown-item><el-dropdown-item @click="openSources(report)">打开来源清单</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div></template></el-table-column>
      </el-table>
      <el-skeleton v-if="portalStore.dataLoading && !portalStore.dataLoaded" :rows="4" animated />
      <div v-else-if="!filteredReports.length && !currentError" class="ps-empty-state" role="status">暂无简报</div>
    </section>
    <section v-else class="ps-digest-grid ws-card-grid">
      <article v-for="schedule in pagedSchedules" :key="schedule.id" class="ps-digest-card"><div class="ps-digest-cover is-auto"><span>自动任务</span><strong>{{ scheduleType(schedule.reportType) }}</strong><i></i></div><div class="ps-digest-body"><div class="ps-digest-state"><span class="ps-status-pill" :class="schedule.enabled ? 'is-success' : 'is-muted'">{{ schedule.enabled ? '已启用' : '已停用' }}</span><small>{{ schedule.scheduleTime }} 执行 · {{ schedule.holidayPolicy === 'skip' ? '节假日跳过' : '节假日照常执行' }}</small></div><button type="button">{{ schedule.name }}</button><dl><div><dt>下次执行</dt><dd>{{ formatBusinessTime(schedule.nextRunTime) || '待计算' }}</dd></div><div><dt>最近状态</dt><dd>{{ scheduleStatus(schedule) }}</dd></div><div><dt>连续失败</dt><dd>{{ schedule.failureCount || 0 }} 次</dd></div></dl><div class="ps-card-actions"><el-button type="primary" text :loading="runningScheduleId === schedule.id" :disabled="!schedule.enabled" @click="runSchedule(schedule)">立即补跑</el-button><el-button type="primary" text @click="toggleSchedule(schedule)">{{ schedule.enabled ? '停用计划' : '启用计划' }}</el-button><el-button type="danger" text @click="removeSchedule(schedule)">删除</el-button></div></div></article>
      <el-skeleton v-if="schedulesLoading" :rows="4" animated />
      <div v-else-if="!filteredSchedules.length && !currentError" class="ps-empty-state" role="status">暂无自动任务</div>
    </section>
    <div v-if="listTotal && !currentError" class="ps-pagination" aria-label="情报简报列表分页"><el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[10, 20, 50]" :total="listTotal" :pager-count="5" layout="total, sizes, ->, prev, pager, next, jumper" background /></div>
  </div>
</template>

<script setup>
import { formatBusinessTime } from '@/utils/portal/businessTime'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MoreFilled, Plus, Search } from '@element-plus/icons-vue'
import usePortalStore from '@/store/modules/portal'
import { exportPipelineResearchReport } from '@/api/pipeline/intelligence'
import { deletePipelineDigestSchedule, listPipelineDigestSchedules, runPipelineDigestSchedule, updatePipelineDigestSchedule } from '@/api/pipeline/intelligence'
import { periodOverlaps } from '../utils/workspace'

const router = useRouter()
const portalStore = usePortalStore()
const keyword = ref('')
const date = ref([])
const status = ref('all')
const activeTab = ref('全部')
const exportingId = ref('')
const schedules = ref([])
const schedulesLoading = ref(false)
const schedulesError = ref('')
const currentError = computed(() => activeTab.value === '自动任务' ? schedulesError.value : portalStore.sectionErrors.digests || portalStore.sectionErrors.reports)
const reportStatuses = computed(() => [...new Set(portalStore.digestReports.map(item => item.status).filter(Boolean))])
const runningScheduleId = ref('')
const tabs = ['全部', '日报', '周报', '月报', '自动任务']
const filteredReports = computed(() => portalStore.digestReports.filter(item => {
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
function scheduleStatus(schedule) { return ({ queued: '已入队', no_data: '周期无数据', skipped: '按节假日策略跳过', failed: '派发失败' })[schedule.lastStatus] || '尚未执行' }
function resetFilters() { keyword.value = ''; date.value = []; status.value = 'all' }
function refreshCurrent() { return activeTab.value === '自动任务' ? loadSchedules() : portalStore.hydrate(true) }
function openSources(report) { router.push({ path: `/portal/digests/${report.id}`, query: { panel: 'sources' } }) }
async function exportDigest(report) {
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
  schedulesLoading.value = true
  schedulesError.value = ''
  try {
    const res = await listPipelineDigestSchedules()
    schedules.value = res.data?.rows || []
  } catch (error) {
    schedulesError.value = error?.msg || '自动计划加载失败，请重试'
  } finally {
    schedulesLoading.value = false
  }
}
async function toggleSchedule(schedule) {
  try {
    const res = await updatePipelineDigestSchedule(schedule.id, { enabled: !schedule.enabled })
    Object.assign(schedule, res.data || {})
    ElMessage.success(schedule.enabled ? '自动计划已启用' : '自动计划已停用')
  } catch (error) {
    ElMessage.error('自动计划状态更新失败')
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
  try {
    await ElMessageBox.confirm(`删除“${schedule.name}”后不再派发新任务，已生成简报不会删除。`, '删除自动计划', { type: 'warning', confirmButtonText: '删除计划', cancelButtonText: '取消' })
  } catch { return }
  try {
    await deletePipelineDigestSchedule(schedule.id)
    schedules.value = schedules.value.filter(item => item.id !== schedule.id)
    ElMessage.success('自动计划已删除')
  } catch (error) {
    ElMessage.error('自动计划删除失败')
  }
}
onMounted(loadSchedules)
</script>

<style scoped>
@media (min-width: 1051px) {
  .ps-digest-toolbar > .ps-search-inline { flex: 1 1 160px; }
  .ps-digest-toolbar :deep(.el-date-editor) { flex: 0 1 260px; width: 260px; }
  .ps-digest-toolbar > .el-select { flex: 0 0 110px; width: 110px !important; }
  .ps-digest-toolbar > .el-button { margin-left: 0; }
}
</style>
