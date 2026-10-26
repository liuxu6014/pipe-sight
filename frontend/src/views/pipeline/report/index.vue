<template>
  <div class="pipeline-page pipeline-report-page">
    <section class="page-heading">
      <div><h1>{{ reportKind === 'digest' ? '简报管理' : '报告管理' }}</h1></div>
      <div class="heading-actions"><el-button plain :icon="DocumentAdd" @click="openCreate(reportKind === 'digest' ? '科技情报日报' : '科研需求报告')">进入用户端编制</el-button><el-button type="primary" :icon="Refresh" :loading="loading" @click="loadReports">刷新列表</el-button></div>
    </section>
    <el-card shadow="never" class="panel-card report-filter-card">
      <div class="report-management-filters">
        <el-input v-model.trim="keyword" clearable aria-label="查询成果名称或作者" placeholder="查询成果名称或作者" />
        <el-select v-model="statusFilter" clearable aria-label="成果业务状态" placeholder="全部业务状态"><el-option v-for="value in statusOptions" :key="value" :value="value" :label="getReportStatusMeta(value).label" /></el-select>
        <el-button v-if="keyword || statusFilter" @click="keyword = ''; statusFilter = ''">清除筛选</el-button>
        <span class="report-management-scope" aria-live="polite">共 {{ filteredRows.length }} 份</span>
      </div>
    </el-card>
    <el-alert v-if="reportError" type="warning" show-icon :closable="false" class="report-load-error">
      <template #title>{{ reportError }}</template><template #default><button type="button" class="report-retry" @click="loadReports">重新加载</button></template>
    </el-alert>
    <el-card v-else shadow="never" class="table-card report-review-table">
      <el-table v-loading="loading" :data="filteredRows" row-key="id" border empty-text="当前条件下暂无成果">
        <el-table-column prop="title" label="成果名称" :min-width="reportKind === 'digest' ? 200 : 260" show-overflow-tooltip />
        <el-table-column prop="type" label="材料类型" :width="reportKind === 'digest' ? 90 : 160" show-overflow-tooltip />
        <el-table-column prop="owner" label="作者" :width="reportKind === 'digest' ? 80 : 140" show-overflow-tooltip />
        <el-table-column v-if="reportKind === 'digest'" prop="period" label="覆盖周期" min-width="140" />
        <el-table-column prop="version" label="版本" :width="reportKind === 'digest' ? 65 : 100" />
        <el-table-column prop="status" label="业务状态" :width="reportKind === 'digest' ? 105 : 120"><template #default="{ row }"><el-tag :type="getReportStatusMeta(row.status).type" effect="light">{{ getReportStatusMeta(row.status).label }}</el-tag></template></el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="180" />
        <el-table-column label="操作" :width="reportKind === 'digest' ? 210 : 250" :fixed="reportKind === 'digest' ? false : 'right'"><template #default="{ row }">
          <el-button link type="primary" :icon="Edit" @click="openReport(row)">查看 / 核对</el-button>
          <el-button v-hasPermi="['pipeline:report:export']" link type="primary" :icon="Download" :loading="downloadingReportId === row.id" @click="handleExportReport(row)">导出</el-button>
        </template></el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { DocumentAdd, Download, Edit, Refresh } from '@element-plus/icons-vue'
import { exportPipelineReport, listPipelineReports } from '@/api/pipeline/intelligence'
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
async function loadReports() {
  loading.value = true
  reportError.value = ''
  try {
    const res = await listPipelineReports()
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
  if (title.includes('日报')) return router.push({ path: '/portal/digests/create', query: { type: '日报' } })
  if (title.includes('月报')) return router.push({ path: '/portal/digests/create', query: { type: '月报' } })
  if (title.includes('周报')) return router.push({ path: '/portal/digests/create', query: { type: '周报' } })
  router.push('/portal/research/create')
}

onMounted(loadReports)
</script>

<style scoped>
.pipeline-report-page .page-heading { padding-bottom: 16px; margin-bottom: 16px; }
.pipeline-report-page .page-heading h1 { margin: 0; }
.pipeline-report-page .report-filter-card { margin-bottom: 14px; }
.pipeline-report-page .report-filter-card :deep(.el-card__body) { padding: 14px 16px; }
.pipeline-report-page .report-review-table { width: 100%; margin: 0; padding: 0; box-shadow: none; }
.pipeline-report-page .report-review-table :deep(.el-card__body) { padding: 16px; }
.pipeline-report-page .report-review-table :deep(.el-table__empty-block) { min-height: 140px; }
.heading-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.report-load-error { margin: 18px 0; }
.report-retry { padding: 0; border: 0; background: transparent; color: #005487; cursor: pointer; font-size: 13px; }
.report-management-filters { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }
.report-management-filters .el-input { flex: 1 1 260px; }
.report-management-filters .el-select { flex: 0 1 180px; }
.report-management-scope { margin: 0; color: #526277; font-size: 13px; white-space: nowrap; }
@media (max-width: 640px) {
  .report-management-filters > * { flex: 1 1 100%; min-width: 0; }
  .heading-actions { width: 100%; }
}
</style>
