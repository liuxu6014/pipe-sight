<template>
  <div class="pipeline-page pipeline-report-page ws-list-page">
    <el-card shadow="never" class="panel-card report-filter-card">
      <div class="report-management-filters">
        <el-input v-model.trim="keyword" clearable aria-label="查询成果名称或作者" placeholder="查询成果名称或作者" />
        <el-select v-model="statusFilter" clearable aria-label="成果业务状态" placeholder="全部业务状态"><el-option v-for="value in statusOptions" :key="value" :value="value" :label="getReportStatusMeta(value).label" /></el-select>
        <el-button v-if="keyword || statusFilter" @click="keyword = ''; statusFilter = ''">清除筛选</el-button>
        <span class="report-management-scope" aria-live="polite">共 {{ filteredRows.length }} 份</span>
        <div v-if="reportKind !== 'digest'" class="heading-actions">
          <el-button plain :icon="DocumentAdd" @click="openCreate('科研需求报告')">进入用户端编制</el-button>
          <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadReports">刷新列表</el-button>
        </div>
      </div>
    </el-card>
    <el-alert v-if="reportError" type="warning" show-icon :closable="false" class="report-load-error">
      <template #title>{{ reportError }}</template><template #default><el-button class="ps-ui-action report-retry" @click="loadReports">重新加载</el-button></template>
    </el-alert>
    <el-card v-else shadow="never" class="panel-card report-list-card ws-list-panel">
      <div ref="listRegion" v-loading="loading" :aria-busy="loading" class="ws-list-scroll report-list-grid" tabindex="0" aria-label="成果列表滚动区">
        <div class="report-list-header">
          <span>序号</span>
          <span>{{ reportKind === 'digest' ? '简报信息' : '报告信息' }}</span>
          <span>操作</span>
        </div>
        <ol v-if="pagedRows.length" :start="pageOffset + 1" class="report-list" role="list" :aria-label="reportKind === 'digest' ? '简报列表' : '报告列表'">
          <li v-for="(row, index) in pagedRows" :key="row.id" class="report-list-item">
            <span class="report-list-index">{{ pageOffset + index + 1 }}</span>
            <div class="report-list-main" :class="{ 'is-centered': reportKind === 'research' }">
              <h2>{{ row.title }}</h2>
              <div class="report-list-meta">
                <el-tag :type="getReportStatusMeta(row.status).type" effect="light" size="small">{{ getReportStatusMeta(row.status).label }}</el-tag>
                <span>{{ reportTypeLabel(row.reportType || row.type) }}</span>
                <span v-if="row.owner">作者 {{ row.owner }}</span>
                <span v-if="reportKind === 'digest' && reportPeriod(row)">覆盖周期 {{ reportPeriod(row) }}</span>
                <span v-if="row.updated_at || row.updatedAt">更新于 {{ row.updated_at || row.updatedAt }}</span>
              </div>
            </div>
            <div class="report-list-actions">
              <el-button plain type="primary" :icon="Edit" @click="openReport(row)">查看 / 核对</el-button>
              <el-button v-hasPermi="['pipeline:report:export']" plain type="primary" :icon="Download" :loading="downloadingReportId === row.id" @click="handleExportReport(row)">导出</el-button>
            </div>
          </li>
        </ol>
        <el-empty v-else-if="!loading" description="当前条件下暂无成果" />
      </div>
      <pagination
        v-if="filteredRows.length"
        v-model:page="page"
        v-model:limit="pageSize"
        :total="filteredRows.length"
        :auto-scroll="false"
        class="report-list-pagination"
      />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { DocumentAdd, Download, Edit, Refresh } from '@element-plus/icons-vue'
import { exportPipelineReport, listPipelineAdminReports } from '@/api/pipeline/intelligence'
import { getReportStatusMeta } from '@/utils/pipeline/reportPresentation'
import { getPortalReportPath, isDigestType } from '@/views/portal/utils/routing'

defineOptions({ name: 'PipelineReport' })

const router = useRouter()
const route = useRoute()
const reportKind = computed(() => route.path === '/pipeline/digest' ? 'digest' : 'research')
const keyword = ref('')
const statusFilter = ref('')
const statusOptions = computed(() => [...new Set(rows.value.map(item => item.status).filter(Boolean))])
const filteredRows = computed(() => rows.value.filter(item => {
  const digest = isDigestType(item.reportType || item.type)
  return (reportKind.value === 'digest' ? digest : !digest)
    && (!statusFilter.value || item.status === statusFilter.value)
    && (!keyword.value || [item.title, item.owner].filter(Boolean).join(' ').toLocaleLowerCase().includes(keyword.value.toLocaleLowerCase()))
}))
const loading = ref(false)
const reportError = ref('')
const downloadingReportId = ref('')
const rows = ref([])
const listRegion = ref(null)
const page = ref(1)
const pageSize = ref(10)
const pageOffset = computed(() => (page.value - 1) * pageSize.value)
const pagedRows = computed(() => filteredRows.value.slice(pageOffset.value, pageOffset.value + pageSize.value))

watch([keyword, statusFilter, reportKind, pageSize], () => {
  page.value = 1
}, { flush: 'sync' })

watch(() => filteredRows.value.length, total => {
  page.value = Math.min(page.value, Math.max(1, Math.ceil(total / pageSize.value)))
})

watch([page, pageSize, keyword, statusFilter, reportKind], () => {
  if (listRegion.value) listRegion.value.scrollTop = 0
}, { flush: 'post' })

