<template>
  <div class="ps-page ps-create-page ps-digest-create-page">
    <header class="ps-create-context">
      <button class="ps-create-back" type="button" aria-label="返回情报简报" title="返回情报简报" @click="router.push('/portal/digests')">
        <Back />
      </button>
      <div class="ps-create-heading"><h1>新建简报</h1></div>
    </header>
    <section class="ps-panel ps-digest-filters" aria-label="筛选简报资料">
        <div class="ps-form-grid ps-digest-filter-grid">
          <label>报告类型
            <el-radio-group v-model="form.type">
              <el-radio-button value="日报">日报</el-radio-button>
              <el-radio-button value="周报">周报</el-radio-button>
              <el-radio-button value="月报">月报</el-radio-button>
            </el-radio-group>
          </label>
          <label>{{ periodFieldLabel }}
            <el-date-picker v-if="form.type === '日报'" v-model="form.date" type="date" placeholder="选择报告日期" />
            <el-date-picker v-else-if="form.type === '周报'" v-model="form.period" type="daterange" start-placeholder="开始日期" end-placeholder="结束日期" />
            <el-date-picker v-else v-model="form.month" type="month" placeholder="选择报告月份" />
          </label>
          <label>来源范围<el-select v-model="form.sources" multiple collapse-tags collapse-tags-tooltip :max-collapse-tags="2"><el-option label="新闻网站" value="新闻网站" /><el-option label="微信公众号" value="微信公众号" /></el-select></label>
          <label class="ps-digest-direction-field">技术方向<el-select v-model="form.directions" multiple collapse-tags collapse-tags-tooltip :max-collapse-tags="2"><el-option v-for="item in ['管网安全', '检测技术', '腐蚀防护', '应力监测', '数字孪生']" :key="item" :label="item" :value="item" /></el-select></label>
          <label class="ps-digest-keyword-field">关键词<el-select v-model="form.keywords" multiple allow-create filterable collapse-tags collapse-tags-tooltip :max-collapse-tags="2"><el-option v-for="item in ['完整性管理', '缺陷识别', '应力监测']" :key="item" :label="item" :value="item" /></el-select></label>
        </div>
    </section>
        <section class="ps-panel ps-digest-candidates" :aria-busy="refreshing">
          <div class="ps-section-head" title="已按筛选条件检索，重复标题仅保留一篇"><h2>候选资料</h2><span role="status">已选 {{ selectedCandidateIds.length }} / {{ DIGEST_SELECTION_LIMIT }} 篇</span></div>
          <div v-if="candidateItems.length" class="ps-digest-candidate-tools">
            <el-button text :disabled="submitting || refreshing || Boolean(previewError)" @click="selectCurrentPage">{{ currentCandidatePageSelected ? '取消当前页选择' : '全选当前页' }}</el-button>
          </div>
          <div class="ps-digest-candidate-scroll">
          <p v-if="selectionNotice" role="status">{{ selectionNotice }}</p>
          <p v-if="sourceTaskLoading || sourceTaskError" role="status">{{ sourceTaskLoading ? '正在载入原简报配置…' : sourceTaskError }} <el-button v-if="sourceTaskError" text @click="loadSourceTask">重试载入</el-button></p>
          <p v-if="refreshing" role="status">加载中…</p>
          <div v-else-if="previewError" class="ps-inline-state is-warning" role="alert"><span>{{ previewError }}</span><el-button text @click="refreshPreview">重试</el-button></div>
          <template v-if="!refreshing">
            <p v-if="previewTruncated" role="status">结果较多，请缩小筛选范围。</p>
            <div v-for="item in candidateItems" :key="item.id" class="ps-material-option"><el-checkbox :model-value="selectedCandidateIds.includes(item.id)" :aria-label="`选择简报资讯：${item.title}`" :disabled="submitting" @change="toggleCandidate(item.id, $event)" /><span><strong>{{ item.title }}</strong><small>{{ item.meta }}</small></span></div>
            <p v-if="!candidateItems.length && !previewError" class="ps-inspector-empty">暂无匹配资料，请调整日期或筛选条件</p>
          </template>
          </div>
          <div v-if="previewTotal > 0" class="ps-pagination ps-digest-candidate-pagination" aria-label="简报资料列表分页">
            <el-pagination v-model:current-page="previewPage" v-model:page-size="previewPageSize" :page-sizes="[10, 20, 50]" :total="previewTotal" layout="total, sizes, ->, prev, pager, next, jumper" :pager-count="5" :disabled="submitting || refreshing" background aria-label="简报候选检索页" />
          </div>
        </section>
    <section class="ps-form-card ps-digest-settings">
        <div v-show="settingsExpanded" id="digest-generation-settings" class="ps-digest-config-body" role="region" aria-label="生成设置">
          <div class="ps-form-grid ps-digest-output-grid">
            <label>报告模板<el-select v-model="form.template"><el-option v-for="item in availableTemplates" :key="item.value" :label="item.label" :value="item.value" /></el-select></label>
            <label>每栏资讯数量<el-input-number v-model="form.itemCount" :min="3" :max="30" /></label>
            <label>单条摘要长度<el-select v-model="form.summaryLength"><el-option label="精简（80-120字）" value="short" /><el-option label="标准（150-200字）" value="normal" /><el-option label="深度（250-300字）" value="long" /></el-select></label>
          </div>
          <div class="ps-option-row"><el-checkbox v-model="form.hotAnalysis">包含热点分析</el-checkbox><el-checkbox v-model="form.duplicateMerge">合并重复事件</el-checkbox><el-checkbox v-model="form.schedule">创建自动计划</el-checkbox></div>
          <div v-if="form.schedule" class="ps-form-grid ps-digest-output-grid ps-digest-schedule-fields">
            <label>自动生成频率<el-select v-model="scheduleFrequency" aria-label="自动生成频率"><el-option label="每天（日报）" value="daily" /><el-option label="每周（周报）" value="weekly" /><el-option label="每月（月报）" value="monthly" /></el-select></label>
            <label v-if="scheduleFrequency === 'weekly'">每周生成日<el-select v-model="form.scheduleWeekday" aria-label="每周生成日"><el-option v-for="(day, index) in weekdayLabels" :key="index" :label="day" :value="index" /></el-select></label>
            <label v-if="scheduleFrequency === 'monthly'">每月生成日<el-select v-model="form.scheduleMonthDay" aria-label="每月生成日"><el-option v-for="day in 31" :key="day" :label="`${day}日`" :value="day" /></el-select><small class="ps-schedule-day-note">当月不足所选日期时，在当月最后一天执行。</small></label>
            <label>{{ scheduleTimeLabel }}<el-time-select v-model="form.scheduleTime" :aria-label="scheduleTimeLabel" start="00:00" step="00:30" end="23:30" /></label>
            <label>节假日策略<el-select v-model="form.holidayPolicy"><el-option label="节假日照常执行" value="run" /><el-option label="节假日跳过执行" value="skip" /></el-select></label>
            <label>节假日日期<el-input v-model="form.holidayDates" placeholder="日期用逗号分隔，如 2026-10-01" /></label>
          </div>
        </div>
      <p v-if="templatesLoading" class="ps-digest-template-notice" role="status">正在加载已发布简报模板…</p>
      <div v-else-if="templatesError" class="ps-inline-state is-warning" role="alert"><span>{{ templatesError }}</span><el-button text @click="loadTemplates">重新加载模板</el-button></div>
      <p v-else-if="!availableTemplates.length" class="ps-digest-template-notice" role="status">当前报告类型暂无启用模板，请联系管理员配置。</p>
      <el-alert v-if="form.template && !decimalId(form.template)" :title="ID_UPGRADE_NOTICE" type="warning" :closable="false" show-icon />
      <el-alert v-if="templateOptions.find(item => item.value === form.template) && templateGenerationError(templateOptions.find(item => item.value === form.template))" :title="templateGenerationError(templateOptions.find(item => item.value === form.template))" type="warning" :closable="false" show-icon />
      <footer class="ps-form-footer ps-digest-submit">
        <button type="button" class="ps-digest-settings-toggle" :aria-expanded="settingsExpanded" aria-controls="digest-generation-settings" @click="settingsExpanded = !settingsExpanded"><span aria-hidden="true">›</span>生成设置</button>
        <div class="ps-digest-submit-actions"><el-button @click="router.push('/portal/digests')">取消</el-button><el-button type="primary" :loading="submitting" :disabled="templatesLoading || !availableTemplates.length || refreshing || Boolean(previewError) || !selectedCandidateIds.length || sourceTaskLoading || Boolean(sourceTaskError)" @click="createDigest">开始生成</el-button></div>
      </footer>
    </section>
  </div>
