<template>
  <div class="pipeline-page">
    <section class="page-heading">
      <div>
        <p class="eyebrow">后台管理 · 数据采集</p>
        <h1>数据源管理</h1>
        <p class="summary">维护新闻源、公众号、论文库等采集入口，为后续清洗、去重和标签生成提供来源配置。</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="showSourceTodo">新增数据源</el-button>
    </section>

    <el-row :gutter="16" class="source-stats">
      <el-col :xs="24" :sm="8">
        <el-card shadow="never" class="stat-card">
          <span>启用数据源</span>
          <strong>{{ enabledCount }}</strong>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="never" class="stat-card">
          <span>平均成功率</span>
          <strong>{{ averageSuccessRate }}%</strong>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="never" class="stat-card">
          <span>来源类型</span>
          <strong>{{ typeCount }}</strong>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="rows" border>
        <el-table-column prop="name" label="数据源" min-width="180" />
        <el-table-column prop="type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="typeTag(row.type)" effect="light">{{ typeText(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="frequency" label="频率" width="120" />
        <el-table-column prop="last_run_time" label="最后采集" width="180" />
        <el-table-column prop="success_rate" label="成功率" min-width="160">
          <template #default="{ row }">
            <el-progress :percentage="row.success_rate" />
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'enabled' ? 'success' : 'info'">
              {{ row.status === 'enabled' ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default>
            <el-button link type="primary" :icon="Edit" @click="showSourceTodo">配置</el-button>
            <el-button link type="primary" :icon="VideoPlay" @click="showSourceTodo">试运行</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Edit, Plus, VideoPlay } from '@element-plus/icons-vue'
import { listPipelineSources } from '@/api/pipeline/intelligence'

defineOptions({ name: 'PipelineSource' })

const loading = ref(false)
const rows = ref([])

const enabledCount = computed(() => rows.value.filter(item => item.status === 'enabled').length)
const typeCount = computed(() => new Set(rows.value.map(item => item.type)).size)
const averageSuccessRate = computed(() => {
  if (!rows.value.length) return 0
  const total = rows.value.reduce((sum, item) => sum + item.success_rate, 0)
  return Math.round(total / rows.value.length)
})

function typeText(type) {
  return { news: '新闻源', wechat: '公众号', paper: '论文库' }[type] || type
}

function typeTag(type) {
  return { news: 'primary', wechat: 'success', paper: 'warning' }[type] || 'info'
}

async function loadSources() {
  loading.value = true
  try {
    const res = await listPipelineSources()
    rows.value = res.data.rows
  } catch (error) {
    ElMessage.warning('暂时无法获取数据源列表')
  } finally {
    loading.value = false
  }
}

function showSourceTodo() {
  ElMessage.info('数据源新增、配置和试运行将在下一阶段接入')
}

onMounted(loadSources)
</script>

<style scoped>
.source-stats {
  margin-bottom: 2px;
}

.stat-card span {
  color: #698092;
  font-size: 13px;
}

.stat-card strong {
  display: block;
  margin-top: 12px;
  color: #173d56;
  font-size: 31px;
}
</style>
