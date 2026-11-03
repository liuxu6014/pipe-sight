<template>
  <div class="pipeline-page ws-list-page source-page">
    <div class="source-summary" aria-label="数据源统计">
      <span>全部来源 <strong>{{ rows.length }}</strong></span>
      <span>已启用 <strong>{{ enabledCount }}</strong></span>
      <div class="source-summary-actions">
        <el-button v-if="canSourceSave" type="primary" :icon="Plus" @click="openCreateDialog">新增公众号</el-button>
      </div>
    </div>

    <el-segmented v-model="activeType" :options="sourceTypeOptions" class="source-type-filter" aria-label="来源分类" />

    <el-alert v-if="sourceError" type="warning" show-icon :closable="false" class="source-load-error">
      <template #title>{{ sourceError }}</template>
      <template #default><el-button class="source-retry" @click="loadSources">重新加载</el-button></template>
    </el-alert>
    <el-card v-else shadow="never" class="source-list-card ws-list-panel">
      <el-table ref="sourceTable" v-loading="loading" :data="pagedRows" row-key="id" height="100%" class="source-table" aria-label="数据源列表" :aria-busy="loading" :empty-text="loading ? '正在加载数据源…' : activeType === 'all' ? '暂无数据源' : `暂无${typeText(activeType)}来源`">
        <el-table-column prop="name" label="数据源名称" min-width="280" align="left">
          <template #default="{ row }"><strong class="source-name">{{ row.name }}</strong></template>
        </el-table-column>
        <el-table-column label="来源类型" width="120" align="center">
          <template #default="{ row }"><el-tag :type="typeTag(sourceType(row))" effect="light">{{ typeText(sourceType(row)) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="采集频率" width="180" align="center">
          <template #default="{ row }">
            <div v-if="sourceType(row) === 'wechat'" class="source-frequency-cell">
              <el-button v-if="canSourceSave" plain type="primary" :icon="Clock" :disabled="busy" @click="openFrequencyDialog(row)">设置频率</el-button>
            </div>
            <span v-else class="source-cell-empty">—</span>
          </template>
        </el-table-column>
        <el-table-column label="最后采集" width="180" align="center">
          <template #default="{ row }">{{ formatBusinessTime(row.lastRunAt ?? row.last_run_at) || '—' }}</template>
        </el-table-column>
        <el-table-column label="是否启用" width="180" align="center">
          <template #default="{ row }">
            <div class="source-list-actions" role="group" :aria-label="`${row.name}操作`">
              <el-button v-if="canSourceSave && sourceType(row) === 'wechat'" plain type="primary" :disabled="busy" @click="openEditDialog(row)">编辑</el-button>
              <el-switch :model-value="sourceEnabled(row)" :disabled="!canSourceSave || busy" :loading="pendingSourceId === row.id" :aria-label="`${row.name}采集开关`" @change="toggleSource(row)" />
            </div>
          </template>
        </el-table-column>
      </el-table>
      <pagination v-model:page="page" v-model:limit="pageSize" :total="filteredRows.length" :auto-scroll="false" class="source-pagination" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingSource ? (editDetails ? '编辑公众号' : '设置采集频率') : '新增公众号'" width="min(520px, calc(100vw - 32px))" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving" destroy-on-close>
      <el-form label-position="top" :model="sourceForm" :disabled="saving" @submit.prevent="saveSource">
        <p v-if="editingSource && !editDetails" class="source-dialog-name">{{ editingSource.name }}</p>
        <template v-else>
          <el-form-item label="公众号名称" required><el-input v-model="sourceForm.name" maxlength="255" placeholder="请输入公众号名称" /></el-form-item>
          <el-form-item label="公众号 RSS 链接" required><el-input v-model="sourceForm.feedUrl" placeholder="请输入已授权的公众号 feed 地址" /></el-form-item>
        </template>
        <el-form-item label="采集间隔">
          <div class="source-frequency-controls">
            <el-select v-model="frequency.unit" aria-label="采集间隔单位" @change="resetIntervalAmount">
              <el-option v-if="hasExistingSchedule" label="保留现有时间计划" value="preserve" />
              <el-option label="按分钟" value="minute" />
              <el-option label="按小时" value="hour" />
              <el-option label="每天" value="day" />
              <el-option label="每周" value="week" />
              <el-option label="不定时采集" value="off" />
            </el-select>
            <template v-if="frequency.unit === 'minute' || frequency.unit === 'hour'">
              <span>每</span>
              <el-select v-model="frequency.amount" aria-label="采集间隔数值" class="source-interval-amount">
                <el-option v-for="amount in intervalChoices" :key="amount" :label="String(amount)" :value="amount" />
              </el-select>
              <span>{{ frequency.unit === 'minute' ? '分钟' : '小时' }}</span>
            </template>
          </div>
        </el-form-item>
        <p class="source-frequency-help">{{ frequencyPreview }}<template v-if="frequency.unit !== 'off'"> · {{ editingSource?.timezone || 'Asia/Shanghai' }}</template></p>
        <p v-if="frequency.unit === 'minute' || frequency.unit === 'hour'" class="source-frequency-help">按时钟整点对齐；例如每 6 小时在 00:00、06:00、12:00、18:00 采集。</p>
        <el-alert v-if="hasExistingSchedule" title="已有指定时间计划，默认保留；选择新的采集间隔后才会替换。" type="info" :closable="false" />
        <el-alert v-if="dialogError" :title="dialogError" type="error" :closable="false" class="source-dialog-error" />
      </el-form>
      <template #footer>
        <el-button :disabled="saving" @click="dialogVisible = false">取消</el-button>
        <el-button v-if="canSourceSave" type="primary" :loading="saving" @click="saveSource">{{ editingSource ? (editDetails ? '保存' : '保存频率') : '新增公众号' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { formatBusinessTime } from '@/utils/portal/businessTime'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Clock, Plus } from '@element-plus/icons-vue'
import { createPipelineSource, disablePipelineSource, listPipelineSources, updatePipelineSource } from '@/api/pipeline/intelligence'
import { sourceEnabled } from '@/utils/pipeline/compactContract'
import { checkPermi } from '@/utils/permission'
import { editedWechatSourcePayload, existingSourcePayload, newWechatSourcePayload, sourceCron, sourceFrequency, sourceFrequencyText, sourceIntervalChoices, sourceIntervalCron } from '@/utils/pipeline/sourceManagement'

defineOptions({ name: 'PipelineSource' })

const loading = ref(false)
const sourceError = ref('')
const rows = ref([])
const dialogVisible = ref(false)
const saving = ref(false)
const dialogError = ref('')
const editingSource = ref(null)
const editDetails = ref(false)
const pendingSourceId = ref(null)
const canSourceList = computed(() => checkPermi(['pipeline:source:list']))
const canSourceSave = computed(() => checkPermi(['pipeline:source:save']))
const busy = computed(() => loading.value || saving.value || pendingSourceId.value !== null)
const sourceForm = reactive({ name: '', sourceType: 'wechat', feedUrl: '' })
const frequency = reactive({ unit: 'hour', amount: 6 })
const intervalChoices = computed(() => sourceIntervalChoices[frequency.unit] || [])
const hasExistingSchedule = computed(() => editingSource.value && sourceFrequency(sourceCron(editingSource.value)).unit === 'preserve')
const frequencyPreview = computed(() => sourceFrequencyText(sourceIntervalCron(frequency, sourceCron(editingSource.value || {}))))
const enabledCount = computed(() => rows.value.filter(sourceEnabled).length)
const activeType = ref('all')
function sourceType(source) {
  const type = source.type || source.sourceType
  return type === 'news' ? 'website' : type
}
const sourceTypeOptions = computed(() => [
  { value: 'all', label: `全部（${rows.value.length}）` },
  ...['paper', 'website', 'wechat'].map(type => ({ value: type, label: `${typeText(type)}（${rows.value.filter(row => sourceType(row) === type).length}）` }))
])
const filteredRows = computed(() => activeType.value === 'all' ? rows.value : rows.value.filter(row => sourceType(row) === activeType.value))
const sourceTable = ref(null)
const page = ref(1)
const pageSize = ref(10)
const pagedRows = computed(() => filteredRows.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))

