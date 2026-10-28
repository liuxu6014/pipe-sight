<template>
  <div class="pipeline-page ws-list-page">
    <section class="page-heading">
      <div>
        <h1>数据源管理</h1>

      </div>
      <el-button v-if="canSourceSave" type="primary" :icon="Plus" @click="openSourceDialog()">新增数据源</el-button>
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
          <span>数据源总数</span>
          <strong>{{ rows.length }}</strong>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="never" class="stat-card">
          <span>来源类型</span>
          <strong>{{ typeCount }}</strong>
        </el-card>
      </el-col>
    </el-row>

    <el-alert v-if="sourceError" type="warning" show-icon :closable="false" class="source-load-error">
      <template #title>{{ sourceError }}</template>
      <template #default><el-button class="ps-ui-action source-retry" @click="loadSources">重新加载</el-button></template>
    </el-alert>
    <el-card v-else shadow="never" class="source-list-card ws-list-panel">
      <div v-loading="loading" :aria-busy="loading" class="source-list-region ws-list-scroll" tabindex="0" aria-label="数据源列表滚动区">
        <ul class="source-list" aria-label="数据源列表">
          <li v-for="row in rows" :key="row.id" class="source-list-item">
            <div class="source-list-copy">
              <div class="source-list-heading"><h2>{{ row.name }}</h2><el-tag :type="typeTag(row.type)" effect="light">{{ typeText(row.type) }}</el-tag><el-tag :type="sourceEnabled(row) ? 'success' : 'info'">{{ sourceEnabled(row) ? '启用' : '停用' }}</el-tag></div>
              <div class="source-list-meta"><span>采集周期：{{ row.cron || '手动采集' }}</span><span>最后采集：{{ formatBusinessTime(row.lastRunAt) || '—' }}</span></div>
            </div>
            <div class="source-list-actions" role="group" :aria-label="`${row.name}操作`">
              <el-button v-if="canSourceSave" plain type="primary" :icon="Edit" @click="openSourceDialog(row)">配置</el-button>
              <el-button v-if="canTaskRun" plain type="primary" :icon="VideoPlay" :disabled="!sourceEnabled(row) || Boolean(runningSourceId) || !supportsSourceAdapter(row)" :loading="runningSourceId === row.id" @click="runSource(row)">{{ supportsSourceAdapter(row) ? '立即采集' : '采集待接入' }}</el-button>
              <el-button v-if="canSourceSave" plain :type="sourceEnabled(row) ? 'danger' : 'success'" @click="toggleSource(row)">{{ sourceEnabled(row) ? '停用' : '启用' }}</el-button>
            </div>
          </li>
        </ul>
        <el-empty v-if="!loading && !rows.length" description="暂无数据源" :image-size="64" />
        <p v-if="loading && !rows.length" class="source-list-loading" role="status">正在加载数据源…</p>
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingSource ? '配置数据源' : '新增数据源'" width="620px" destroy-on-close>
      <el-form label-position="top" :model="sourceForm">
        <div class="source-form-grid">
          <el-form-item label="数据源名称"><el-input v-model="sourceForm.name" placeholder="例如：国家管网集团要闻" /></el-form-item>

          <el-form-item label="来源类型"><el-select v-model="sourceForm.sourceType"><el-option label="新闻源" value="website" /><el-option label="公众号（采集待接入）" value="wechat" disabled /><el-option label="论文库" value="paper" /></el-select></el-form-item>
          <el-form-item label="采集适配器"><el-select v-model="sourceForm.adapterKey" :disabled="!availableAdapters.length" placeholder="当前类型暂无采集适配器"><el-option v-for="adapter in availableAdapters" :key="adapter.key" :label="adapter.label" :value="adapter.key" /></el-select></el-form-item>
          <el-form-item label="入口地址" class="is-full"><el-input v-model="sourceForm.endpoint" placeholder="https://..." /></el-form-item>
          <el-form-item label="调度表达式"><el-input v-model="sourceForm.scheduleCron" placeholder="留空表示仅手动运行" /></el-form-item>

          <el-form-item label="时区"><el-input v-model="sourceForm.timezone" /></el-form-item>
          <el-form-item label="翻译模型（可选）"><el-select v-model="sourceForm.modelId" clearable placeholder="不自动翻译"><el-option v-for="model in textModels" :key="model.modelId" :label="model.modelName || model.modelCode" :value="model.modelId" /></el-select></el-form-item>
          <el-form-item label="单次抓取上限"><el-input-number v-model="sourceForm.limit" :min="1" :max="30" /></el-form-item>
          <el-form-item v-if="sourceForm.adapterKey === 'crossref_works'" label="论文检索词" class="is-full"><el-input v-model="sourceForm.query" placeholder="例如：oil gas pipeline integrity monitoring" /></el-form-item>
        </div>
        <el-alert v-if="!adapterSupported" title="当前来源未接入可用采集适配器，不能保存或启用采集。已有公众号文章仍可浏览和用于选材；自动采集需接入经授权的来源接口。" type="warning" :closable="false" />
        <el-alert v-else title="启用来源不会立即采集。停用会取消排队任务；已开始的采集请到任务页单独请求停止。" type="info" :closable="false" />
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button v-if="canSourceSave" type="primary" :loading="saving" :disabled="!adapterSupported" @click="saveSource">保存配置</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { formatBusinessTime } from '@/utils/portal/businessTime'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Edit, Plus, VideoPlay } from '@element-plus/icons-vue'
import { createPipelineSource, disablePipelineSource, listPipelineSources, runPipelineTask, updatePipelineSource } from '@/api/pipeline/intelligence'
import { listModelAll } from '@/api/ai/model'
import { sourceEnabled, modelsFor } from '@/utils/pipeline/compactContract'
import { checkPermi } from '@/utils/permission'
import { adaptersForSource, supportsSourceAdapter } from '@/utils/pipeline/sourceAdapters'

