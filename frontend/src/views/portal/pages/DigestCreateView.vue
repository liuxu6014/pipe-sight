<template>
  <div class="ps-page ps-create-page ps-digest-create-page" :class="{ 'is-configuring': activeStep === 0 }">
    <header class="ps-create-context">
      <el-button :icon="Back" circle class="ps-ui-action ps-create-back" :disabled="submitting" :title="activeStep ? '返回上一步' : '返回上一页'" :aria-label="activeStep ? '返回上一步' : '返回上一页'" @click="goBack" />
      <div class="ps-create-heading"><h1>新建简报</h1></div>
      <el-steps :active="activeStep" finish-status="success" simple class="ps-create-steps" aria-label="新建简报步骤">
        <el-step title="简报配置" :aria-current="activeStep === 0 ? 'step' : undefined"><template #icon>1</template></el-step>
        <el-step title="确认生成" :aria-current="activeStep === 1 ? 'step' : undefined"><template #icon>2</template></el-step>
      </el-steps>
    </header>

    <section class="ps-step-card">
      <div v-if="activeStep === 0" class="ps-step-content">
        <div v-if="sourceTaskLoading || sourceTaskError" class="ps-inline-state is-warning" role="status">
          <span>{{ sourceTaskLoading ? '正在载入原简报配置…' : sourceTaskError }}</span>
          <el-button v-if="sourceTaskError" plain @click="loadSourceTask">重试载入</el-button>
        </div>
        <div class="ps-form-grid ps-digest-config-fields">
          <div class="ps-digest-type-field"><span>简报类型</span>
            <el-radio-group v-model="form.type" aria-label="简报类型">
              <el-radio-button value="周报">周报</el-radio-button>
              <el-radio-button value="月报">月报</el-radio-button>
            </el-radio-group>
          </div>
          <label>{{ periodFieldLabel }}
            <el-date-picker v-if="form.type === '周报'" v-model="form.period" type="daterange" popper-class="ps-digest-period-popper" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" />
            <el-date-picker v-else v-model="form.month" type="month" placeholder="选择报告月份" />
          </label>
          <label>简报模板
            <el-select v-model="form.templateId" aria-label="简报模板" placeholder="系统默认模板" :loading="templatesLoading">
              <el-option label="系统默认模板" value="" />
              <el-option v-for="item in availableTemplates" :key="item.id" :label="item.name" :value="item.id" />
              <el-option v-if="templateUnavailable" label="原模板已不可用" :value="form.templateId" disabled />
            </el-select>
          </label>
        </div>
        <DigestScreeningRules v-model:categories="screeningCategories" v-model:prompt="screeningPrompt"
          class="ps-digest-screening-rule" :default-prompt="templateGeneralPrompt">
          <template #actions>
            <el-button v-if="categoryOverride !== null || screeningPromptOverride !== null" @click="resetRules">恢复模板规则</el-button>
          </template>
        </DigestScreeningRules>
        <div v-if="templateError || templateUnavailable" class="ps-inline-state is-warning" role="alert">
          <span>{{ templateUnavailable ? '请选择可用的简报模板。' : templateError }}</span>
          <el-button v-if="templateError" size="small" @click="loadTemplates">重试加载模板</el-button>
        </div>
      </div>

      <div v-else class="ps-step-content ps-digest-confirm" tabindex="0" aria-label="确认生成简报">
        <section v-if="refreshing" class="ps-digest-screening-status" role="status" aria-live="polite">
          <strong>系统正在按提示词自动筛选、分类并打标签</strong>
          <el-progress v-if="screeningTotal" :percentage="Math.floor(screeningProcessed * 100 / screeningTotal)" :show-text="false" />
          <span>{{ screeningTotal ? `已处理 ${screeningProcessed} / ${screeningTotal} 篇，完成后即可提交生成。` : '正在查询本期资讯…' }}</span>
        </section>
        <div v-else-if="previewError" class="ps-inline-state is-warning" role="alert">
          <span>{{ previewError }}</span>
          <el-button :disabled="!canStart" @click="refreshPreview">{{ screeningId ? '继续筛选' : '重新筛选' }}</el-button>
        </div>
        <div v-else-if="capacityNotice" class="ps-inline-state is-warning" role="alert">{{ capacityNotice }}</div>
        <div v-else-if="screeningRows && !passedRows.length" class="ps-inline-state is-warning" role="status">
          <span>{{ screeningTotal ? '没有文章符合本次提示词，请返回调整筛选规则。' : '报告周期内没有资讯，请返回调整报告周期。' }}</span>
        </div>
        <el-descriptions title="生成信息" :column="2" border>
          <el-descriptions-item label="简报类型">{{ form.type }}</el-descriptions-item>
          <el-descriptions-item label="报告周期">{{ periodLabel }}</el-descriptions-item>
          <el-descriptions-item label="简报模板">{{ templateName }}</el-descriptions-item>
          <el-descriptions-item label="系统筛选">
            <template v-if="screeningRows">本期 {{ screeningTotal }} 篇，自动纳入 {{ passedRows.length }} 篇</template>
            <template v-else>{{ previewError ? '筛选未完成' : '正在自动筛选…' }}</template>
          </el-descriptions-item>
          <el-descriptions-item v-if="screeningRows && categoryCounts.length" label="分类结果" :span="2">
            {{ categoryCounts.map(item => `${item.name} ${item.count} 篇`).join('、') }}
          </el-descriptions-item>
        </el-descriptions>
        <section aria-labelledby="digest-generation-settings">
          <h2 id="digest-generation-settings">生成设置</h2>
          <div class="ps-form-grid ps-form-grid-wide">
            <label>每栏资讯数量<el-input-number v-model="form.itemCount" :min="3" :max="30" /></label>
            <label>单条摘要长度<el-select v-model="form.summaryLength" aria-label="单条摘要长度"><el-option label="精简（80–120 字）" value="short" /><el-option label="标准（150–200 字）" value="normal" /><el-option label="深度（250–300 字）" value="long" /></el-select></label>
          </div>
          <div class="ps-option-row"><el-checkbox v-model="form.hotAnalysis">包含热点分析</el-checkbox><el-checkbox v-model="form.duplicateMerge">合并重复事件</el-checkbox></div>
        </section>
      </div>

      <footer class="ps-step-footer">
        <small v-if="activeStep === 0" class="ps-digest-rule-note">系统按本次规则筛选资讯。另存后可在以后的简报中复用。</small>
        <el-button v-if="activeStep > 0" :disabled="submitting" @click="goBack">上一步</el-button>
        <span class="ps-digest-footer-spacer" />
        <el-button v-if="activeStep === 0" :disabled="!canSaveTemplate" @click="openSaveTemplate">存为模板</el-button>
        <el-button v-if="activeStep === 0" @click="goBack">取消</el-button>
        <el-button v-if="activeStep === 0" type="primary" :disabled="!canStart" @click="confirmGeneration">下一步</el-button>
        <el-button v-else type="primary" :loading="submitting" :disabled="!canGenerate" @click="createDigest">提交生成任务</el-button>
      </footer>
    </section>
    <el-dialog v-model="saveDialogOpen" title="存为模板" width="min(440px, calc(100vw - 32px))"
      :close-on-click-modal="false" :close-on-press-escape="!savingTemplate" :show-close="!savingTemplate" append-to-body align-center>
      <el-form label-position="top" @submit.prevent="saveAsTemplate">
        <el-form-item label="模板名称" for="digest-new-template-name" :error="saveTemplateError">
          <el-input id="digest-new-template-name" v-model="newTemplateName" :maxlength="255" :disabled="savingTemplate"
            :placeholder="`例如：工程应用专题${form.type}`" @input="saveTemplateError = ''" />
        </el-form-item>
        <p class="ps-digest-rule-note">保存后，可在「我的模板 → 情报简报」中编辑和复用。</p>
      </el-form>
      <template #footer>
        <el-button :disabled="savingTemplate" @click="saveDialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="savingTemplate" :disabled="!newTemplateName.trim() || !canSaveTemplate" @click="saveAsTemplate">保存模板</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { useWizardHistory } from '@/utils/portal/wizardHistory'
