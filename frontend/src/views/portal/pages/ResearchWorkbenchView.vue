<template>
  <div class="ps-page ps-research-workspace ps-list-page">
    <div class="ps-toolbar ps-research-toolbar">
      <div class="ps-research-toolbar-row">
        <el-input class="ps-search-input" v-model.trim="keyword" clearable aria-label="搜索报告" placeholder="搜索报告名称或类型" :prefix-icon="Search" />
        <el-select v-model="status" placeholder="全部状态" aria-label="报告生成状态"><el-option label="全部状态" value="" /><el-option v-for="item in reportStatuses" :key="item.value" :label="item.label" :value="item.value" /></el-select>
        <div class="ps-research-toolbar-actions">
          <el-button v-if="keyword || status" @click="keyword = ''; status = ''">重置</el-button>
          <el-button type="primary" :icon="Plus" @click="router.push('/portal/research/create')">新建报告</el-button>
        </div>
      </div>
    </div>
    <div class="ps-report-workspace-content ps-list-stack">
      <section class="ps-panel ps-report-main ps-list-stack">
        <div v-if="loadError" class="ps-inline-state is-warning" role="alert"><span>{{ loadError }}</span><el-button plain :loading="refreshing" @click="refreshWorkspace">重试</el-button></div>
        <el-skeleton v-if="portalStore.dataLoading && !portalStore.dataLoaded" :rows="5" animated />
        <template v-else>
          <div ref="listRegion" class="ps-list-scroll ps-report-list-region" aria-label="科研报告列表">
            <el-table :data="pagedReports" row-key="key" :max-height="listHeight" style="width: 100%" class="ps-report-records-table" :default-sort="{ prop: 'updatedAt', order: 'descending' }" @sort-change="changeReportSort">
              <el-table-column prop="title" label="报告名称" min-width="320" sortable="custom" :sort-orders="['ascending', 'descending']">
                <template #default="{ row: report }">
                  <div class="ps-report-identity">
                    <el-icon class="ps-report-file-icon" aria-hidden="true"><Document /></el-icon>
                    <div class="ps-report-row-title">
                    <el-link v-if="report.path" underline="hover" :href="$router.resolve(report.path).href" class="ps-report-title-link" :aria-label="`打开报告：${report.title}`" @click.prevent="router.push(report.path)">{{ report.title }}</el-link>
                    <strong v-else>{{ report.title }}</strong>
                    <small v-if="report.words">{{ Number(report.words).toLocaleString() }} 字</small>
                    <el-progress v-if="report.status === 'active'" :percentage="report.progress" :stroke-width="4" />
                    </div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="104">
                <template #default="{ row: report }"><el-tag :type="({ success: 'success', danger: 'danger', running: 'primary' })[statusClass(report.status)] || 'info'">{{ report.statusLabel }}</el-tag></template>
              </el-table-column>
              <el-table-column prop="updatedAt" label="更新时间" width="180" show-overflow-tooltip sortable="custom" :sort-orders="['descending', 'ascending']">
                <template #default="{ row }"><time>{{ row.updatedAt || '时间未提供' }}</time></template>
              </el-table-column>
              <el-table-column label="操作" width="232" align="right">
                <template #default="{ row: report }"><div class="ps-report-row-actions"><el-button v-for="action in reportRowActions(report)" :key="action.label" plain :type="action.primary ? 'primary' : 'default'" :disabled="deletingId === String(report.id)" @click="router.push(action.path)">{{ action.label }}</el-button><el-button v-if="canDeleteResearchReport(report)" type="danger" plain :loading="deletingId === String(report.id)" :disabled="Boolean(deletingId)" @click="deleteReport(report)">删除</el-button><span v-if="!reportRowActions(report).length" class="ps-muted">暂无可用操作</span></div></template>
              </el-table-column>
              <template #empty><span role="status">{{ loadError ? '列表加载失败，请重试' : keyword || status ? '暂无匹配报告' : '暂无报告' }}</span></template>
            </el-table>
          </div>
          <div v-if="filteredReports.length" class="ps-pagination" aria-label="科研报告列表分页"><el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[10, 20, 50]" :total="filteredReports.length" :pager-count="5" layout="total, sizes, ->, prev, pager, next, jumper" background /></div>
        </template>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Document, Plus, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import usePortalStore from '@/store/modules/portal'
