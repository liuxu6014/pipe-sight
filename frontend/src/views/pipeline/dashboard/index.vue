<template>
  <div class="pipeline-page pipeline-dashboard">
    <el-alert v-if="dashboardError" type="warning" show-icon :closable="false" class="dashboard-load-error">
      <template #title>{{ dashboardError }}</template>
      <template #default><el-button plain @click="loadDashboard">重新加载</el-button></template>
    </el-alert>
    <el-skeleton v-else-if="loading && !dashboard.metrics.length" :rows="8" animated />
    <template v-else>
      <section class="metric-grid" aria-label="内容总览">
        <el-card v-for="item in dashboard.metrics" :key="item.label" shadow="never" class="metric-card">
          <el-icon class="metric-icon" aria-hidden="true"><component :is="metricIcon(item.label)" /></el-icon>
          <el-statistic :title="item.label" :value="item.value"><template #suffix><span class="metric-unit">{{ item.unit }}</span></template></el-statistic>
        </el-card>
      </section>

      <el-card v-if="visibleAdminEntries.length" shadow="never" class="dashboard-shortcuts">
        <template #header><h2>常用管理</h2></template>
        <section class="management-entry-grid" aria-label="管理功能入口">
          <el-button v-for="item in visibleAdminEntries" :key="item.path" :auto-insert-space="false" class="management-entry" @click="$router.push(item.path)">
            <el-icon class="entry-icon" aria-hidden="true"><component :is="item.icon" /></el-icon>
            <span class="entry-copy"><strong>{{ item.title }}</strong><small>{{ item.description }}</small></span>
            <el-icon class="entry-arrow" aria-hidden="true"><ArrowRight /></el-icon>
          </el-button>
        </section>
      </el-card>

      <div class="dashboard-details">
        <el-card shadow="never" class="panel-card collection-panel">
          <template #header><div class="card-header"><h2>最近采集任务</h2><el-button v-if="checkPermi(['pipeline:task:list'])" plain @click="$router.push('/pipeline/task')">全部任务<el-icon class="button-arrow"><ArrowRight /></el-icon></el-button></div></template>
          <el-table v-if="dashboard.collect_status?.length" :data="dashboard.collect_status" row-key="id" max-height="420" class="collection-table">
            <el-table-column label="数据源" min-width="200" header-align="center"><template #default="{ row: item }"><span class="collection-name">{{ item.name }}</span></template></el-table-column>
            <el-table-column label="状态" width="100" align="center"><template #default="{ row: item }"><el-tag :type="statusType(item.status)">{{ statusText(item.status) }}</el-tag></template></el-table-column>
            <el-table-column label="读取" width="90" align="center"><template #default="{ row: item }">{{ item.fetched_count ?? '—' }}</template></el-table-column>
            <el-table-column label="保存" width="90" align="center"><template #default="{ row: item }">{{ item.saved_count ?? '—' }}</template></el-table-column>
            <el-table-column label="失败" width="90" align="center"><template #default="{ row: item }"><span :class="{ 'failed-count': item.failed_count > 0 }">{{ item.failed_count ?? '—' }}</span></template></el-table-column>
          </el-table>
          <el-empty v-else description="暂无采集任务" :image-size="64"><p class="empty-description">采集运行后，将在这里显示状态与入库数量。</p><el-button v-if="checkPermi(['pipeline:source:list'])" type="primary" plain @click="$router.push('/pipeline/source')">管理数据源</el-button></el-empty>
        </el-card>

        <el-card shadow="never" class="panel-card category-panel">
          <template #header><div class="card-header"><h2>内容分类</h2><el-tooltip content="按新闻和论文的类别汇总数量，最多展示前 6 类。" placement="top"><el-icon class="scope-info" tabindex="0" aria-label="分类统计口径"><InfoFilled /></el-icon></el-tooltip></div></template>
          <div v-if="dashboard.hot_topics?.length" class="category-list">
            <div class="category-list-heading"><span>类别</span><span>文章数量</span></div>
            <div v-for="topic in dashboard.hot_topics" :key="topic.name" class="topic-row"><el-tag effect="plain">{{ topic.name }}</el-tag><span><strong>{{ topic.count }}</strong> 条</span></div>
          </div>
          <el-empty v-else description="暂无分类统计" :image-size="64"><p class="empty-description">新闻和论文完成分类后显示统计结果。</p><el-button v-if="checkPermi(['ai:model:list'])" plain @click="$router.push('/pipeline/model')">配置类别提示词</el-button></el-empty>
        </el-card>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowRight, Collection, Connection, DataAnalysis, Document, EditPen, MagicStick, InfoFilled, Reading } from '@element-plus/icons-vue'