import { decimalId, ID_UPGRADE_NOTICE, requireBusinessId } from '@/utils/portal/businessId'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { calendarDate, parseCalendarDate } from '@/utils/portal/businessTime'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back } from '@element-plus/icons-vue'
import DigestScreeningRules from '../components/DigestScreeningRules.vue'
import { screeningRulesError } from '@/utils/portal/digestScreeningRules'
import usePortalStore from '@/store/modules/portal'
import { advancePipelineDigestScreening, createPipelineResearchJob, createPipelineTemplate, getPipelineResearchJob, listPipelineTemplates, startPipelineDigestScreening } from '@/api/pipeline/intelligence'
import { DIGEST_SELECTION_LIMIT } from '@/utils/portal/evidenceInput'
import { digestTemplatesFor } from '@/utils/pipeline/compactContract'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const refreshing = ref(false)
const previewError = ref('')
const { activeStep, advanceStep, goBack, isCurrentVisit, draftQuery } = useWizardHistory(router, route, '/portal/digests', step => step === 1 && canStart.value)
const screeningId = ref('')
const screeningRows = ref(null)
const screeningTotal = ref(0)
const screeningProcessed = ref(0)
const screeningPromptOverride = ref(null)
const defaultScreeningPrompt = ref('')
const defaultWritingPrompts = ref({})
const defaultCategories = ref(null)
const categoryOverride = ref(null)
const sourceTaskLoading = ref(false)
const sourceTaskError = ref('')
let previewGeneration = 0
let sourceTaskGeneration = 0
let stopped = false
onBeforeUnmount(() => { stopped = true; previewGeneration += 1; sourceTaskGeneration += 1 })
const submitting = ref(false)
const requestId = ref('')
let requestFingerprint = ''
const reportTypeConfigs = {
  周报: { reportType: 'weekly', periodLabel: '报告周期', itemCount: 10 },
  月报: { reportType: 'monthly', periodLabel: '报告月份', itemCount: 15 }
}
const initialType = ({ weekly: '周报', monthly: '月报', 周报: '周报', 月报: '月报' })[String(route.query.type || '')] || '周报'
const form = reactive({ type: initialType, templateId: '', period: [], month: new Date(), itemCount: reportTypeConfigs[initialType].itemCount, summaryLength: 'normal', hotAnalysis: true, duplicateMerge: true })
const currentTypeConfig = computed(() => reportTypeConfigs[form.type])
const templates = ref([]), templatesLoading = ref(false), templateError = ref('')
const availableTemplates = computed(() => digestTemplatesFor(templates.value, currentTypeConfig.value?.reportType))
const templateUnavailable = computed(() => Boolean(form.templateId && !availableTemplates.value.some(item => item.id === form.templateId)))
async function loadTemplates() {
  const session = portalStore.workspaceEpoch
  templatesLoading.value = true
  templateError.value = ''
  try {
    const { data } = await listPipelineTemplates({ category: 'digest', publishedOnly: true })
    if (!stopped && session === portalStore.workspaceEpoch) {
      templates.value = data.rows
      defaultScreeningPrompt.value = data.defaultScreeningPrompt || ''
      defaultWritingPrompts.value = data.defaultWritingPrompts || {}
      defaultCategories.value = data.defaultScreeningCategories ?? null
    }
  } catch (error) {
    if (!stopped && session === portalStore.workspaceEpoch) templateError.value = error?.msg || '模板加载失败'
  } finally { templatesLoading.value = false }
}
const periodFieldLabel = computed(() => currentTypeConfig.value.periodLabel)
const periodLabel = computed(() => buildReportPeriod().label)
const activeTemplate = computed(() => availableTemplates.value.find(item => item.id === form.templateId))
const templateName = computed(() => activeTemplate.value?.name || '系统默认模板')
const templateGeneralPrompt = computed(() => activeTemplate.value?.screeningPrompt || defaultScreeningPrompt.value)
const templateCategories = computed(() => activeTemplate.value?.screeningCategories ?? defaultCategories.value)
const screeningCategories = computed({
  get: () => categoryOverride.value ?? templateCategories.value ?? [],
  set: value => { categoryOverride.value = value }
})
const screeningPrompt = computed({
  get: () => screeningPromptOverride.value ?? templateGeneralPrompt.value,
  set: value => { screeningPromptOverride.value = value }
})
const saveDialogOpen = ref(false)
const newTemplateName = ref('')
const saveTemplateError = ref('')
const savingTemplate = ref(false)
const writingPrompt = computed(() => activeTemplate.value?.prompt || defaultWritingPrompts.value[currentTypeConfig.value?.reportType])
const canSaveTemplate = computed(() => Boolean(writingPrompt.value && !templatesLoading.value && !templateError.value
  && !templateUnavailable.value && !sourceTaskLoading.value && !sourceTaskError.value && !screeningRulesError(screeningCategories.value)))