import { buildPersonalReports } from '@/utils/portal/personalReports'
import useUserStore from '@/store/modules/user'
import { sortResearchReports } from '../utils/reportList'
import { isDigestType } from '../utils/routing'
import { canDeleteResearchReport, createResearchRefresh, removeDeletedReport, reportRowActions } from '@/utils/portal/researchWorkspace'
import { deletePipelineResearchReport, listPipelineResearchJobs, listPipelineResearchReports } from '@/api/pipeline/intelligence'

const router = useRouter()
const route = useRoute()
const portalStore = usePortalStore()
const userStore = useUserStore()
const refreshing = ref(false)
const deletingId = ref('')
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
const refresher = createResearchRefresh({ store: portalStore, loadJobs: listPipelineResearchJobs,
  loadReports: listPipelineResearchReports, waitForHydration: () => portalStore.hydrate() })
let refreshTimer, disposed = false
function scheduleRefresh() {
  clearTimeout(refreshTimer)
  if (!disposed && !deletingId.value && typeof document !== 'undefined' && !document.hidden && researchReports.value.some(item => item.status === 'active')) {
    refreshTimer = setTimeout(refreshWorkspace, 5000)
  }
}
async function refreshWorkspace() {
  if (disposed || refreshing.value || deletingId.value) return
  const epoch = portalStore.workspaceEpoch
  refreshing.value = true
  try { await refresher.run() }
  catch { if (!disposed && epoch === portalStore.workspaceEpoch) portalStore.sectionErrors.reports = '列表暂时无法更新，已保留原内容，请重试' }
  finally { refreshing.value = false; scheduleRefresh() }
}
function handleVisibility() {
  if (document.hidden) { clearTimeout(refreshTimer); refresher.invalidate() }
  else void refreshWorkspace()
}
async function deleteReport(report) {
  if (deletingId.value || !canDeleteResearchReport(report)) return
  const epoch = portalStore.workspaceEpoch
  const owner = userStore.id
  const id = String(report.id)
  deletingId.value = id
  clearTimeout(refreshTimer)
  refresher.invalidate()
  try {
    await ElMessageBox.confirm(`确认删除报告“${report.title}”？该报告及其生成、编辑和导出记录将被删除，引用的新闻、论文和上传资料不受影响。`, '删除报告', {
      type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消', closeOnClickModal: false
    })
    if (disposed || epoch !== portalStore.workspaceEpoch || owner !== userStore.id) return
    await deletePipelineResearchReport(id)
    if (disposed || epoch !== portalStore.workspaceEpoch || owner !== userStore.id) return
    refresher.invalidate()
    removeDeletedReport(portalStore, id)
    ElMessage.success('报告已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close' && !disposed && epoch === portalStore.workspaceEpoch) {
      ElMessage.error(error?.msg || error?.message || '删除失败，请重试')
    }
  } finally {
    deletingId.value = ''
    scheduleRefresh()
  }
}
const researchReports = computed(() => buildPersonalReports({ reports: portalStore.researchReports, tasks: portalStore.tasks.filter(task => !isDigestType(task.reportType || task.type)), userId: userStore.id }))
const keyword = ref(String(route.query.q || ''))
const normalizeStatus = value => value === 'completed' ? 'generated' : ['active', 'generated', 'failed', 'cancelled', 'unavailable'].includes(value) ? value : ''
const status = ref(normalizeStatus(route.query.status))
watch(() => route.query, query => { keyword.value = String(query.q || ''); status.value = normalizeStatus(query.status) })
const currentPage = ref(1)
const pageSize = ref(10)
const sort = ref('updated-desc')
function changeReportSort({ prop, order }) {
  sort.value = prop === 'title' && order ? (order === 'descending' ? 'title-desc' : 'title')
    : order === 'ascending' ? 'updated-asc' : 'updated-desc'
}
const reportStatuses = [{ value: 'active', label: '生成中' }, { value: 'generated', label: '已生成' }, { value: 'failed', label: '失败' }, { value: 'cancelled', label: '已取消' }, { value: 'unavailable', label: '暂无正文' }]
const loadError = computed(() => portalStore.sectionErrors.reports || portalStore.sectionErrors.tasks || portalStore.sectionErrors.digests)
const filteredReports = computed(() => researchReports.value.filter(item => (!status.value || item.status === status.value) && (!keyword.value || `${item.title} ${item.typeLabel}`.toLocaleLowerCase().includes(keyword.value.toLocaleLowerCase()))))
const pagedReports = computed(() => sortResearchReports(filteredReports.value, sort.value).slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value))
watch([keyword, status, sort, pageSize], () => { currentPage.value = 1 })
watch(() => filteredReports.value.length, count => { currentPage.value = Math.min(currentPage.value, Math.max(1, Math.ceil(count / pageSize.value))) })
function statusClass(value) { return ({ active: 'running', generated: 'success', failed: 'danger', cancelled: 'muted' })[value] || 'muted' }
watch(() => researchReports.value.some(item => item.status === 'active'), scheduleRefresh)
watch(() => portalStore.workspaceEpoch, () => { clearTimeout(refreshTimer); refresher.invalidate() })
onMounted(() => { void refreshWorkspace(); if (typeof document !== 'undefined') document.addEventListener('visibilitychange', handleVisibility) })
onBeforeUnmount(() => { listResizeObserver?.disconnect(); disposed = true; clearTimeout(refreshTimer); refresher.stop(); if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', handleVisibility) })
</script>

<style scoped>
.ps-research-workspace > .ps-research-toolbar { overflow-x: auto; }
.ps-research-toolbar-row { display: grid; grid-template-columns: minmax(160px, 1fr) 124px max-content; align-items: center; gap: 8px; width: 100%; min-width: 0; --el-component-size: 40px; }
.ps-research-toolbar-row > .el-input, .ps-research-toolbar-row > .el-select { min-width: 0; width: 100%; }
.ps-research-toolbar-actions { display: flex; flex-wrap: nowrap; align-items: center; gap: 8px; }
.ps-research-toolbar-actions :deep(.el-button) { flex-shrink: 0; height: 40px; margin-left: 0; }
.ps-research-workspace .ps-report-main.ps-panel { padding: 0; border: 0; border-radius: 0; background: transparent; gap: 12px; }
.ps-report-list-region { overflow: hidden; }
.ps-research-workspace .ps-report-main > .ps-pagination { margin: 0; padding: 12px 16px; border: 1px solid var(--ps-line); border-radius: 10px; background: #fff; }
.ps-report-identity { display: flex; align-items: flex-start; gap: 12px; min-width: 0; }
.ps-report-file-icon { flex: 0 0 36px; width: 36px; height: 40px; margin-top: 2px; border-radius: 8px; background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-size: 20px; }
.ps-report-row-title { flex: 1; min-width: 0; display: flex; flex-direction: column; align-items: flex-start; gap: 6px; }
.ps-report-title-link { max-width: 100%; color: var(--ps-ink); font-size: 15px; font-weight: 600; line-height: 1.6; text-align: left; white-space: normal; overflow-wrap: anywhere; }
.ps-report-title-link:hover { color: var(--el-color-primary); }
.ps-report-row-title > .el-progress { width: 100%; max-width: 240px; }
.ps-report-row-title small { color: var(--ps-muted); font-size: 12px; line-height: 1.5; }
.ps-report-row-actions { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 8px; }
.ps-report-row-actions :deep(.el-button) { margin: 0; }
.ps-report-records-table { border: 1px solid var(--ps-line); border-radius: 10px; }
.ps-report-records-table :deep(.el-table__cell) { padding-block: 14px; }
.ps-report-records-table :deep(th.el-table__cell) { padding-block: 10px; color: var(--ps-muted); font-size: 12px; font-weight: 500; }
.ps-report-records-table :deep(.cell) { padding-inline: 16px; }
.ps-report-records-table time { color: var(--ps-muted); font-size: 13px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.ps-report-records-table :deep(.el-table__inner-wrapper::before) { display: none; }
</style>
