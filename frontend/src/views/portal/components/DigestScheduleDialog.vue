<template>
  <el-dialog :model-value="modelValue" :title="record ? '编辑自动计划' : '新建自动计划'" width="min(820px, calc(100vw - 24px))" class="ps-schedule-dialog" :close-on-click-modal="false" :close-on-press-escape="!saving" :show-close="!saving" @update:model-value="close">
    <div v-loading="loading" class="ps-schedule-form">
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
      <p class="ps-schedule-intro">独立保存计划，不立即生成简报。每次执行时重新筛选资料，没有匹配文章则跳过。</p>
      <el-form label-position="top" :disabled="saving || loading" @submit.prevent="save">
        <div class="ps-schedule-fields">
          <el-form-item label="计划名称" class="is-wide"><el-input v-model="form.name" aria-label="计划名称" maxlength="255" placeholder="例如：管道检测每周简报" /></el-form-item>
          <el-form-item label="生成频率"><el-select v-model="form.frequency" aria-label="生成频率"><el-option label="每天（日报）" value="daily" /><el-option label="每周（周报）" value="weekly" /><el-option label="每月（月报）" value="monthly" /></el-select></el-form-item>
          <el-form-item label="执行时间 · 北京时间"><el-time-picker v-model="form.time" aria-label="执行时间" format="HH:mm" value-format="HH:mm" :clearable="false" /></el-form-item>
          <el-form-item v-if="form.frequency === 'weekly'" label="每周生成日"><el-select v-model="form.weekday" aria-label="每周生成日"><el-option v-for="(day, index) in weekdays" :key="index" :label="day" :value="index" /></el-select></el-form-item>
          <el-form-item v-if="form.frequency === 'monthly'" label="每月生成日"><el-select v-model="form.monthDay" aria-label="每月生成日"><el-option v-for="day in 31" :key="day" :label="`${day}日`" :value="day" /></el-select><small>当月不足所选日期时，月末执行。</small></el-form-item>
          <el-form-item label="报告模板" :class="{ 'is-wide': form.frequency === 'daily' }"><el-select v-model="form.templateId" aria-label="计划报告模板" placeholder="选择对应周期的模板"><el-option v-for="template in matchingTemplates" :key="template.id" :label="template.name" :value="String(template.id)" /></el-select><small v-if="!loading && !matchingTemplates.length">当前周期暂无已发布模板，请联系管理员配置。</small></el-form-item>
        </div>
        <h3>资料筛选</h3>
        <div class="ps-schedule-fields">
          <el-form-item label="来源范围"><el-select v-model="form.sources" aria-label="计划来源范围" multiple><el-option label="新闻网站" value="新闻网站" /><el-option label="微信公众号" value="微信公众号" /></el-select></el-form-item>
          <el-form-item label="文章类别"><el-select v-model="form.categories" aria-label="计划文章类别" multiple filterable clearable placeholder="全部类别" :multiple-limit="10"><el-option v-for="name in categories" :key="name" :label="name" :value="name" /><el-option v-for="name in missingCategories" :key="name" :label="`${name}（当前不可用）`" :value="name" disabled /></el-select></el-form-item>
          <el-form-item label="关键词" class="is-wide"><el-input-tag v-model="form.keywords" aria-label="计划关键词" :max="20" :maxlength="200" placeholder="输入后按回车添加，多个词命中任意一个即可" /><small>关键词、类别、来源与自动计算的报告周期共同筛选；关键词和类别留空表示不限。</small></el-form-item>
        </div>
        <h3>生成与执行</h3>
        <div class="ps-schedule-fields">
          <el-form-item label="每栏资讯数量"><el-input-number v-model="form.itemCount" aria-label="计划每栏资讯数量" :min="3" :max="30" /></el-form-item>
          <el-form-item label="摘要长度"><el-select v-model="form.summaryLength" aria-label="计划摘要长度"><el-option label="精简（80–120字）" value="short" /><el-option label="标准（150–200字）" value="normal" /><el-option label="深度（250–300字）" value="long" /></el-select></el-form-item>
          <el-form-item label="节假日策略"><el-select v-model="form.holidayPolicy" aria-label="计划节假日策略"><el-option label="照常执行" value="run" /><el-option label="指定节假日跳过" value="skip" /></el-select></el-form-item>
          <el-form-item label="指定节假日"><el-date-picker v-model="form.holidayDates" aria-label="计划节假日日期" type="dates" value-format="YYYY-MM-DD" placeholder="自行选择需要跳过的日期" /></el-form-item>
          <el-form-item label="生成要求" class="is-wide"><el-input v-model="form.requirements" aria-label="计划生成要求" type="textarea" :rows="2" maxlength="5000" placeholder="可选，不编造资料没有支持的结论" /></el-form-item>
        </div>
        <div class="ps-schedule-switches"><el-checkbox v-model="form.hotAnalysis">包含热点分析</el-checkbox><el-checkbox v-model="form.duplicateMerge">合并重复事件</el-checkbox><el-switch v-model="form.enabled" aria-label="保存后启用计划" active-text="保存后启用" inactive-text="停用保存" /></div>
      </el-form>
      <p class="ps-schedule-summary">{{ scheduleSummary(form) }} · {{ periodDescription }}</p>
    </div>
    <template #footer><el-button :disabled="saving" @click="close(false)">取消</el-button><el-button type="primary" :loading="saving" :disabled="loading || Boolean(loadError)" @click="save">保存计划</el-button></template>
  </el-dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import usePortalStore from '@/store/modules/portal'