function openSaveTemplate() {
  if (!canSaveTemplate.value) return
  newTemplateName.value = ''
  saveTemplateError.value = ''
  saveDialogOpen.value = true
}
async function saveAsTemplate() {
  const name = newTemplateName.value.trim()
  if (!saveDialogOpen.value || savingTemplate.value || !canSaveTemplate.value || !name) return
  const session = portalStore.workspaceEpoch
  savingTemplate.value = true
  saveTemplateError.value = ''
  try {
    const { data } = await createPipelineTemplate({
      name, purpose: 'digest', digestCadence: currentTypeConfig.value.reportType, isEnabled: true,
      description: activeTemplate.value?.description || '', prompt: writingPrompt.value,
      screeningPrompt: screeningPrompt.value.trim() || templateGeneralPrompt.value,
      screeningCategories: screeningCategories.value.map(({ name, prompt }) => ({ name: name.trim(), prompt: prompt.trim() }))
    })
    if (stopped || session !== portalStore.workspaceEpoch) return
    templates.value = [data, ...templates.value]
    form.templateId = data.id
    saveDialogOpen.value = false
    ElMessage.success('已保存到我的模板')
  } catch (error) {
    if (!stopped && session === portalStore.workspaceEpoch) saveTemplateError.value = error?.msg || error?.message || '模板保存失败，请重试'
  } finally {
    savingTemplate.value = false
  }
}
function resetRules() {
  screeningPromptOverride.value = null
  categoryOverride.value = null
}
watch(() => form.templateId, resetRules, { flush: 'sync' })
const previewScope = computed(() => ({
  reportType: currentTypeConfig.value?.reportType,
  templateId: form.templateId ? requireBusinessId(form.templateId) : null,
  period: buildReportPeriod().period,
  screeningPrompt: screeningPromptOverride.value?.trim() || null,
  screeningCategories: categoryOverride.value ?? templateCategories.value
}))
const scopeKey = computed(() => JSON.stringify(previewScope.value))
const canStart = computed(() => Boolean(currentTypeConfig.value && periodLabel.value
  && !screeningRulesError(screeningCategories.value) && !templatesLoading.value && !templateError.value
  && !sourceTaskLoading.value && !sourceTaskError.value && !templateUnavailable.value))