const reportTypeLabels = {
  research: '科研报告',
  'research-demand': '科研需求报告',
  'technology-route': '技术路线报告',
  'project-demand': '科技项目需求表',
  daily: '日报',
  weekly: '周报',
  monthly: '月报'
}
function reportTypeLabel(type) {
  return reportTypeLabels[type] || type || (reportKind.value === 'digest' ? '情报简报' : '科研报告')
}
function reportPeriod(row) {
  const period = row.period || row.metadata?.period
  return Array.isArray(period) ? period.join(' 至 ') : period
}
async function loadReports() {
  loading.value = true
  reportError.value = ''
  try {
    const res = await listPipelineAdminReports()
    rows.value = res.data.rows
  } catch (error) {
    rows.value = []
    reportError.value = error?.msg || '报告列表暂时无法加载，请检查服务后重试'
    ElMessage.warning(reportError.value)
  } finally {
    loading.value = false
  }
}

function downloadMarkdown(fileName, content) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName || '管网科技情报报告.md'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

async function handleExportReport(row) {
  if (!row) return
  downloadingReportId.value = row.id
  try {
    const res = await exportPipelineReport(row.id, { allowDraft: row.requiresReview })
    downloadMarkdown(res.data.file_name, res.data.content)
    ElMessage.success(res.data.isDraft ? '草稿已导出' : '报告已导出')
  } catch (error) {
    ElMessage.warning('报告导出失败，请稍后重试')
  } finally {
    downloadingReportId.value = ''
  }
}

function openReport(row) {
  if (!row?.id) return ElMessage.warning('当前报告缺少有效编号，暂时无法打开编辑器')
  router.push(getPortalReportPath({ id: row.id, reportType: row.reportType || row.type }))
}
function openCreate(title) {
  if (title.includes('月报')) return router.push({ path: '/portal/digests/create', query: { type: '月报' } })
  if (title.includes('周报')) return router.push({ path: '/portal/digests/create', query: { type: '周报' } })
  router.push('/portal/research/create')
}

onMounted(loadReports)
</script>

<style scoped>
.pipeline-report-page .report-filter-card { margin-bottom: 14px; }
.pipeline-report-page .report-filter-card :deep(.el-card__body) { padding: 14px 16px; }
.report-list-card :deep(.el-card__body) { padding: 0; }
.report-list-grid {
  --report-list-inset: 20px;
  display: grid;
  grid-template-columns: calc(32px + var(--report-list-inset)) minmax(0, 1fr) max-content;
  column-gap: 16px;
  align-content: start;
}
.report-list-grid > *,
.report-list-item { grid-column: 1 / -1; }
.report-list-header,
.report-list,
.report-list-item {
  display: grid;
  grid-template-columns: subgrid;
}
.report-list { margin: 0; padding: 0; list-style: none; }
.report-list-header,
.report-list-item {
  align-items: center;
  padding-block: 14px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.report-list-header {
  position: sticky;
  top: 0;
  z-index: 1;
  padding-block: 10px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  font-size: 13px;
  font-weight: 600;
  line-height: 20px;
  white-space: nowrap;
}
.report-list-header > :first-child,
.report-list-index { margin-inline-start: var(--report-list-inset); text-align: center; }
.report-list-header > :last-child,
.report-list-actions { margin-inline-end: var(--report-list-inset); }
.report-list-header > :last-child { text-align: center; }
.report-list-item:last-child { border-bottom: 0; }
.report-list-index { color: var(--el-text-color-secondary); font-size: 13px; font-variant-numeric: tabular-nums; }
.report-list-main { min-width: 0; overflow-wrap: anywhere; }
.report-list-main h2 { margin: 0; color: var(--el-text-color-primary); font-size: 16px; font-weight: 600; line-height: 1.5; }
.report-list-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin-top: 6px; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.6; }
.report-list-actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }
.report-list-actions .el-button { margin: 0; }
.report-list-card .report-list-pagination { padding-inline: 16px; border-top: 1px solid var(--el-border-color-lighter); }
.report-list-pagination :deep(.el-pagination) { flex-wrap: wrap; justify-content: flex-end; }
.heading-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.heading-actions .el-button { margin: 0; }
.report-load-error { margin: 18px 0; }
.report-retry { padding: 0; border: 0; background: transparent; color: #409eff; cursor: pointer; font-size: 13px; }
.report-management-filters { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }
.report-management-filters .el-input { flex: 1 1 260px; }
.report-management-filters .el-select { flex: 0 1 180px; }
.report-management-scope { margin: 0; color: #526277; font-size: 13px; white-space: nowrap; }
@media (width > 640px) {
  .report-list-header > :nth-child(2),
  .report-list-main.is-centered { text-align: center; }
  .report-list-main.is-centered .report-list-meta { justify-content: center; }
  .report-list-main:not(.is-centered) { padding-inline-start: clamp(24px, 12%, 112px); }
}
@media (max-width: 640px) {
  .report-list-grid {
    --report-list-inset: 14px;
    grid-template-columns: calc(24px + var(--report-list-inset)) minmax(0, 1fr);
    column-gap: 12px;
  }
  .report-list-header,
  .report-list-item { align-items: start; row-gap: 8px; }
  .report-list-header { font-size: 12px; }
  .report-list-header > :last-child { display: none; }
  .report-list-main { margin-inline-end: var(--report-list-inset); }
  .report-list-index { line-height: 24px; }
  .report-list-actions { grid-column: 2; justify-content: flex-start; }
  .report-list-pagination :deep(.el-pagination__jump) { display: none; }
  .report-management-filters > * { flex: 1 1 100%; min-width: 0; }
  .heading-actions { width: 100%; }
}
</style>
