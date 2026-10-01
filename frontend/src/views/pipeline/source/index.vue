<template>
  <div class="pipeline-page">
    <section class="page-heading">
      <div>
        <p class="eyebrow">后台管理 · 数据采集</p>
        <h1>数据源管理</h1>
        <p class="summary">维护新闻源、公众号、论文库等采集入口，为后续清洗、去重和标签生成提供来源配置。</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openSourceDialog()">新增数据源</el-button>
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
            <el-button link type="primary" :icon="Edit" @click="openSourceDialog(row)">配置</el-button>
            <el-button link type="primary" :icon="VideoPlay" @click="runSource(row)">试运行</el-button>
            <el-button link :type="row.enabled ? 'danger' : 'success'" @click="toggleSource(row)">{{ row.enabled ? '停用' : '启用' }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingSource ? '配置数据源' : '新增数据源'" width="620px" destroy-on-close>
      <el-form label-position="top" :model="sourceForm">
        <div class="source-form-grid">
          <el-form-item label="数据源名称"><el-input v-model="sourceForm.name" placeholder="例如：国家管网集团要闻" /></el-form-item>
          <el-form-item label="数据源编码"><el-input v-model="sourceForm.sourceCode" placeholder="小写字母、数字、短横线或下划线" :disabled="Boolean(editingSource)" /></el-form-item>
          <el-form-item label="来源类型"><el-select v-model="sourceForm.sourceType"><el-option label="新闻源" value="news" /><el-option label="公众号" value="wechat" /><el-option label="论文库" value="paper" /></el-select></el-form-item>
          <el-form-item label="采集适配器"><el-select v-model="sourceForm.adapterKey"><el-option label="国家管网资讯" value="pipechina_group_news" /><el-option label="Crossref 论文" value="crossref_works" /></el-select></el-form-item>
          <el-form-item label="入口地址" class="is-full"><el-input v-model="sourceForm.endpoint" placeholder="https://..." /></el-form-item>
          <el-form-item label="调度表达式"><el-input v-model="sourceForm.scheduleCron" placeholder="留空表示仅手动运行" /></el-form-item>
          <el-form-item label="外部处理模式"><el-select v-model="sourceForm.handoffMode"><el-option label="本地入库" value="local" /><el-option label="提交 InsightHub" value="external" /></el-select></el-form-item>
          <el-form-item label="外部来源编码"><el-input v-model="sourceForm.processorSourceCode" placeholder="可选，用于外部处理系统匹配" /></el-form-item>
          <el-form-item label="单次抓取上限"><el-input-number v-model="sourceForm.limit" :min="1" :max="30" /></el-form-item>
          <el-form-item v-if="sourceForm.adapterKey === 'crossref_works'" label="论文检索词" class="is-full"><el-input v-model="sourceForm.query" placeholder="例如：oil gas pipeline integrity monitoring" /></el-form-item>
        </div>
        <el-alert title="试运行会真实访问入口并写入采集运行记录；外部处理模式需要先配置 InsightHub 连接。" type="info" :closable="false" />
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveSource">保存配置</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Edit, Plus, VideoPlay } from '@element-plus/icons-vue'
import { createPipelineSource, disablePipelineSource, listPipelineSources, runPipelineTask, updatePipelineSource } from '@/api/pipeline/intelligence'

defineOptions({ name: 'PipelineSource' })

const loading = ref(false)
const rows = ref([])
const dialogVisible = ref(false)
const saving = ref(false)
const editingSource = ref(null)
const sourceForm = reactive({
  sourceCode: '', name: '', sourceType: 'news', adapterKey: 'pipechina_group_news', endpoint: '',
  scheduleCron: '', handoffMode: 'external', processorSourceCode: '', limit: 12, query: ''
})

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

function resetForm(source = null) {
  editingSource.value = source
  Object.assign(sourceForm, {
    sourceCode: source?.source_code || '',
    name: source?.name || '',
    sourceType: source?.type || 'news',
    adapterKey: source?.adapter_key || 'pipechina_group_news',
    endpoint: source?.endpoint || '',
    scheduleCron: source?.schedule_cron || '',
    handoffMode: source?.handoff_mode || 'external',
    processorSourceCode: source?.processor_source_code || '',
    limit: Number(source?.config_json?.limit || 12),
    query: source?.config_json?.query || ''
  })
}

function openSourceDialog(source = null) {
  resetForm(source)
  dialogVisible.value = true
}

function sourcePayload(source = sourceForm) {
  return {
    sourceCode: source.sourceCode || source.source_code,
    name: source.name,
    sourceType: source.sourceType || source.type,
    endpoint: source.endpoint || '',
    adapterKey: source.adapterKey || source.adapter_key,
    scheduleCron: source.scheduleCron || source.schedule_cron || '',
    enabled: source.enabled !== false,
    configJson: { ...(source.config_json || {}), limit: Number(source.limit || source.config_json?.limit || 12), ...(source.query || source.config_json?.query ? { query: source.query || source.config_json.query } : {}) },
    handoffMode: source.handoffMode || source.handoff_mode || 'external',
    processorSourceCode: source.processorSourceCode || source.processor_source_code || ''
  }
}

async function saveSource() {
  if (saving.value) return
  if (!sourceForm.name || !sourceForm.sourceCode || !sourceForm.endpoint) return ElMessage.warning('请填写名称、编码和入口地址')
  saving.value = true
  try {
    const payload = sourcePayload()
    if (editingSource.value) await updatePipelineSource(editingSource.value.id, payload)
    else await createPipelineSource(payload)
    dialogVisible.value = false
    ElMessage.success(editingSource.value ? '数据源配置已更新' : '数据源已创建')
    await loadSources()
  } catch (error) {
    ElMessage.error(error?.msg || '数据源保存失败')
  } finally {
    saving.value = false
  }
}

async function toggleSource(source) {
  const enabled = source.enabled
  try {
    if (enabled) await updatePipelineSource(source.id, sourcePayload(source))
    else await disablePipelineSource(source.id)
    ElMessage.success(enabled ? '数据源已启用' : '数据源已停用')
    await loadSources()
  } catch (error) {
    source.enabled = !enabled
    ElMessage.error(error?.msg || '数据源状态更新失败')
  }
}

async function runSource(source) {
  try {
    const result = await runPipelineTask(source.id)
    ElMessage.success(result.msg || `${source.name}已开始试运行`)
    await loadSources()
  } catch (error) {
    ElMessage.error(error?.msg || '数据源试运行失败')
  }
}

onMounted(loadSources)
</script>

<style scoped>
.source-stats {
  margin-bottom: 2px;
}

.source-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 16px; }
.source-form-grid .is-full { grid-column: 1 / -1; }
@media (max-width: 760px) { .source-form-grid { grid-template-columns: 1fr; } .source-form-grid .is-full { grid-column: auto; } }

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