defineOptions({ name: 'PipelineSource' })

const loading = ref(false)
const sourceError = ref('')
const rows = ref([])
const dialogVisible = ref(false)
const saving = ref(false)
const editingSource = ref(null)
const canSourceList = computed(() => checkPermi(['pipeline:source:list']))
const canSourceSave = computed(() => checkPermi(['pipeline:source:save']))
const canTaskRun = computed(() => checkPermi(['pipeline:task:run']))
const runningSourceId = ref('')
const models = ref([])
const textModels = computed(() => modelsFor(models.value, 'text_generate'))
const sourceForm = reactive({ name: '', sourceType: 'website', adapterKey: 'pipechina_group_news', endpoint: '', scheduleCron: '', timezone: 'Asia/Shanghai', modelId: null, limit: 12, query: '', isEnabled: true })
const availableAdapters = computed(() => adaptersForSource(sourceForm.sourceType))
const adapterSupported = computed(() => supportsSourceAdapter(sourceForm))
watch(() => sourceForm.sourceType, () => {
  if (availableAdapters.value.length && !adapterSupported.value) sourceForm.adapterKey = availableAdapters.value[0].key
})
const enabledCount = computed(() => rows.value.filter(sourceEnabled).length)
const typeCount = computed(() => new Set(rows.value.map(item => item.type)).size)
function typeText(type) {
  return { website: '新闻源', news: '新闻源', wechat: '公众号', paper: '论文库' }[type] || type
}

function typeTag(type) {
  return { website: 'primary', news: 'primary', wechat: 'success', paper: 'warning' }[type] || 'info'
}

async function loadSources() {
  if (!canSourceList.value) return
  loading.value = true
  sourceError.value = ''
  try {
    const res = await listPipelineSources()
    rows.value = res.data.rows
  } catch (error) {
    rows.value = []
    sourceError.value = error?.msg || error?.message || '数据源列表暂时无法加载，请检查服务后重试'
    ElMessage.warning(sourceError.value)
  } finally {
    loading.value = false
  }
}