watch([activeType, pageSize], () => { page.value = 1 }, { flush: 'sync' })
watch(() => filteredRows.value.length, total => {
  page.value = Math.min(page.value, Math.max(1, Math.ceil(total / pageSize.value)))
}, { flush: 'sync' })
watch([page, pageSize, activeType], () => sourceTable.value?.setScrollTop(0), { flush: 'post' })

function typeText(type) {
  return { website: '新闻网站', news: '新闻网站', wechat: '公众号', paper: '论文' }[type] || type || '其他来源'
}
function typeTag(type) {
  return { website: 'primary', news: 'primary', wechat: 'success', paper: 'warning' }[type] || 'info'
}

async function loadSources() {
  if (!canSourceList.value) { sourceError.value = '暂无数据源列表查看权限'; return }
  loading.value = true
  sourceError.value = ''
  try {
    const res = await listPipelineSources()
    if (!Array.isArray(res.data?.rows)) throw new Error('数据源列表响应格式异常，请重试')
    rows.value = res.data.rows
  } catch (error) {
    rows.value = []
    sourceError.value = error?.msg || error?.message || '数据源列表暂时无法加载，请检查服务后重试'
  } finally {
    loading.value = false
  }
}

function resetIntervalAmount() {
  if (!intervalChoices.value.includes(frequency.amount)) frequency.amount = intervalChoices.value[0] || 1
  dialogError.value = ''
}
function openCreateDialog() {
  if (!canSourceSave.value || busy.value) return
  editDetails.value = false
  editingSource.value = null
  Object.assign(sourceForm, { name: '', sourceType: 'wechat', feedUrl: '' })
  Object.assign(frequency, { unit: 'hour', amount: 6 })
  dialogError.value = ''
  dialogVisible.value = true
}
function openFrequencyDialog(source) {
  if (!canSourceSave.value || busy.value || sourceType(source) !== 'wechat') return
  editDetails.value = false
  editingSource.value = source
  Object.assign(frequency, sourceFrequency(sourceCron(source)))
  dialogError.value = ''
  dialogVisible.value = true
}
function openEditDialog(source) {
  if (!canSourceSave.value || busy.value || sourceType(source) !== 'wechat') return
  openFrequencyDialog(source)
  editDetails.value = true
  Object.assign(sourceForm, { name: source.name, sourceType: 'wechat', feedUrl: source.config?.feed_url || source.url || source.endpoint || '' })
}
async function saveSource() {
  if (!canSourceSave.value || busy.value) return
  dialogError.value = ''
  if (editingSource.value && sourceType(editingSource.value) !== 'wechat') {
    dialogError.value = '论文和新闻网站仅支持启停'
    return
  }
  let payload
  try {
    payload = editingSource.value
      ? (editDetails.value ? editedWechatSourcePayload(editingSource.value, sourceForm, frequency) : existingSourcePayload(editingSource.value, { cron: sourceIntervalCron(frequency, sourceCron(editingSource.value)) }))
      : newWechatSourcePayload(sourceForm, frequency)
  } catch (error) {
    dialogError.value = error.message
    return
  }
  saving.value = true
  try {
    if (editingSource.value) await updatePipelineSource(editingSource.value.id, payload)
    else await createPipelineSource(payload)
    dialogVisible.value = false
    ElMessage.success(editingSource.value ? (editDetails.value ? '公众号已更新' : '采集频率已更新') : '公众号已新增')
    await loadSources()
  } catch (error) {
    dialogError.value = error?.msg || error?.message || '保存失败，请重试'
  } finally {
    saving.value = false
  }
}
async function toggleSource(source) {
  if (!canSourceSave.value || busy.value) return
  const enabled = sourceEnabled(source)
  pendingSourceId.value = source.id
  try {
    if (enabled) await disablePipelineSource(source.id)
    else await updatePipelineSource(source.id, existingSourcePayload(source, { isEnabled: true }))
    ElMessage.success(enabled ? '来源已停用；已开始的采集不会立即停止' : '来源已启用')
    await loadSources()
  } catch (error) {
    ElMessage.error(error?.msg || error?.message || '数据源状态更新失败')
  } finally {
    pendingSourceId.value = null
  }
}