</template>

<script setup>
import { displayId, decimalId, requireBusinessId, ID_UPGRADE_NOTICE } from '@/utils/portal/businessId'
import { templateGenerationError } from '@/utils/pipeline/compactContract'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { calendarDate, parseCalendarDate } from '@/utils/portal/businessTime'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back } from '@element-plus/icons-vue'
import usePortalStore from '@/store/modules/portal'
import { createPipelineDigestSchedule, createPipelineResearchJob, getPipelineIntelligenceDetail, getPipelineResearchJob, listPipelineTemplates, searchPipelineDigestCandidates } from '@/api/pipeline/intelligence'
import { DIGEST_SELECTION_LIMIT, digestCandidate, fetchDigestPage, mapEvidence, preciseDate, verifyEvidence } from '@/utils/portal/evidenceInput'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const refreshing = ref(false)
const previewError = ref('')
const settingsExpanded = ref(false)
const previewPage = ref(1)
const previewPageSize = ref(10)
const previewPageKey = computed(() => `${previewPageSize.value}:${previewPage.value}`)
const previewPages = ref({})
const selectedCandidateIds = ref([])
function acceptSelection(ids) {
  if (ids.length > DIGEST_SELECTION_LIMIT) {
    selectionNotice.value = `每份简报最多选择 ${DIGEST_SELECTION_LIMIT} 篇资料，本次未增加勾选，请减少选择后重试。`
    ElMessage.warning(selectionNotice.value)
    return
  }
  selectedCandidateIds.value = [...new Set(ids.map(displayId))]
  selectionNotice.value = ''
}
function toggleCandidate(id, checked) {
  id = displayId(id)
  if (submitting.value) return
  if (checked) acceptSelection([...new Set([...selectedCandidateIds.value, id])])
  else removeCandidate(id)
}
const selectionNotice = ref('')
const previewPageCount = ref(1)
const previewTotal = ref(0)
const previewTruncated = ref(false)
const sourceTaskLoading = ref(false)
const sourceTaskError = ref('')
let previewGeneration = 0
let sourceTaskGeneration = 0
let initialized = false
let stopped = false
let previewRefreshQueued = false
onBeforeUnmount(() => { stopped = true; previewGeneration += 1; sourceTaskGeneration += 1 })
const submitting = ref(false)
const requestId = ref('')
let requestFingerprint = ''
const reportTypeConfigs = {
  日报: { reportType: 'daily', periodLabel: '报告日期', leadTitle: '今日要闻', hotTitle: '热点研判', itemCount: 8 },
  周报: { reportType: 'weekly', periodLabel: '报告周期', leadTitle: '本周要闻', hotTitle: '周度趋势研判', itemCount: 10 },
  月报: { reportType: 'monthly', periodLabel: '报告月份', leadTitle: '月度要闻', hotTitle: '月度趋势研判', itemCount: 15 }
}
const templateOptions = ref([])
const templatesLoading = ref(false)
const templatesError = ref('')
const initialType = ({ 日报: '日报', 周报: '周报', 月报: '月报' })[String(route.query.type || '')] || '日报'
const form = reactive({ type: initialType, date: new Date(), period: [], month: new Date(), directions: ['检测技术', '应力监测', '管网安全'], sources: ['新闻网站', '微信公众号'], keywords: ['完整性管理'], template: String(route.query.template || ''), itemCount: 8, summaryLength: 'normal', hotAnalysis: true, duplicateMerge: true, schedule: false, scheduleTime: '08:00', scheduleWeekday: 0, scheduleMonthDay: 1, holidayPolicy: 'run', holidayDates: '' })
const currentTypeConfig = computed(() => reportTypeConfigs[form.type])
const scheduleFrequency = computed({
  get: () => currentTypeConfig.value.reportType,
  set: value => {
    const type = { daily: '日报', weekly: '周报', monthly: '月报' }[value]
    if (type) form.type = type
  }
})
const weekdayLabels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const scheduleTimeLabel = computed(() => ({ daily: '每天执行时间', weekly: `每${weekdayLabels[form.scheduleWeekday]}执行时间`, monthly: `每月${form.scheduleMonthDay}日执行时间` })[scheduleFrequency.value])
const periodFieldLabel = computed(() => currentTypeConfig.value.periodLabel)
const availableTemplates = computed(() => templateOptions.value.filter(item => (item.type === '通用' || item.type === form.type)))
const previewScope = computed(() => ({ period: buildReportPeriod().period, directions: [...form.directions], keywords: [...form.keywords], sources: [...form.sources] }))
const scopeKey = computed(() => JSON.stringify(previewScope.value))
const candidateItems = computed(() => previewPages.value[previewPageKey.value]?.rows || [])
const currentCandidatePageSelected = computed(() => candidateItems.value.length > 0
  && candidateItems.value.every(item => selectedCandidateIds.value.includes(item.id)))