import { getPipelineDashboard } from '@/api/pipeline/intelligence'
import { checkPermi } from '@/utils/permission'

defineOptions({ name: 'PipelineDashboard' })

const loading = ref(false)
const dashboardError = ref('')
const dashboard = ref({ metrics: [], collect_status: [], hot_topics: [] })
const adminEntries = [
  { title: '数据源管理', description: '维护网站、公众号和论文来源', path: '/pipeline/source', permission: 'pipeline:source:list', icon: Connection },
  { title: '采集任务', description: '调度采集、清洗和解析任务', path: '/pipeline/task', permission: 'pipeline:task:list', icon: DataAnalysis },
  { title: '模板管理', description: '维护提示词、章节和生成模型', path: '/pipeline/template', permission: 'pipeline:template:list', icon: Document },
  { title: '模型与类别提示词', description: '配置模型能力、类别及提示词', path: '/pipeline/model', permission: 'ai:model:list', icon: MagicStick },
  { title: '报告与导出', description: '编辑报告并跟踪导出任务', path: '/pipeline/report', permission: 'pipeline:report:list', icon: EditPen }
]
const visibleAdminEntries = computed(() => adminEntries.filter(item => checkPermi([item.permission])))

function metricIcon(label) { return /论文/.test(label) ? Reading : /资料/.test(label) ? Collection : Document }

function statusType(status) {
  return { queued: 'info', running: 'primary', stopping: 'warning', success: 'success', failed: 'danger', cancelled: 'info' }[status] || 'info'
}

function statusText(status) {
  return { queued: '排队中', running: '运行中', stopping: '停止中', success: '成功', failed: '失败', cancelled: '已取消' }[status] || status
}

async function loadDashboard() {
  loading.value = true
  dashboardError.value = ''
  try {
    const res = await getPipelineDashboard()
    dashboard.value = res.data
  } catch (error) {
    dashboard.value = { metrics: [], collect_status: [], hot_topics: [] }
    dashboardError.value = error?.msg || '工作台数据暂时无法加载，请检查服务后重试'
    ElMessage.warning('暂时无法获取管网情报工作台数据')
  } finally {
    loading.value = false
  }
}

onMounted(loadDashboard)
</script>