const passedRows = computed(() => (screeningRows.value || []).filter(item => item.keep))
const categoryCounts = computed(() => {
  const counts = new Map(screeningCategories.value.map(rule => [rule.name.trim(), 0]))
  for (const row of passedRows.value) counts.set(row.category, (counts.get(row.category) || 0) + 1)
  return Array.from(counts, ([name, count]) => ({ name, count }))
})
const capacityNotice = computed(() => passedRows.value.length > DIGEST_SELECTION_LIMIT
  ? `通过筛选的资讯有 ${passedRows.value.length} 篇，每份简报最多纳入 ${DIGEST_SELECTION_LIMIT} 篇。请返回收紧筛选提示词。`
  : '')
const canGenerate = computed(() => Boolean(screeningId.value && passedRows.value.length
  && !refreshing.value && !previewError.value && !capacityNotice.value && canStart.value))
function ensureRequestId(payload) {
  const fingerprint = JSON.stringify(payload)
  if (!requestId.value || requestFingerprint !== fingerprint) {
    requestId.value = globalThis.crypto?.randomUUID?.() || `digest-${Date.now()}-${Math.random().toString(16).slice(2)}`
    requestFingerprint = fingerprint
  }
  return requestId.value
}
watch(() => form.type, type => {
  if (reportTypeConfigs[type]) form.itemCount = reportTypeConfigs[type].itemCount
  if (templateUnavailable.value) form.templateId = ''
})
function clearScreening() {
  previewGeneration += 1
  screeningRows.value = null
  screeningId.value = ''
  screeningTotal.value = 0
  screeningProcessed.value = 0
  previewError.value = ''
  refreshing.value = false
}
async function recoverScreeningError(error) {
  if (error?.data !== 'digest_screening_restart') return false
  const session = portalStore.workspaceEpoch
  clearScreening()
  await loadTemplates()
  if (!stopped && session === portalStore.workspaceEpoch && activeStep.value === 1) {
    previewError.value = templateError.value ? '模板加载失败，请返回配置重试加载模板。'
      : templateUnavailable.value ? '原模板已不可用，请返回配置选择模板。'
      : error.message || error.msg || '筛选结果已失效，请重新筛选。'
  }
  return true
}
watch(scopeKey, clearScreening, { flush: 'sync' })
function confirmGeneration() {
  if (!canStart.value) return
  advanceStep()
}
watch(activeStep, step => {
  if (step === 1 && !screeningRows.value && !refreshing.value && !previewError.value) void refreshPreview()
}, { flush: 'sync' })
async function refreshPreview() {
  if (refreshing.value || !canStart.value) return
  const generation = ++previewGeneration
  const session = portalStore.workspaceEpoch
  const current = () => !stopped && generation === previewGeneration && session === portalStore.workspaceEpoch
  refreshing.value = true
  previewError.value = ''
  try {
    let data
    if (!screeningId.value) {
      ;({ data } = await startPipelineDigestScreening(previewScope.value))
      if (!current()) return
      screeningId.value = data.screeningId || ''
      screeningTotal.value = data.total
      screeningProcessed.value = data.processed
    }
    while (!data?.rows) {
      if (!screeningId.value) throw new Error('未收到复筛编号，请重试')
      ;({ data } = await advancePipelineDigestScreening(screeningId.value))
      if (!current()) return
      screeningTotal.value = data.total
      screeningProcessed.value = data.processed
    }
    if (data.rows.length !== screeningTotal.value) throw new Error('复筛结果不完整，请重试')
    screeningRows.value = data.rows.map(item => ({ ...item, id: requireBusinessId(item.id) }))
  } catch (error) {
    if (current() && !await recoverScreeningError(error)) previewError.value = error?.msg || error?.message || '资料复筛失败，请重试'
  } finally {
    if (current()) refreshing.value = false
  }
}
async function loadSourceTask() {
  if (!draftQuery.value.sourceTask) return
  if (!decimalId(draftQuery.value.sourceTask)) { sourceTaskError.value = ID_UPGRADE_NOTICE; return }
  const generation = ++sourceTaskGeneration
  const session = portalStore.workspaceEpoch
  sourceTaskLoading.value = true
  sourceTaskError.value = ''
  try {
    const res = await getPipelineResearchJob(String(draftQuery.value.sourceTask))
    if (stopped || generation !== sourceTaskGeneration || session !== portalStore.workspaceEpoch) return
    const task = res.data || {}
    const config = task.config || {}
    const reportType = task.type || config.reportType || config.report_type
    if (['daily', '日报'].includes(reportType)) throw new Error('历史日报仅供查阅，请返回简报列表新建周报或月报')
    const typeMap = { weekly: '周报', monthly: '月报' }
    if (typeMap[reportType]) form.type = typeMap[reportType]
    await Promise.resolve()
    form.templateId = task.fixedDigestFormat ? '' : decimalId(config.template_id ?? config.templateId) || ''
    const options = config.options || {}
    screeningPromptOverride.value = typeof task.screeningPrompt === 'string' ? task.screeningPrompt : null
    categoryOverride.value = task.screeningCategories ?? (screeningPromptOverride.value !== null ? [] : null)
    form.itemCount = Number(options.itemCount || form.itemCount)
    form.summaryLength = options.summaryLength || form.summaryLength
    form.hotAnalysis = options.hotAnalysis !== false
    form.duplicateMerge = options.duplicateMerge !== false
    if (Array.isArray(config.period)) {
      if (form.type === '周报') form.period = config.period.map(parseCalendarDate)
      else form.month = parseCalendarDate(config.period[0])
    }
    ElMessage.success('已载入原简报配置，请按本期规则重新复筛')
  } catch (error) {
    if (!stopped && generation === sourceTaskGeneration) sourceTaskError.value = error?.msg || error?.message || '原简报配置加载失败，请重试后再确认候选范围'
  } finally {
    if (!stopped && generation === sourceTaskGeneration) {
      sourceTaskLoading.value = false
    }
  }
}
watch(() => draftQuery.value.sourceTask, () => {
  activeStep.value = 0
  clearScreening()
  void loadSourceTask()
})
function formatDate(value) {
  return calendarDate(value)
}
function buildReportPeriod() {
  if (form.type === '周报') {
    const period = (form.period || []).map(formatDate).filter(Boolean)
    return { period, label: period.length === 2 && period[0] <= period[1] ? `${period[0]} 至 ${period[1]}` : '' }
  }
  if (!form.month) return { period: [], label: '' }
  const month = new Date(form.month)
  if (Number.isNaN(month.getTime())) return { period: [], label: '' }
  const year = month.getFullYear()
  const monthIndex = month.getMonth()
  return {
    period: [formatDate(new Date(year, monthIndex, 1)), formatDate(new Date(year, monthIndex + 1, 0))],
    label: `${year}年${monthIndex + 1}月`
  }
}
async function createDigest() {
  if (submitting.value) return
  if (!canGenerate.value) return
  submitting.value = true
  const session = portalStore.workspaceEpoch
  try {
    const payload = buildDigestPayload()
    const requestId = ensureRequestId(payload)
    const res = await createPipelineResearchJob({ ...payload, requestId })
    if (stopped || session !== portalStore.workspaceEpoch) return
    portalStore.registerGenerationTask(res.data)
    await portalStore.hydrate(true)
    if (stopped || session !== portalStore.workspaceEpoch) return
    ElMessage.success(`${form.type}任务已进入后台生成队列，切换页面后会继续生成，完成后将提醒查看`)
    if (isCurrentVisit()) router.push(`/portal/research/tasks/${res.data.jobId || res.data.id}`)
  } catch (error) {
    if (stopped || session !== portalStore.workspaceEpoch) return
    const recovered = await recoverScreeningError(error)
    if (!recovered && !stopped && session === portalStore.workspaceEpoch) ElMessage.error(error?.msg || error?.message || `${form.type}创建失败，请确认后端和数据库已启动`)
  } finally {
    submitting.value = false
  }
}
function buildDigestPayload() {
  if (!['周报', '月报'].includes(form.type)) throw new Error('仅支持新建周报或月报')
  if (!canGenerate.value) throw new Error(capacityNotice.value || '请先完成系统筛选')
  if (form.templateId && templateUnavailable.value) throw new Error('请选择可用的简报模板')
  const reportType = currentTypeConfig.value.reportType
  const { period, label } = buildReportPeriod()
  if (!period.length || period.length !== 2 || period[0] > period.at(-1)) throw new Error(`请选择完整且有效的${periodFieldLabel.value}`)
  return {
      title: `科技情报${form.type} ${label}`.trim(),
      reportType,
      screeningId: screeningId.value,
      ...(form.templateId ? { templateId: requireBusinessId(form.templateId) } : {}),
      period,
      requirements: `报告周期：${label}；每栏 ${form.itemCount} 条；摘要长度：${form.summaryLength}`,
      citationCheck: true,
      options: { cadence: reportType, summaryLength: form.summaryLength, itemCount: form.itemCount, hotAnalysis: form.hotAnalysis, duplicateMerge: form.duplicateMerge }
  }
}
onMounted(async () => {
  await loadTemplates()
  await loadSourceTask()
})
</script>

