<template>
  <div class="ps-page ps-create-page">
    <PortalPageHeader title="新建简报" />
    <div class="ps-create-split">
      <section class="ps-form-card">
        <h2>报告配置</h2>
        <div class="ps-form-grid ps-form-grid-wide">
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
          <label>技术方向<el-select v-model="form.directions" multiple><el-option v-for="item in ['管网安全', '检测技术', '腐蚀防护', '应力监测', '数字孪生']" :key="item" :label="item" :value="item" /></el-select></label>
          <label>来源范围<el-select v-model="form.sources" multiple><el-option label="新闻网站" value="新闻网站" /><el-option label="微信公众号" value="微信公众号" /><el-option label="论文数据库" value="论文数据库" /></el-select></label>
          <label>关键词<el-select v-model="form.keywords" multiple allow-create filterable><el-option v-for="item in ['完整性管理', '缺陷识别', '应力监测']" :key="item" :label="item" :value="item" /></el-select></label>
          <label>报告模板<el-select v-model="form.template"><el-option v-for="item in availableTemplates" :key="item.value" :label="item.label" :value="item.value" /></el-select></label>
          <label>每栏资讯数量<el-input-number v-model="form.itemCount" :min="3" :max="30" /></label>
          <label>单条摘要长度<el-select v-model="form.summaryLength"><el-option label="精简（80-120字）" value="short" /><el-option label="标准（150-200字）" value="normal" /><el-option label="深度（250-300字）" value="long" /></el-select></label>
        </div>
        <div class="ps-option-row"><el-checkbox v-model="form.hotAnalysis">包含热点分析</el-checkbox><el-checkbox v-model="form.duplicateMerge">合并重复事件</el-checkbox><el-checkbox v-model="form.schedule" disabled>自动计划（调度服务未启用）</el-checkbox></div>
        <footer class="ps-form-footer"><span class="ps-form-note">创建完成后会自动保留初始版本</span><el-button @click="router.push('/portal/digests')">取消</el-button><el-button type="primary" :loading="submitting" @click="createDigest">开始生成</el-button></footer>
      </section>
      <aside class="ps-preview-sidebar"><section class="ps-panel"><div class="ps-section-head"><div><h2>候选内容预览</h2><small>根据当前来源、方向与关键词实时计算</small></div><el-button text :loading="refreshing" @click="refreshPreview"><Refresh />刷新</el-button></div><div class="ps-preview-metrics"><span><b>{{ previewMetrics.candidates }}</b>候选资讯</span><span><b>{{ previewMetrics.sources }}</b>内容来源</span><span><b>{{ previewMetrics.duplicates }}</b>疑似重复</span><span><b>{{ previewMetrics.directions }}</b>技术方向</span></div><div v-if="sourceDistribution.length" class="ps-source-bars"><div v-for="source in sourceDistribution" :key="source.name"><span>{{ source.name }}</span><i><span :style="{ width: source.rate + '%' }"></span></i><b>{{ source.count }}</b></div></div><p v-else class="ps-inspector-empty">当前筛选条件下没有候选内容</p></section><section class="ps-panel ps-gap-alert"><h3><Warning />数据缺口与覆盖</h3><p>{{ dataGap }}</p><el-button text type="primary" @click="expandSourceScope">扩大来源范围</el-button></section><section class="ps-panel"><h3>栏目建议</h3><ol><li v-for="item in columnSuggestions" :key="item">{{ item }}</li></ol></section></aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Warning } from '@element-plus/icons-vue'