const checkedCandidates = computed(() => [...new Map(Object.values(previewPages.value).flatMap(page => page.rows).map(item => [item.id, item])).values()])
const selectedCandidates = computed(() => selectedCandidateIds.value.map(id => checkedCandidates.value.find(item => item.id === id) || { id, title: `选材 ${id}（尚未通过当前候选核验）`, ready: false }))
function ensureRequestId(payload) {
  const fingerprint = JSON.stringify(payload)
  if (!requestId.value || requestFingerprint !== fingerprint) {
    requestId.value = globalThis.crypto?.randomUUID?.() || `digest-${Date.now()}-${Math.random().toString(16).slice(2)}`
    requestFingerprint = fingerprint
  }
  return requestId.value
}
const columnSuggestions = computed(() => [...new Set([currentTypeConfig.value.leadTitle, ...form.directions.map(item => `${item}动态`), ...(form.hotAnalysis ? [currentTypeConfig.value.hotTitle] : []), ...(form.type === '月报' ? ['风险与机会', '下月关注'] : [])])])
watch(() => form.type, type => {
  const options = templateOptions.value.filter(item => item.type === '通用' || item.type === type)
  if (!form.template || templateOptions.value.some(item => item.value === form.template)) form.template = options[0]?.value || ''
  form.itemCount = reportTypeConfigs[type].itemCount
})
watch(() => route.query.template, value => { if (value !== undefined) form.template = String(value) })
function selectTemplateForType() {
  const options = templateOptions.value.filter(item => item.type === '通用' || item.type === form.type)
  if (!form.template) form.template = options[0]?.value || ''
}
async function refreshPreview() {
  const generation = ++previewGeneration
  const session = portalStore.workspaceEpoch
  const key = scopeKey.value
  const scope = JSON.parse(key)
  const page = previewPage.value
  const pageSize = previewPageSize.value
  const pageKey = previewPageKey.value
  refreshing.value = true
  previewError.value = ''
  const retained = { ...previewPages.value }; delete retained[pageKey]; previewPages.value = retained
  try {
    const result = await fetchDigestPage(scope, { search: searchPipelineDigestCandidates, getIntelligence: getPipelineIntelligenceDetail }, page, pageSize)
    if (stopped || generation !== previewGeneration || session !== portalStore.workspaceEpoch || key !== scopeKey.value) return
    const next = { ...previewPages.value, [pageKey]: result }
    previewPages.value = next
    previewPageCount.value = result.pageCount
    previewTotal.value = result.total
    previewTruncated.value = result.truncated
    const validIds = new Set(checkedCandidates.value.map(item => item.id))
    const missing = selectedCandidateIds.value.filter(id => !validIds.has(id))
    if (missing.length) previewError.value = `已选资料 ${missing.join('、')} 不再匹配或已失效，请移除或重新核验。`
  } catch (error) {
    if (!stopped && generation === previewGeneration && session === portalStore.workspaceEpoch) previewError.value = error?.msg || error?.message || '候选核验失败，请重试'
  } finally {
    if (!stopped && generation === previewGeneration) refreshing.value = false
  }
}
watch([scopeKey, previewPage, previewPageSize], ([key, , pageSize], previous) => {
  previewGeneration += 1
  if (key !== previous?.[0]) {
    if (selectedCandidateIds.value.length) selectionNotice.value = '覆盖期或筛选条件已变化，原选择已清空，请按当前条件重新选材。'
    previewPage.value = 1; previewPages.value = {}; selectedCandidateIds.value = []; previewError.value = ''; previewPageCount.value = 1; previewTruncated.value = false
  } else if (pageSize !== previous?.[2]) {
    previewPage.value = 1
  }
  if (initialized) refreshing.value = true
  if (!previewRefreshQueued) {
    previewRefreshQueued = true
    void nextTick().then(() => {
      previewRefreshQueued = false
      if (!stopped && initialized && !sourceTaskLoading.value) void refreshPreview()
    })
  }
}, { flush: 'sync' })
function selectCurrentPage() {
  if (submitting.value || refreshing.value || previewError.value) return
  const pageIds = new Set(candidateItems.value.map(item => item.id))
  acceptSelection(currentCandidatePageSelected.value
    ? selectedCandidateIds.value.filter(id => !pageIds.has(id))
    : [...new Set([...selectedCandidateIds.value, ...pageIds])])
}
function removeCandidate(id) {
  selectedCandidateIds.value = selectedCandidateIds.value.filter(item => item !== id)
  if (previewError.value.startsWith('已选资料') && selectedCandidates.value.every(item => item.ready)) previewError.value = ''
}
async function loadSourceTask() {
  if (!route.query.sourceTask) return
  if (!decimalId(route.query.sourceTask)) { sourceTaskError.value = ID_UPGRADE_NOTICE; return }
  const generation = ++sourceTaskGeneration
  const session = portalStore.workspaceEpoch
  sourceTaskLoading.value = true
  sourceTaskError.value = ''
  try {
    const res = await getPipelineResearchJob(String(route.query.sourceTask))
    if (stopped || generation !== sourceTaskGeneration || session !== portalStore.workspaceEpoch) return
    const task = res.data || {}
    const config = task.config || {}
    const reportType = task.type || config.reportType || config.report_type
    const typeMap = { daily: '日报', weekly: '周报', monthly: '月报' }
    if (typeMap[reportType]) form.type = typeMap[reportType]
    await Promise.resolve()
    const options = config.options || {}
    form.template = config.templateId || config.template_id || form.template
    form.directions = String(config.direction || '').split('、').filter(Boolean)
    form.keywords = Array.isArray(config.keywords) ? [...config.keywords] : []
    form.sources = Array.isArray(options.sources) ? options.sources.filter(source => ['新闻网站', '微信公众号'].includes(source)) : ['新闻网站', '微信公众号']
    form.itemCount = Number(options.itemCount || form.itemCount)
    form.summaryLength = options.summaryLength || form.summaryLength
    form.hotAnalysis = options.hotAnalysis !== false
    form.duplicateMerge = options.duplicateMerge !== false
    if (Array.isArray(config.period)) {
      if (form.type === '日报') form.date = parseCalendarDate(config.period[0])
      else if (form.type === '周报') form.period = config.period.map(parseCalendarDate)
      else form.month = parseCalendarDate(config.period[0])
    }
    ElMessage.success('已载入原简报配置，请重新核对周期候选并明确选择资料')
  } catch (error) {
    if (!stopped && generation === sourceTaskGeneration) sourceTaskError.value = error?.msg || '原简报配置加载失败，请重试后再确认候选范围'
  } finally {
    if (!stopped && generation === sourceTaskGeneration) {
      sourceTaskLoading.value = false
      if (initialized && !sourceTaskError.value) void refreshPreview()
    }
  }
}
watch(() => route.query.sourceTask, () => { void loadSourceTask() })
function formatDate(value) {
  return calendarDate(value)
}
function buildReportPeriod() {
  if (form.type === '日报') {
    const value = formatDate(form.date)
    const date = new Date(form.date)
    return { period: value ? [value] : [], label: value ? `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日` : '' }
  }
  if (form.type === '周报') {
    const period = (form.period || []).map(formatDate).filter(Boolean)
    return { period, label: period.length === 2 ? `${period[0]} 至 ${period[1]}` : '' }
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
  if (form.template && !decimalId(form.template)) return ElMessage.warning(ID_UPGRADE_NOTICE)
  if (selectedCandidateIds.value.length > DIGEST_SELECTION_LIMIT) return ElMessage.warning(`每份简报最多选择 ${DIGEST_SELECTION_LIMIT} 篇资料，请减少勾选`)
  if (refreshing.value || previewError.value || sourceTaskLoading.value || sourceTaskError.value) return ElMessage.warning('请先完成候选核验并处理加载失败')
  if (!selectedCandidateIds.value.length) return ElMessage.warning('请明确选择用于生成的候选资料')
  const selectedTemplate = templateOptions.value.find(item => item.value === form.template)
  if (!selectedTemplate) return ElMessage.warning('当前报告类型没有可用的启用模板')
  const modelError = templateGenerationError(selectedTemplate)
  if (modelError) return ElMessage.warning(modelError)
  submitting.value = true
  try {
    const key = scopeKey.value
    const ids = [...selectedCandidateIds.value]
    const session = portalStore.workspaceEpoch
    const checked = await mapEvidence(ids, id => verifyEvidence({ id, type: 'article' }, { getIntelligence: getPipelineIntelligenceDetail }))
    if (stopped || key !== scopeKey.value || session !== portalStore.workspaceEpoch || JSON.stringify(ids) !== JSON.stringify(selectedCandidateIds.value)) return ElMessage.warning('周期、账号或选材已变化，请重新确认')
    const failed = checked.filter(item => !item.ready || !digestCandidate(item.detail, previewScope.value))
    if (failed.length) { previewError.value = `已选资料核验失败或已不匹配：${failed.map(item => `${item.id}（${item.reason || '日期或来源不匹配'}）`).join('；')}`; return }
    const payload = buildDigestPayload()
    const reportType = currentTypeConfig.value.reportType
    const requestId = ensureRequestId(payload)
    const res = await createPipelineResearchJob({ ...payload, requestId })
    if (form.schedule) {
      try {
        await createPipelineDigestSchedule({
          name: `${form.type}自动计划 - ${form.directions[0] || '管网科技情报'}`,
          requestId,
          reportType,
          templateId: requireBusinessId(form.template),
          templateVersion: selectedTemplate?.version || '',
          scheduleTime: form.scheduleTime,
          scheduleWeekday: form.scheduleWeekday,
          scheduleMonthDay: form.scheduleMonthDay,
          holidayPolicy: form.holidayPolicy,
          holidayDates: form.holidayDates.split(',').map(item => item.trim()).filter(Boolean),
          direction: form.directions.join('、'),
          keywords: form.keywords,
          requirements: payload.requirements,
          outline: payload.outline,
          options: { ...payload.options, sources: form.sources }
        })
      } catch (error) {
        await portalStore.hydrate(true)
        ElMessage.warning(`任务已入队，但自动计划保存失败：${error?.msg || '请稍后在自动任务中重新创建'}`)
        router.push(`/portal/research/tasks/${res.data.jobId || res.data.id}`)
        return
      }
    }
    await portalStore.hydrate(true)
    ElMessage.success(form.schedule ? `${form.type}任务已入队，自动计划也已保存` : `${form.type}任务已进入后台生成队列`)
    router.push(`/portal/research/tasks/${res.data.jobId || res.data.id}`)
  } catch (error) {
    ElMessage.error(error?.msg || error?.message || `${form.type}创建失败，请确认后端和数据库已启动`)
  } finally {
    submitting.value = false
  }
}
function buildDigestPayload() {
  if (form.template && !decimalId(form.template)) throw new Error(ID_UPGRADE_NOTICE)
  if (selectedCandidateIds.value.length > DIGEST_SELECTION_LIMIT) throw new Error(`每份简报最多选择 ${DIGEST_SELECTION_LIMIT} 篇资料，请减少勾选`)
  if (refreshing.value || previewError.value || sourceTaskLoading.value || sourceTaskError.value) throw new Error('候选核验尚未完成或加载失败')
  if (!selectedCandidateIds.value.length || selectedCandidates.value.some(item => !item.ready)) throw new Error('存在未核验的已选资料')
  const reportType = currentTypeConfig.value.reportType
  const { period, label } = buildReportPeriod()
  if (!period.length || (reportType !== 'daily' && period.length !== 2) || period[0] > period.at(-1)) throw new Error(`请选择完整且有效的${periodFieldLabel.value}`)
  const selectedTemplate = templateOptions.value.find(item => item.value === form.template)
  if (!selectedTemplate) throw new Error('请选择有效的启用模板')
  const modelError = templateGenerationError(selectedTemplate)
  if (modelError) throw new Error(modelError)
  return {
      title: `管网科技情报${form.type} ${label}`.trim(),
      reportType,
      templateId: requireBusinessId(form.template),
      templateVersion: selectedTemplate?.version || '版本待补充',
      direction: form.directions.join('、'),
      period,
      keywords: form.keywords,
      requirements: `报告周期：${label}；来源范围：${form.sources.join('、')}；每栏 ${form.itemCount} 条；摘要长度：${form.summaryLength}`,
      citationCheck: true,
      outline: columnSuggestions.value.map((title, index) => ({ id: index + 1, title, words: form.summaryLength === 'long' ? 1800 : 1200 })),
      selectedItemIds: selectedCandidateIds.value.map(requireBusinessId),
      options: { cadence: reportType, summaryLength: form.summaryLength, itemCount: form.itemCount, directions: [...form.directions], sources: [...form.sources], hotAnalysis: form.hotAnalysis, duplicateMerge: form.duplicateMerge, schedule: form.schedule }
  }
}
async function loadTemplates() {
  templatesLoading.value = true
  templatesError.value = ''
  try {
    const res = await listPipelineTemplates({ category: 'digest', publishedOnly: true })
    const typeMap = { daily: '日报', weekly: '周报', monthly: '月报' }
    templateOptions.value = (res.data?.rows || []).map(item => ({ ...item, type: typeMap[item.reportType] || '通用', label: item.name, value: displayId(item.id || item.templateKey), version: item.version || '' }))
    selectTemplateForType()
  } catch (error) {
    templateOptions.value = []
    templatesError.value = error?.msg || '模板服务暂时不可用，请稍后重试。'
  } finally {
    templatesLoading.value = false
  }
}

onMounted(async () => {
  await loadTemplates()
  await loadSourceTask()
  if (stopped) return
  await nextTick()
  initialized = true
  await refreshPreview()
})
</script>

<style scoped>
.ps-create-context { width: 100%; max-width: none; flex-shrink: 0; grid-template-columns: 44px minmax(0, 1fr); gap: 12px; align-items: center; margin-bottom: 0; padding-bottom: 12px; }
.ps-create-back { grid-column: auto; width: 44px; height: 44px; padding: 0; justify-content: center; border: 1px solid var(--ps-line); border-radius: 8px; background: #fff; }
.ps-create-back svg { width: 18px; height: 18px; }
.ps-create-back:hover { border-color: var(--ps-blue); background: var(--ps-blue-soft); }
.ps-create-back:hover svg { transform: none; }
.ps-create-heading h1 { font-size: 26px; }
.ps-digest-create-page { display: flex; flex-direction: column; gap: 12px; }
.ps-digest-create-page .ps-digest-filter-grid { grid-template-columns: repeat(6, minmax(0, 1fr)); }
.ps-digest-filter-grid > label { grid-column: span 2; min-width: 0; gap: 6px; }
.ps-digest-filter-grid > .ps-digest-direction-field, .ps-digest-filter-grid > .ps-digest-keyword-field { grid-column: span 3; }
.ps-digest-create-page .ps-digest-output-grid { grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr) minmax(0, 1fr); }
.ps-digest-create-page .ps-form-grid :deep(.el-date-editor), .ps-digest-create-page .ps-form-grid :deep(.el-input-number) { width: 100%; }
.ps-digest-candidate-scroll > .ps-inspector-empty { margin: 0; padding: 36px 16px; text-align: center; }
.ps-digest-settings-toggle { display: flex; align-items: center; flex-shrink: 0; gap: 8px; min-height: 44px; padding: 0; border: 0; background: transparent; color: var(--ps-ink); font: inherit; cursor: pointer; }
.ps-digest-settings-toggle > span { font-size: 22px; line-height: 1; }
.ps-digest-settings-toggle[aria-expanded="true"] > span { transform: rotate(90deg); }
.ps-digest-submit-actions { display: flex; align-items: center; flex-shrink: 0; gap: 8px; margin-left: auto; }
.ps-digest-template-notice { margin: 0; padding: 10px 20px; color: var(--ps-muted); }
.ps-digest-schedule-fields { margin-top: 12px; }
.ps-schedule-day-note { color: var(--ps-muted); font-size: 12px; font-weight: 400; line-height: 1.5; }
.ps-digest-create-page .ps-digest-schedule-fields { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.ps-digest-create-page .ps-digest-submit { position: sticky; bottom: 0; z-index: 10; display: flex; align-items: center; flex-wrap: nowrap; justify-content: space-between; gap: 16px; background: #fff; border: 0; border-radius: 10px; }
.ps-digest-settings:has(.ps-digest-settings-toggle[aria-expanded="true"]) .ps-digest-submit { border-top: 1px solid var(--ps-line); border-top-left-radius: 0; border-top-right-radius: 0; }
@media (max-width: 1050px) {
  .ps-digest-create-page .ps-digest-filter-grid, .ps-digest-create-page .ps-digest-output-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ps-digest-filter-grid > label, .ps-digest-filter-grid > .ps-digest-direction-field { grid-column: auto; }
  .ps-digest-filter-grid > .ps-digest-keyword-field { grid-column: 1 / -1; }
}
@media (max-width: 760px) {
  .ps-create-heading h1 { font-size: 22px; line-height: 1.4; }
  .ps-digest-create-page .ps-digest-submit { gap: 8px; padding-inline: 12px; }
}
@media (max-width: 600px) {
  .ps-digest-create-page .ps-digest-filter-grid, .ps-digest-create-page .ps-digest-output-grid, .ps-digest-create-page .ps-digest-schedule-fields { grid-template-columns: minmax(0, 1fr); }
  .ps-digest-filter-grid > label { grid-column: auto; }
}
</style>