<style scoped>
.ps-digest-create-page.is-configuring { overflow-y: auto; }
.ps-digest-create-page .ps-create-context {
  width: 100%;
  max-width: none;
  grid-template-columns: auto minmax(0, 1fr) minmax(300px, 380px);
  gap: 10px;
  border-bottom: 0;
  padding-block: 4px;
}
.ps-create-context h1 { font-size: 24px; }
.ps-create-context .ps-create-back { grid-column: auto; }
.ps-create-context .ps-create-steps { width: 100%; padding: 0; background: transparent; }
.ps-create-steps :deep(.el-step.is-simple .el-step__title) { max-width: none; white-space: nowrap; font-size: 14px; line-height: 24px; }
.ps-create-steps :deep(.el-step.is-simple .el-step__head) { padding-right: 6px; }
.ps-create-steps :deep(.el-step__title.is-process), .ps-create-steps :deep(.el-step__head.is-process) { color: var(--ps-blue); border-color: currentColor; }
.ps-create-steps :deep(.el-step__icon.is-icon) { width: 20px; height: 20px; border: 1px solid currentColor; border-radius: 50%; font-size: 12px; font-weight: 600; }
.ps-create-steps :deep(.is-process .el-step__icon.is-icon) { background: var(--ps-blue); color: #fff; border-color: var(--ps-blue); }
.ps-create-steps :deep(.el-step__arrow::before) { width: 16px; height: 1px; transform: none; }
.ps-create-steps :deep(.el-step__arrow::after) { display: none; }
.ps-digest-create-page > .ps-step-card { width: 100%; max-width: none; }
.ps-digest-create-page .ps-step-content { padding: 18px 20px; }
.ps-digest-create-page > .ps-step-card > .ps-step-content.ps-digest-confirm { flex: 0 1 auto; }
.ps-digest-create-page .ps-step-footer {
  display: flex;
  min-height: 54px;
  gap: 8px;
  padding: 8px 16px;
  flex-shrink: 0;
}
.ps-step-footer :deep(.el-button) { margin: 0; }
.ps-digest-footer-spacer { flex: 1; }
.ps-digest-create-page .ps-form-grid { gap: 14px 18px; }
.ps-digest-create-page .ps-digest-config-fields { grid-template-columns: auto minmax(0, 1fr) minmax(0, 1fr); align-items: end; }
.ps-digest-type-field { display: grid; gap: 8px; align-self: stretch; align-content: space-between; font-size: 13px; font-weight: 650; color: var(--ps-ink-2); }
.ps-digest-type-field :deep(.el-radio-button__inner) { min-height: 40px; display: inline-flex; align-items: center; padding-inline: 19px; }
.ps-digest-create-page .ps-form-grid > label { min-width: 0; }
.ps-digest-create-page .ps-form-grid :deep(.el-date-editor) { min-width: 0; max-width: 100%; }
.ps-digest-config-fields :deep(.el-date-editor--month) { height: auto; }
.ps-digest-rule-note { font-size: 13px; color: var(--ps-muted); }
.ps-digest-confirm h2 { margin: 0 0 10px; font-size: 15px; color: var(--ps-ink); }
.ps-digest-screening-status {
  display: grid;
  gap: 10px;
  margin-bottom: 18px;
  padding: 14px 16px;
  background: var(--ps-blue-soft);
  border-radius: 8px;
  font-size: 13px;
  color: var(--ps-muted);
}
.ps-digest-confirm > section[aria-labelledby] { margin-top: 20px; }
.ps-digest-screening-rule { margin-top: 18px; }
.ps-digest-create-page.is-configuring > .ps-step-card { flex: 0 0 auto; }
.ps-digest-create-page.is-configuring .ps-step-content { flex: 0 0 auto; overflow: visible; }
.ps-digest-create-page .ps-option-row { margin-top: 10px; padding: 0; background: transparent; flex-wrap: wrap; }
@media (min-width: 761px) and (min-height: 641px) {
  .ps-digest-create-page:not(.is-configuring) > .ps-step-card { flex: 0 1 auto; }
}
@media (max-width: 920px) {
  .ps-digest-create-page .ps-digest-config-fields { grid-template-columns: auto minmax(0, 1fr); }
  .ps-digest-config-fields > label:last-child { grid-column: 1 / -1; }
}
@media (max-width: 760px), (max-height: 640px) {
  .ps-digest-create-page > .ps-step-card { flex: 0 0 auto; }
  .ps-digest-create-page .ps-step-content { flex: 0 0 auto; padding: 14px; }
  .ps-digest-create-page .ps-create-steps :deep(.el-step__title) { font-size: 13px; }
}
@media (max-width: 540px) {
  .ps-digest-create-page .ps-create-context { grid-template-columns: auto minmax(0, 1fr); }
  .ps-create-context .ps-create-steps { grid-column: 1 / -1; padding: 6px 0; }
  .ps-digest-create-page .ps-form-grid { grid-template-columns: 1fr; }
  .ps-digest-create-page .ps-step-footer:has(.ps-digest-rule-note) { flex-wrap: wrap; }
  .ps-digest-rule-note { width: 100%; line-height: 1.5; }
  :global(.ps-digest-period-popper .el-date-range-picker) {
    width: min(350px, calc(100vw - 24px));
    max-height: 48dvh;
    overflow-y: auto;
  }
  :global(.ps-digest-period-popper .el-picker-panel__body) { min-width: 0; }
  :global(.ps-digest-period-popper .el-date-range-picker__content) { display: block; width: 100%; }
}
</style>