function resetForm(source = null) {
 editingSource.value = source
 Object.assign(sourceForm, { name: source?.name || '', sourceType: source?.type === 'news' ? 'website' : source?.type || 'website',
  adapterKey: source?.adapter || source?.adapter_key || 'pipechina_group_news', endpoint: source?.url ?? source?.endpoint ?? '',
  scheduleCron: source?.cron ?? source?.schedule_cron ?? '', timezone: source?.timezone || 'Asia/Shanghai',
  modelId: source?.modelId ?? source?.model_id ?? null, limit: Number(source?.config?.limit || 12), query: source?.config?.query || '',
  isEnabled: source ? sourceEnabled(source) : true })
}
function openSourceDialog(source = null) {
 if (!canSourceSave.value) return
 resetForm(source); dialogVisible.value = true
}
function sourcePayload() {
 return { name: sourceForm.name.trim(), type: sourceForm.sourceType, url: sourceForm.endpoint.trim() || null,
 adapter: sourceForm.adapterKey, cron: sourceForm.scheduleCron.trim() || null, timezone: sourceForm.timezone,
 modelId: sourceForm.modelId || null, isEnabled: sourceForm.isEnabled,
 config: { ...(editingSource.value?.config || {}), limit: sourceForm.limit, ...(sourceForm.adapterKey === 'crossref_works' ? { query: sourceForm.query } : {}) } }
}
async function saveSource() {
  if (!canSourceSave.value) return
  if (saving.value) return
  if (!adapterSupported.value) return ElMessage.warning('当前来源类型未接入可用采集适配器')
  if (!sourceForm.name.trim() || !sourceForm.adapterKey) return ElMessage.warning('请填写名称并选择采集适配器')
  saving.value = true
  try {
    const payload = sourcePayload()
    if (editingSource.value) await updatePipelineSource(editingSource.value.id, payload)
    else await createPipelineSource(payload)
    dialogVisible.value = false
    ElMessage.success(editingSource.value ? '数据源配置已更新' : '数据源已创建')
    await loadSources()
  } catch (error) {
    ElMessage.error(error?.msg || error?.message || '数据源保存失败')
  } finally {
    saving.value = false
  }
}

async function toggleSource(source) {
  if (!canSourceSave.value) return
  const enabled = sourceEnabled(source)
  if (!enabled && !supportsSourceAdapter(source)) return ElMessage.warning('当前来源尚未接入匹配的采集适配器，不能启用')
  try {
    if (enabled) await disablePipelineSource(source.id)
    else await updatePipelineSource(source.id, { name: source.name, type: source.type === 'news' ? 'website' : source.type, url: source.url ?? source.endpoint ?? null, adapter: source.adapter || source.adapter_key, cron: source.cron ?? source.schedule_cron ?? null, timezone: source.timezone || 'Asia/Shanghai', config: source.config || {}, modelId: source.modelId ?? source.model_id ?? null, isEnabled: true })
    ElMessage.success(enabled ? '来源已停用，排队任务取消；运行中的采集需单独停止' : '来源已启用，后续可定时或手动采集')
    await loadSources()
  } catch (error) {
    ElMessage.error(error?.msg || error?.message || '数据源状态更新失败')
  }
}

async function runSource(source) {
  if (!canTaskRun.value || !sourceEnabled(source) || runningSourceId.value || !supportsSourceAdapter(source)) return
  runningSourceId.value = source.id
  try {
    const result = await runPipelineTask(source.id)
    ElMessage.success(result.msg || '采集请求已提交，请到任务页查看运行状态')
    await loadSources()
  } catch (error) {
    ElMessage.error(error?.msg || error?.message || '采集请求失败')
  } finally { runningSourceId.value = '' }
}

onMounted(async () => { await loadSources(); if (checkPermi(['ai:model:query'])) { try { const res = await listModelAll(); models.value = res.data?.rows || res.data || [] } catch { ElMessage.warning('翻译模型列表暂时无法加载，可稍后配置') } } })
</script>

<style scoped>
.source-list-card :deep(.el-card__body) { padding: 0; }
.source-list-region { min-height: 96px; }
.source-list { list-style: none; margin: 0; padding: 0; }
.source-list-item { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 18px 20px; border-bottom: 1px solid #e5ebf1; }
.source-list-item:last-child { border-bottom: 0; }
.source-list-copy { min-width: 0; flex: 1; }
.source-list-heading { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.source-list-heading h2 { margin: 0 4px 0 0; font-size: 15px; line-height: 1.6; font-weight: 600; color: #173d56; overflow-wrap: anywhere; }
.source-list-meta { display: flex; flex-wrap: wrap; gap: 6px 24px; margin-top: 8px; font-size: 13px; line-height: 1.6; color: #526277; overflow-wrap: anywhere; }
.source-list-actions { display: flex; align-items: center; flex-shrink: 0; gap: 16px; }
.source-list-actions :deep(.el-button) { margin-left: 0; min-height: 44px; }
.source-list-loading { padding: 24px; margin: 0; color: #526277; }
@media (max-width: 760px) {
  .source-list-item { align-items: stretch; flex-direction: column; gap: 8px; padding: 16px; }
  .source-list-actions { justify-content: flex-end; flex-wrap: wrap; gap: 12px; }
}
.source-stats {
  margin-bottom: 2px;
}

.source-load-error { margin-bottom: 18px; }
.source-retry { padding: 0; border: 0; background: transparent; color: #2764e7; cursor: pointer; font-size: 13px; }

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
