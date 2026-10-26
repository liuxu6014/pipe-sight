<template>
  <div class="pipeline-page pipeline-dashboard">
    <section class="page-heading">
      <div>
        <p class="eyebrow">管理端</p>
        <h1>管理首页</h1>
        <p class="summary">查看当前业务状态，定位待处理事项。汇总不是运行健康或行业趋势结论。</p>
      </div>
      <div class="heading-actions">
        <el-button plain :icon="Monitor" @click="$router.push('/portal')">查看用户端</el-button>
        <el-button plain :icon="EditPen" @click="$router.push('/pipeline/manuscript')">论文生成</el-button>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadDashboard">刷新数据</el-button>
      </div>
    </section>

    <el-alert v-if="dashboardError" type="warning" show-icon :closable="false" class="dashboard-load-error">
      <template #title>{{ dashboardError }}</template>
      <template #default><button type="button" class="dashboard-retry" @click="loadDashboard">重新加载</button></template>
    </el-alert>

    <template v-else>

    <el-row :gutter="16" class="metric-grid">
      <el-col v-for="item in dashboard.metrics" :key="item.label" :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="metric-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}{{ item.unit }}</strong>
          <em>当前记录数量 · 非趋势指标</em>
        </el-card>
      </el-col>
    </el-row>

    <section class="management-entry-grid ws-card-grid" aria-label="管理功能入口">
          <button v-for="item in visibleAdminEntries" :key="item.path" type="button" @click="$router.push(item.path)">
        <span><component :is="item.icon" /></span>
        <span><strong>{{ item.title }}</strong><small>{{ item.description }}</small></span>
        <ArrowRight />
      </button>
    </section>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="panel-card">
          <template #header>
            <div class="card-header">
              <span>最近采集任务</span>
              <el-tag type="info" effect="plain">任务进度，不代表数据审核通过</el-tag>
            </div>
          </template>
          <div v-for="item in dashboard.collect_status" :key="item.name" class="status-row">
            <div class="status-copy">
              <strong>{{ item.name }}</strong>
              <el-tag :type="statusType(item.status)" effect="light">{{ statusText(item.status) }}</el-tag>
            </div>
            <el-progress :percentage="item.value" :status="item.status === 'warning' ? 'warning' : undefined" />
          </div>
          <el-empty v-if="!dashboard.collect_status?.length" description="当前没有采集运行记录" :image-size="64" />
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="panel-card">
          <template #header>已展示内容的标签计数</template>
          <div v-for="topic in dashboard.hot_topics" :key="topic.name" class="topic-row">
            <strong>{{ topic.name }}</strong>
            <span>{{ topic.count }} 条</span>
          </div>
          <p class="dashboard-scope-note">按当前可展示内容的标签计数，不代表技术热度或行业趋势。</p>
          <el-empty v-if="!dashboard.hot_topics?.length" description="暂无可统计的已展示标签" :image-size="64" />
        </el-card>
      </el-col>
    </el-row>

    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowRight, Collection, Connection, DataAnalysis, Document, EditPen, MagicStick, Monitor, Refresh, Stamp } from '@element-plus/icons-vue'
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

function statusType(status) {
  return { running: 'primary', success: 'success', warning: 'warning', reviewing: 'warning', draft: 'info', planned: 'primary' }[status] || 'info'
}

function statusText(status) {
  return { running: '运行中', success: '成功', warning: '需关注', reviewing: '审核中', draft: '草稿', planned: '规划中' }[status] || status
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
.heading-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.metric-grid {
  margin-bottom: 2px;
}

.dashboard-load-error {
  margin-bottom: 18px;
}

.dashboard-retry {
  padding: 0;
  border: 0;
  background: transparent;
  color: #2764e7;
  cursor: pointer;
  font-size: 13px;
}

.metric-card {
  min-height: 136px;
  margin-bottom: 16px;
}

.metric-card span,
.metric-card em {
  display: block;
  color: #698092;
  font-size: 13px;
  font-style: normal;
}

.metric-card strong {
  display: block;
  margin: 14px 0 10px;
  color: #173d56;
  font-size: 32px;
}

.management-entry-grid {
  margin: 2px 0 18px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.management-entry-grid button {
  min-height: 82px;
  padding: 15px;
  border: 1px solid #dfe8ee;
  border-radius: 9px;
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) 16px;
  gap: 11px;
  align-items: center;
  background: #fff;
  color: #173d56;
  cursor: pointer;
  text-align: left;
}

.management-entry-grid button:hover {
  border-color: #8db9d2;
  box-shadow: 0 8px 22px rgba(23, 61, 86, .08);
}

.management-entry-grid button > span:first-child {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: #edf6fb;
  color: #287da8;
}

.management-entry-grid button > span:nth-child(2) {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.management-entry-grid svg {
  width: 17px;
}

.management-entry-grid strong {
  font-size: 13px;
}

.management-entry-grid small {
  margin-top: 4px;
  overflow: hidden;
  color: #698092;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .management-entry-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .management-entry-grid {
    grid-template-columns: 1fr;
  }
}

.status-row + .status-row,
.topic-row + .topic-row {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e6edf1;
}

.status-copy,
.topic-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.status-copy {
  margin-bottom: 10px;
}

.topic-row {
  flex-wrap: wrap;
}

.topic-row .el-progress {
  flex: 1 1 100%;
}
</style>