import PortalPageHeader from '../components/PortalPageHeader.vue'
import usePortalStore from '@/store/modules/portal'
import { createPipelineResearchJob, getPipelineResearchJob, listPipelineTemplates } from '@/api/pipeline/intelligence'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const refreshing = ref(false)
const submitting = ref(false)
const reportTypeConfigs = {
  日报: { reportType: 'daily', periodLabel: '报告日期', leadTitle: '今日要闻', hotTitle: '热点研判', itemCount: 8 },
  周报: { reportType: 'weekly', periodLabel: '报告周期', leadTitle: '本周要闻', hotTitle: '周度趋势研判', itemCount: 10 },
  月报: { reportType: 'monthly', periodLabel: '报告月份', leadTitle: '月度要闻', hotTitle: '月度趋势研判', itemCount: 15 }
}
const templateOptions = ref([])
const form = reactive({ type: '日报', date: new Date(), period: [], month: new Date(), directions: ['检测技术', '应力监测', '管网安全'], sources: ['新闻网站', '微信公众号'], keywords: ['完整性管理'], template: 'daily-v2', itemCount: 8, summaryLength: 'normal', hotAnalysis: true, duplicateMerge: true, schedule: false })
const currentTypeConfig = computed(() => reportTypeConfigs[form.type])
const periodFieldLabel = computed(() => currentTypeConfig.value.periodLabel)
const availableTemplates = computed(() => templateOptions.value.filter(item => item.type === form.type))
const sourceItems = computed(() => [...portalStore.newsItems, ...portalStore.paperItems])
function isWithinSelectedPeriod(item) {
  const { period } = buildReportPeriod()
  if (!period.length) return false
  if (item.sourceType === '论文数据库') return false
  const timestamp = item.publishTime || item.time
  const published = new Date(timestamp)
  if (Number.isNaN(published.getTime())) return false
  const start = new Date(`${period[0]}T00:00:00`)
  const end = new Date(`${period[period.length - 1]}T00:00:00`)
  end.setDate(end.getDate() + 1)
  return published >= start && published < end
}
const candidateItems = computed(() => sourceItems.value.filter(item => {
  const searchText = [item.title, item.summary, item.category, ...(item.tags || [])].filter(Boolean).join(' ').toLocaleLowerCase('zh-CN')
  const sourceMatched = !form.sources.length || form.sources.includes(item.sourceType)
  const directionMatched = !form.directions.length || form.directions.some(direction => searchText.includes(direction.toLocaleLowerCase('zh-CN')))
  const keywordMatched = !form.keywords.length || form.keywords.some(keyword => searchText.includes(String(keyword).toLocaleLowerCase('zh-CN')))
  return sourceMatched && directionMatched && keywordMatched && isWithinSelectedPeriod(item)
}))
const sourceDistribution = computed(() => {
  const counts = new Map()
  candidateItems.value.forEach(item => counts.set(item.sourceType || item.source || '其他来源', (counts.get(item.sourceType || item.source || '其他来源') || 0) + 1))
  const max = Math.max(...counts.values(), 1)
  return [...counts.entries()].map(([name, count]) => ({ name, count, rate: Math.max(8, Math.round(count / max * 100)) })).sort((a, b) => b.count - a.count)
})
const previewMetrics = computed(() => {
  const sourceNames = new Set(candidateItems.value.map(item => item.source).filter(Boolean))
  const normalizedTitles = candidateItems.value.map(item => String(item.title || '').replace(/[\s，。、“”《》]/g, '').slice(0, 18)).filter(Boolean)
  const duplicates = normalizedTitles.length - new Set(normalizedTitles).size
  const directions = form.directions.filter(direction => candidateItems.value.some(item => `${item.title}${item.summary}${(item.tags || []).join('')}`.includes(direction))).length
  return { candidates: candidateItems.value.length, sources: sourceNames.size, duplicates, directions }
})
const dataGap = computed(() => {
  if (!candidateItems.value.length) return '当前条件没有检索到候选内容，请扩大来源范围或减少关键词。'
  const coverage = form.directions.map(direction => ({ direction, count: candidateItems.value.filter(item => `${item.title}${item.summary}${(item.tags || []).join('')}`.includes(direction)).length })).sort((a, b) => a.count - b.count)
  const weakest = coverage[0]
  return weakest && weakest.count < 2 ? `“${weakest.direction}”仅有 ${weakest.count} 条候选内容，建议补充来源后再形成独立栏目。` : '当前方向均有候选内容覆盖，创建后仍需在编辑器中复核来源。'
})
const columnSuggestions = computed(() => [...new Set([currentTypeConfig.value.leadTitle, ...form.directions.map(item => `${item}动态`), ...(form.hotAnalysis ? [currentTypeConfig.value.hotTitle] : []), ...(form.type === '月报' ? ['风险与机会', '下月关注'] : [])])])
watch(() => form.type, type => {
  const options = templateOptions.value.filter(item => item.type === type)
  form.template = options[0]?.value || ''
  form.itemCount = reportTypeConfigs[type].itemCount
})
async function refreshPreview() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await portalStore.hydrate(true)
    ElMessage.success(`已更新候选内容，共匹配 ${candidateItems.value.length} 条`)
  } catch (error) {
    ElMessage.error('候选内容刷新失败，请检查后端服务')
  } finally {
    refreshing.value = false
  }
}
async function loadSourceTask() {
  if (!route.query.sourceTask) return
  try {
    const res = await getPipelineResearchJob(String(route.query.sourceTask))
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
    form.itemCount = Number(options.itemCount || form.itemCount)
    form.summaryLength = options.summaryLength || form.summaryLength
    form.hotAnalysis = options.hotAnalysis !== false
    form.duplicateMerge = options.duplicateMerge !== false
    if (Array.isArray(config.period)) {
      if (form.type === '日报') form.date = new Date(config.period[0])
      else if (form.type === '周报') form.period = config.period.map(value => new Date(value))
      else form.month = new Date(config.period[0])
    }
    ElMessage.success('已载入原简报任务配置，可在生成前继续调整')
  } catch (error) {
    ElMessage.warning('原简报任务配置暂时无法加载，已按新任务处理')
  }
}
function expandSourceScope() { form.sources = ['新闻网站', '微信公众号', '论文数据库']; form.keywords = []; ElMessage.success('已扩大来源范围并清空关键词限制') }
function formatDate(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
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
  if (!candidateItems.value.length) return ElMessage.warning('当前条件没有可用于生成的候选内容')
  submitting.value = true
  try {
    const reportType = currentTypeConfig.value.reportType
    const { period, label } = buildReportPeriod()
    if (!period.length || (reportType !== 'daily' && period.length !== 2)) return ElMessage.warning(`请选择完整的${periodFieldLabel.value}`)
    const selectedTemplate = templateOptions.value.find(item => item.value === form.template)
    const res = await createPipelineResearchJob({
      title: `管网科技情报${form.type} ${label}`.trim(),
      reportType,
      templateId: form.template,
      templateVersion: selectedTemplate?.version || 'V1.0',
      direction: form.directions.join('、'),
      period,
      keywords: form.keywords,
      requirements: `报告周期：${label}；来源范围：${form.sources.join('、')}；每栏 ${form.itemCount} 条；摘要长度：${form.summaryLength}`,
      citationCheck: true,
      outline: columnSuggestions.value.map((title, index) => ({ id: index + 1, title, words: form.summaryLength === 'long' ? 1800 : 1200 })),
      selectedItemIds: candidateItems.value.slice(0, Math.max(form.itemCount * Math.max(form.directions.length, 1), form.itemCount)).map(item => item.id),
      options: { cadence: reportType, summaryLength: form.summaryLength, itemCount: form.itemCount, directions: form.directions, hotAnalysis: form.hotAnalysis, duplicateMerge: form.duplicateMerge, schedule: form.schedule }
    })
    await portalStore.hydrate(true)
    ElMessage.success(`${form.type}任务已进入后台生成队列`)
    router.push(`/portal/research/tasks/${res.data.jobId || res.data.id}`)
  } catch (error) {
    ElMessage.error(`${form.type}创建失败，请确认后端和数据库已启动`)
  } finally {
    submitting.value = false
  }
}
onMounted(async () => {
  try {
    const res = await listPipelineTemplates({ category: 'digest', publishedOnly: true })
    const typeMap = { daily: '日报', weekly: '周报', monthly: '月报' }
    templateOptions.value = (res.data?.rows || []).map(item => ({ type: typeMap[item.reportType] || '日报', label: `${item.name} ${item.version}`, value: item.templateKey, version: item.version }))
    if (!templateOptions.value.some(item => item.value === form.template)) form.template = templateOptions.value[0]?.value || form.template
  } catch (error) {
    ElMessage.warning('简报模板列表暂时无法加载')
  }
  await portalStore.hydrate()
  await loadSourceTask()
})
</script>