<style scoped>
:global(.ps-workspace-surface > .pipeline-dashboard),
:global(.ps-management-shell .ps-workspace-surface > .pipeline-dashboard) {
  width: 100%; max-width: none; padding: 20px 24px 28px; margin: 0;
}
.pipeline-dashboard { display: flex; flex-direction: column; gap: 16px; }
.metric-grid { display: flex; gap: 16px; }
.metric-card { flex: 1 1 0; min-width: 0; margin: 0; }
.metric-card :deep(.el-card__body) { display: flex; align-items: center; gap: 12px; padding: 18px; }
.metric-card :deep(.el-statistic) { min-width: 0; }
.metric-icon { flex: 0 0 48px; height: 48px; border-radius: 12px; background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-size: 24px; }
.metric-card :deep(.el-statistic__head) { margin-bottom: 6px; color: var(--el-text-color-regular); font-size: 14px; }
.metric-card :deep(.el-statistic__content) { color: var(--el-text-color-primary); font-size: 30px; font-weight: 600; font-variant-numeric: tabular-nums; }
.metric-unit { margin-left: 4px; color: var(--el-text-color-secondary); font-size: 13px; font-weight: 400; }
.pipeline-dashboard h2 { margin: 0; font-size: 16px; font-weight: 600; }
.pipeline-dashboard :deep(.el-card__header) { min-height: 52px; padding: 12px 16px; }
.dashboard-shortcuts { border-radius: 10px; }
.dashboard-shortcuts :deep(.el-card__body) { padding: 12px; }
.management-entry-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 210px), 1fr)); gap: 10px; }
.management-entry.el-button { width: 100%; min-width: 0; height: auto; margin: 0; padding: 14px 12px; text-align: left; white-space: normal; }
.management-entry :deep(> span) { display: flex; align-items: center; width: 100%; min-width: 0; gap: 10px; }
.entry-icon { flex: 0 0 36px; height: 36px; border-radius: 8px; background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-size: 19px; }
.entry-copy { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 5px; line-height: 1.5; }
.entry-copy strong { color: var(--el-text-color-primary); font-size: 14px; font-weight: 600; }
.entry-copy small { color: var(--el-text-color-secondary); font-size: 12px; overflow-wrap: anywhere; }
.entry-arrow { flex-shrink: 0; color: var(--el-text-color-secondary); }
.dashboard-details { display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(280px, 1fr); align-items: stretch; gap: 16px; }
.dashboard-details > .el-card { min-width: 0; margin: 0; }
.collection-panel :deep(.el-card__body) { padding: 0 16px 12px; }
.category-panel :deep(.el-card__body) { padding: 0 16px 12px; }
.card-header { min-width: 0; gap: 8px; }
.button-arrow { margin-left: 6px; }
.scope-info { color: var(--el-text-color-secondary); cursor: help; }
.collection-table { width: 100%; }
.collection-table :deep(.el-table__cell) { padding-block: 12px; }
.collection-name { color: var(--el-text-color-primary); font-weight: 500; overflow-wrap: anywhere; }
.failed-count { color: var(--el-color-danger); font-weight: 600; }
.category-list-heading, .topic-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 13px 0; }
.category-list-heading { color: var(--el-text-color-secondary); font-size: 12px; }
.topic-row { min-height: 52px; border-top: 1px solid var(--el-border-color-lighter); }
.topic-row > span:not(.el-tag) { flex-shrink: 0; color: var(--el-text-color-secondary); font-size: 12px; }
.topic-row strong { margin-right: 4px; color: var(--el-text-color-primary); font-size: 16px; font-variant-numeric: tabular-nums; }
.topic-row :deep(.el-tag) { max-width: 80%; height: auto; min-height: 26px; padding: 3px 8px; line-height: 18px; white-space: normal; overflow-wrap: anywhere; }
.pipeline-dashboard :deep(.el-empty) { padding: 30px 12px 24px; }
.pipeline-dashboard :deep(.el-empty__bottom) { margin-top: 10px; text-align: center; }
.empty-description { margin: 0 0 14px; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.6; }
@media (max-width: 1100px) { .dashboard-details { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 900px) {
  .metric-grid { gap: 12px; }
  .metric-card :deep(.el-card__body) { padding: 14px; gap: 10px; }
  .metric-icon { flex-basis: 36px; height: 36px; border-radius: 8px; font-size: 20px; }
}
@media (max-width: 600px) {
  :global(.ps-workspace-surface > .pipeline-dashboard), :global(.ps-management-shell .ps-workspace-surface > .pipeline-dashboard) { padding: 14px 12px 24px; }
  .pipeline-dashboard { gap: 12px; }
  .metric-grid { gap: 8px; }
  .metric-card :deep(.el-card__body) { flex-direction: column; align-items: flex-start; padding: 12px 10px; gap: 8px; }
  .metric-icon { flex-basis: auto; width: 28px; height: 28px; font-size: 17px; }
  .metric-card :deep(.el-statistic__head) { font-size: 13px; }
  .metric-card :deep(.el-statistic__content) { font-size: 24px; flex-wrap: wrap; }
}
</style>