import { createPipelineDigestSchedule, savePipelineDigestScheduleConfig, listPipelineTemplates, getPipelineContentFilters } from '@/api/pipeline/intelligence'
import { newScheduleForm, readScheduleForm, schedulePayload, scheduleSummary } from '@/utils/portal/digestScheduleEditor'

const props = defineProps({ modelValue: Boolean, record: { type: Object, default: null } })
const emit = defineEmits(['update:modelValue', 'saved'])
const store = usePortalStore()
const form = ref(newScheduleForm()), templates = ref([]), categories = ref([])
const loading = ref(false), saving = ref(false), error = ref(''), loadError = ref('')
const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const matchingTemplates = computed(() => templates.value.filter(item => ['all', form.value.frequency].includes(item.digestCadence)))
const missingCategories = computed(() => form.value.categories.filter(name => !categories.value.includes(name)))
const periodDescription = computed(() => ({ daily: '汇总前一天文章', weekly: '汇总执行日前 7 天文章', monthly: '汇总上一个自然月文章' })[form.value.frequency])
let epoch = 0, disposed = false
function close(value) { if (!saving.value) emit('update:modelValue', value) }
watch(() => form.value.frequency, () => {
  if (loading.value) return
  if (!matchingTemplates.value.some(item => String(item.id) === form.value.templateId)) form.value.templateId = ''
})
watch(() => props.modelValue, async open => {
  const current = ++epoch
  if (!open) return
  const account = store.workspaceEpoch
  loading.value = true; error.value = ''; loadError.value = ''
  form.value = props.record ? readScheduleForm(props.record) : newScheduleForm()
  try {
    const [catalog, filters] = await Promise.all([listPipelineTemplates({ category: 'digest', publishedOnly: true }), getPipelineContentFilters()])
    if (disposed || current !== epoch || account !== store.workspaceEpoch) return
    if (!Array.isArray(catalog.data?.rows) || !Array.isArray(filters.data?.articleCategories)) throw new Error('模板或类别数据无效，请关闭后重试')
    templates.value = catalog.data.rows; categories.value = filters.data.articleCategories
  } catch (err) { if (current === epoch) { loadError.value = err?.msg || err.message || '配置加载失败，请关闭后重试'; error.value = loadError.value } }
  finally { if (current === epoch) loading.value = false }
})
watch(() => store.workspaceEpoch, () => { epoch++; emit('update:modelValue', false) })
async function save() {
  if (loading.value || saving.value || loadError.value) return
  error.value = ''
  let payload
  try {
    if (missingCategories.value.length) throw new Error('已有类别已不可用，请调整后保存，系统不会静默删除筛选条件')
    payload = schedulePayload(form.value, templates.value.find(item => String(item.id) === form.value.templateId))
  } catch (err) { error.value = err.message; return }
  const account = store.workspaceEpoch, current = epoch
  saving.value = true
  try {
    const result = props.record ? await savePipelineDigestScheduleConfig(props.record.id, payload) : await createPipelineDigestSchedule(payload)
    if (disposed || current !== epoch || account !== store.workspaceEpoch) return
    emit('saved', result.data); emit('update:modelValue', false)
    ElMessage.success('自动计划已保存，未立即生成简报')
  } catch (err) { if (current === epoch) error.value = err?.msg || err.message || '保存失败，已保留填写内容' }
  finally { saving.value = false }
}
onBeforeUnmount(() => { disposed = true; epoch++ })
</script>

<style scoped>
.ps-schedule-form { max-height: min(68dvh, 680px); overflow-y: auto; padding: 0 4px 0 0; }
.ps-schedule-intro, .ps-schedule-summary, .ps-schedule-fields small { color: var(--ps-muted); font-size: 13px; line-height: 1.6; }
.ps-schedule-intro { margin: 0 0 16px; }
.ps-schedule-fields { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 0 18px; }
.ps-schedule-fields .is-wide { grid-column: 1 / -1; }
.ps-schedule-fields :deep(.el-select), .ps-schedule-fields :deep(.el-date-editor), .ps-schedule-fields :deep(.el-input-number) { width: 100%; }
.ps-schedule-fields :deep(.el-form-item) { min-width: 0; margin-bottom: 16px; }
.ps-schedule-form h3 { font-size: 15px; margin: 8px 0 14px; }
.ps-schedule-switches { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 16px; }
.ps-schedule-switches :deep(.el-checkbox) { margin-right: 0; }
.ps-schedule-summary { padding-top: 12px; margin: 12px 0 0; border-top: 1px solid var(--ps-line); }
@media (max-width: 560px) { .ps-schedule-fields { grid-template-columns: minmax(0, 1fr); } .ps-schedule-form { max-height: 64dvh; } }
</style>
