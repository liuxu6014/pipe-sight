<template>
  <div class="pipeline-page pipeline-dashboard">
    <section class="page-heading">
      <div>
        <p class="eyebrow">后台管理 · 管网项目</p>
        <h1>国家管网科技情报与科研辅助平台工作台</h1>
        <p class="summary">面向管理员汇总采集、研判、审核与报告生成状态；用户端展示入口已移至 /portal。</p>
      </div>
      <div class="heading-actions">
        <el-button plain :icon="Monitor" @click="$router.push('/portal')">查看用户端</el-button>
        <el-button plain :icon="EditPen" @click="$router.push('/pipeline/manuscript')">论文生成</el-button>
        <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadDashboard">刷新数据</el-button>
      </div>
    </section>

    <el-row :gutter="16" class="metric-grid">
      <el-col v-for="item in dashboard.metrics" :key="item.label" :xs="24" :sm="12" :lg="6">
        <el-card shadow="never" class="metric-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}{{ item.unit }}</strong>
          <em>{{ item.trend === 'up' ? '持续提升' : '稳定运行' }}</em>
        </el-card>
      </el-col>
    </el-row>

    <section class="management-entry-grid" aria-label="管理功能入口">
      <button v-for="item in adminEntries" :key="item.path" type="button" @click="$router.push(item.path)">
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
              <span>采集处理链路</span>
              <el-tag type="primary" effect="plain">后台监控</el-tag>
            </div>
          </template>
          <div v-for="item in dashboard.collect_status" :key="item.name" class="status-row">
            <div class="status-copy">
              <strong>{{ item.name }}</strong>
              <el-tag :type="statusType(item.status)" effect="light">{{ statusText(item.status) }}</el-tag>
            </div>
            <el-progress :percentage="item.value" :status="item.status === 'warning' ? 'warning' : undefined" />
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="panel-card">
          <template #header>热点主题</template>
          <div v-for="topic in dashboard.hot_topics" :key="topic.name" class="topic-row">
            <strong>{{ topic.name }}</strong>
            <span>{{ topic.count }} 条</span>
            <el-progress :percentage="topic.heat" :show-text="false" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="panel-card">
      <template #header>
        <div class="card-header">
          <span>待审核报告</span>
          <el-button text type="primary" @click="$router.push('/pipeline/report')">进入报告管理</el-button>
        </div>
      </template>
      <el-table :data="dashboard.pending_reviews" border>
        <el-table-column prop="title" label="报告名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="type" label="类型" width="150" />
        <el-table-column prop="owner" label="责任组" width="150" />
        <el-table-column prop="coverage" label="覆盖资讯" width="120" align="right" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" effect="light">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowRight, Collection, Connection, DataAnalysis, Document, EditPen, MagicStick, Monitor, Refresh } from '@element-plus/icons-vue'
import { getPipelineDashboard } from '@/api/pipeline/intelligence'

defineOptions({ name: 'PipelineDashboard' })

const loading = ref(false)
const dashboard = ref({ metrics: [], collect_status: [], hot_topics: [], pending_reviews: [] })
const adminEntries = [
  { title: '数据源管理', description: '维护网站、公众号和论文来源', path: '/pipeline/source', icon: Connection },
  { title: '采集任务', description: '调度采集、清洗和解析任务', path: '/pipeline/task', icon: DataAnalysis },
  { title: '数据治理', description: '处理重复、缺失和质量异常', path: '/pipeline/governance', icon: Collection },
  { title: '模板管理', description: '维护报告模板和版本结构', path: '/pipeline/template', icon: Document },
  { title: '模型与 Prompt', description: '配置模型路由和提示词版本', path: '/pipeline/model', icon: MagicStick },
  { title: '报告与导出', description: '审核报告并跟踪导出任务', path: '/pipeline/report', icon: EditPen }
]

function statusType(status) {
  return { running: 'primary', success: 'success', warning: 'warning', reviewing: 'warning', draft: 'info', planned: 'primary' }[status] || 'info'
}

function statusText(status) {
  return { running: '运行中', success: '成功', warning: '需关注', reviewing: '审核中', draft: '草稿', planned: '规划中' }[status] || status
}

async function loadDashboard() {
  loading.value = true
  try {
    const res = await getPipelineDashboard()
    dashboard.value = res.data
  } catch (error) {
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
  font-size: 10px;
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