onMounted(loadSources)
</script>

<style scoped>
.source-page { min-width: 0; gap: 12px; }
.source-summary { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 24px; padding: 12px 16px; border: 1px solid #e5ebf1; border-radius: 8px; color: #526277; font-size: 13px; background: #fff; }
.source-summary strong { margin-left: 6px; color: #173d56; font-size: 18px; }
.source-summary-actions { margin-left: auto; }
.source-type-filter { align-self: flex-start; max-width: 100%; }
.source-type-filter :deep(.el-segmented__group) { flex-wrap: wrap; }
.source-list-card :deep(.el-card__body) { padding: 0; }
.source-table { width: 100%; }
.source-pagination { flex: 0 0 auto; margin: 0; padding: 12px 20px; border-top: 1px solid var(--el-border-color-lighter); }
.source-pagination :deep(.el-pagination) { display: flex; flex-wrap: wrap; gap: 8px; }
.source-pagination :deep(.el-pagination__sizes) { margin-right: auto; }
@media (max-width: 767px) {
  .source-pagination { padding: 10px 12px; }
  .source-pagination :deep(.el-pagination__jump) { display: none; }
}
.source-table :deep(td.el-table__cell) { height: 68px; padding: 10px 0; vertical-align: middle; }
.source-table :deep(.cell) { padding-inline: 16px; }
.source-table :deep(th.el-table__cell) { padding: 12px 0; }
.source-name { font-size: 14px; line-height: 1.6; font-weight: 600; color: var(--el-text-color-primary); overflow-wrap: anywhere; }
.source-frequency-cell { display: flex; align-items: center; justify-content: center; gap: 12px; }
.source-frequency-cell > :deep(.el-button) { flex-shrink: 0; margin: 0; }
.source-cell-empty { color: var(--el-text-color-secondary); }
.source-cell-empty { display: block; text-align: center; }
.source-list-actions { display: grid; grid-template-columns: 64px 40px; gap: 12px; align-items: center; justify-content: center; }
.source-list-actions > :deep(.el-button) { grid-column: 1; margin: 0; }
.source-summary-actions > :deep(.el-button) { margin-left: 0; }
.source-list-actions > :deep(.el-switch) { grid-column: 2; grid-row: 1; margin: 0; }
.source-retry { min-height: 44px; color: #409eff; }
.source-dialog-name { margin: 0 0 16px; font-weight: 600; overflow-wrap: anywhere; }
.source-frequency-controls { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; width: 100%; }
.source-frequency-controls > :deep(.el-select) { flex: 1 1 140px; min-width: 0; }
.source-frequency-controls > :deep(.source-interval-amount) { flex: 0 1 72px; }
.source-frequency-help { color: #526277; font-size: 13px; line-height: 1.6; margin: 0 0 12px; }
.source-dialog-error { margin-top: 12px; }
</style>
