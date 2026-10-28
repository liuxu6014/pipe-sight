<template>
  <div class="ps-page ps-research-workspace ps-list-page">
    <div class="ps-toolbar ps-research-toolbar">
        <el-input class="ps-search-input" v-model.trim="keyword" clearable aria-label="搜索报告" placeholder="搜索报告名称或类型" :prefix-icon="Search" />
        <el-select v-model="status" placeholder="全部状态" aria-label="报告生成状态"><el-option label="全部状态" value="" /><el-option v-for="item in reportStatuses" :key="item.value" :label="item.label" :value="item.value" /></el-select>
        <el-select v-model="sort" aria-label="报告排序"><el-option label="最近更新" value="updated-desc" /><el-option label="最早更新" value="updated-asc" /><el-option label="名称排序" value="title" /></el-select>
        <el-button :loading="refreshing" @click="refreshWorkspace">刷新</el-button>
        <el-button v-if="keyword || status" @click="keyword = ''; status = ''">重置</el-button>
      <div class="ps-research-toolbar-actions"><el-button type="primary" :icon="Plus" @click="router.push('/portal/research/create')">新建报告</el-button></div>
    </div>
    <div class="ps-report-workspace-content ps-list-stack">
      <section class="ps-panel ps-report-main ps-list-stack">
        <div v-if="loadError" class="ps-inline-state is-warning" role="alert"><span>{{ loadError }}</span><el-button plain :loading="refreshing" @click="refreshWorkspace">重试</el-button></div>
        <el-skeleton v-if="portalStore.dataLoading && !portalStore.dataLoaded" :rows="5" animated />
        <template v-else>
          <div class="ps-list-scroll" tabindex="0" aria-label="科研报告列表">
          <div v-if="filteredReports.length" class="ps-report-table">
            <div class="ps-table-head"><span>报告名称</span><span>状态</span><span>更新时间</span><span>操作</span></div>
            <article v-for="report in pagedReports" :key="report.key" class="ps-report-list-row">
              <div class="ps-report-row-title"><button v-if="report.path" type="button" :aria-label="`打开报告：${report.title}`" @click="router.push(report.path)">{{ report.title }}</button><strong v-else>{{ report.title }}</strong><small>{{ report.typeLabel }}<template v-if="report.words"> · {{ Number(report.words).toLocaleString() }} 字</template></small><el-progress v-if="report.status === 'active'" :percentage="report.progress" :stroke-width="4" /></div>
              <span><b class="ps-status-pill" :class="`is-${statusClass(report.status)}`">{{ report.statusLabel }}</b></span><time>{{ report.updatedAt || '时间未提供' }}</time>
              <div class="ps-report-row-actions"><el-button v-for="action in reportRowActions(report)" :key="action.label" plain :type="action.primary ? 'primary' : 'default'" @click="router.push(action.path)">{{ action.label }}</el-button><span v-if="!reportRowActions(report).length" class="ps-muted">暂无可用操作</span></div>
            </article>
          </div>
          <div v-else-if="!loadError" class="ps-empty-state" role="status">{{ keyword || status ? '暂无匹配报告' : '暂无报告' }}</div>
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
import { Plus, Search } from '@element-plus/icons-vue'
import usePortalStore from '@/store/modules/portal'
import { buildPersonalReports } from '@/utils/portal/personalReports'
import useUserStore from '@/store/modules/user'
import { sortResearchReports } from '../utils/reportList'
import { createResearchRefresh, reportRowActions } from '@/utils/portal/researchWorkspace'
import { listPipelineResearchJobs, listPipelineResearchReports } from '@/api/pipeline/intelligence'

const router = useRouter()
const route = useRoute()
const portalStore = usePortalStore()
const userStore = useUserStore()
const refreshing = ref(false)
const refresher = createResearchRefresh({ store: portalStore, loadJobs: listPipelineResearchJobs,
  loadReports: listPipelineResearchReports, waitForHydration: () => portalStore.hydrate() })
let refreshTimer, disposed = false
function scheduleRefresh() {
  clearTimeout(refreshTimer)
  if (!disposed && typeof document !== 'undefined' && !document.hidden && researchReports.value.some(item => item.status === 'active')) {
    refreshTimer = setTimeout(refreshWorkspace, 5000)
  }
}
async function refreshWorkspace() {
  if (disposed || refreshing.value) return
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
const researchReports = computed(() => buildPersonalReports({ reports: [...portalStore.researchReports, ...portalStore.digestReports], tasks: portalStore.tasks, userId: userStore.id }))
const keyword = ref(String(route.query.q || ''))
const normalizeStatus = value => value === 'completed' ? 'generated' : ['active', 'generated', 'failed', 'cancelled', 'unavailable'].includes(value) ? value : ''
const status = ref(normalizeStatus(route.query.status))
watch(() => route.query, query => { keyword.value = String(query.q || ''); status.value = normalizeStatus(query.status) })
const currentPage = ref(1)
const pageSize = ref(10)
const sort = ref('updated-desc')
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
onBeforeUnmount(() => { disposed = true; clearTimeout(refreshTimer); refresher.stop(); if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', handleVisibility) })
</script>

<style scoped>
.ps-research-toolbar-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.ps-research-toolbar-actions :deep(.el-button) { margin-left: 0; }
.ps-research-workspace .ps-report-main .ps-report-table .ps-table-head, .ps-report-table .ps-report-list-row { display: grid; grid-template-columns: minmax(220px, 1fr) 100px 170px 180px; gap: 14px; align-items: center; }
.ps-research-workspace .ps-report-main .ps-table-head > span { white-space: nowrap; }
.ps-status-pill.is-danger { color: #a63232; background: #fff0f0; }
.ps-status-pill.is-running { color: var(--ps-blue); background: var(--ps-blue-soft); }
.ps-report-list-row { padding: 16px 0; border-top: 1px solid var(--ps-line-soft); font-size: 13px; }
.ps-report-row-title { min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.ps-report-row-title > button { padding: 0; border: 0; background: none; color: var(--ps-ink); font: inherit; font-weight: 600; cursor: pointer; text-align: left; overflow-wrap: anywhere; }
.ps-report-row-title > button:hover { color: var(--ps-blue); }
.ps-report-row-title small { color: var(--ps-muted); }
.ps-report-row-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.ps-report-row-actions :deep(.el-button) { margin: 0; padding: 8px 10px; }
.ps-report-list-row time { white-space: nowrap; }
@media (max-width: 1100px) {
  .ps-report-table .ps-report-list-row { grid-template-columns: minmax(0, 1fr) auto; gap: 10px; }
  .ps-research-workspace .ps-report-main .ps-report-table .ps-table-head { display: none; }
  .ps-report-row-title, .ps-report-row-actions { grid-column: 1 / -1; }
}
@media (min-width: 1051px) {
  .ps-research-toolbar > .el-input { flex: 1 1 180px; }
  .ps-research-toolbar > .el-select { flex: 0 0 130px; width: 130px; }
}
</style>
