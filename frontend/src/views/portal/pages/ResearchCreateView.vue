<template>
  <div class="ps-page ps-create-page">
    <header class="ps-create-context">
      <button class="ps-create-back" type="button" aria-label="返回科研工作台" @click="router.push('/portal/research')">
        <ArrowLeft />
        <span>科研工作台</span>
      </button>
      <div class="ps-create-heading">
        <h1>新建科研报告</h1>
        <p>确认模板、资料、任务参数与报告大纲</p>
      </div>
      <span class="ps-create-progress" aria-live="polite">步骤 <strong>{{ activeStep + 1 }}</strong> / 4</span>
    </header>
    <el-steps :active="activeStep" finish-status="success" align-center class="ps-create-steps"><el-step title="类型与模板" description="确定输出形式" /><el-step title="选择资料" description="建立证据范围" /><el-step title="任务参数" description="补充研究要求" /><el-step title="确认大纲" description="提交生成任务" /></el-steps>
    <section class="ps-step-card">
      <div v-if="activeStep === 0" class="ps-step-content"><div class="ps-step-title"><span>01</span><div><h2>选择报告类型与模板</h2><p>模板决定报告结构、必填字段和导出样式。</p></div></div><div class="ps-template-choice"><button v-for="template in reportTemplates" :key="template.id" type="button" :class="{ 'is-selected': form.template === template.id }" @click="form.template = template.id"><i :style="{ background: template.color }"></i><Check v-if="form.template === template.id" /><strong>{{ template.name }}</strong><p>{{ template.description }}</p></button></div><div class="ps-form-grid"><label>模板版本<el-select v-model="form.version"><el-option v-if="selectedTemplate" :label="selectedTemplate.version" :value="selectedTemplate.version" /></el-select></label><label>输出语言<el-select v-model="form.language"><el-option label="简体中文" value="zh" /><el-option label="中英双语（暂未开放）" value="bilingual" disabled /></el-select></label><label>预计篇幅<el-select v-model="form.length"><el-option label="标准（8,000-12,000字）" value="standard" /><el-option label="详细（暂未开放）" value="long" disabled /></el-select></label></div></div>
      <div v-else-if="activeStep === 1" class="ps-step-content"><div class="ps-step-title"><span>02</span><div><h2>选择研究资料</h2><p>仅已解析且有权限的资料可用于生成。</p></div></div><div class="ps-material-picker"><div class="ps-material-source"><div class="ps-search-inline"><Search /><input v-model="materialKeyword" aria-label="搜索研究资料" placeholder="搜索资讯、论文或内部资料" /></div><div class="ps-tabs-line"><button v-for="tab in materialTabs" :key="tab" type="button" :class="{ 'is-active': materialTab === tab }" @click="materialTab = tab">{{ tab }}</button></div><label v-for="item in availableMaterials" :key="item.id" class="ps-material-option"><el-checkbox v-model="selectedIds" :value="item.id" :disabled="!item.ready" /><span><strong>{{ item.title }}</strong><small>{{ item.meta }}</small></span><b :class="{ 'is-ready': item.ready }">{{ item.ready ? '可用' : '解析中' }}</b></label><p v-if="!availableMaterials.length" class="ps-inspector-empty">没有匹配的可访问资料</p></div><aside class="ps-selected-basket"><h3>已选资料 <span>{{ selectedIds.length }}</span></h3><div v-for="item in selectedMaterials" :key="item.id"><span><strong>{{ item.title }}</strong><small>{{ item.meta }}</small></span><button type="button" :aria-label="`移除${item.title}`" @click="removeMaterial(item.id)"><Close /></button></div><p v-if="!selectedMaterials.length" class="ps-inspector-empty">请从左侧选择用于生成的资料</p><input ref="fileInput" class="ps-visually-hidden" type="file" accept=".pdf,.docx,.md,.txt" @change="uploadResearchMaterial" /><button type="button" class="ps-upload-drop" :disabled="uploading" @click="fileInput?.click()"><UploadFilled /><span>{{ uploading ? '正在上传并解析…' : '上传新资料' }}</span><small>可搜索 PDF、DOCX、MD、TXT，最大 100MB</small></button></aside></div></div>
      <div v-else-if="activeStep === 2" class="ps-step-content"><div class="ps-step-title"><span>03</span><div><h2>填写任务参数</h2><p>描述越具体，系统越能生成符合业务场景的内容。</p></div></div><div class="ps-form-grid ps-form-grid-wide"><label>任务名称<el-input v-model="form.name" placeholder="例如：管道本体应力监测科研需求报告" /></label><label>研究方向<el-input v-model="form.direction" placeholder="例如：管道应力监测" /></label><label>项目名称 / 需求名称<el-input v-model="form.project" placeholder="请输入正式项目名称" /></label><label>业务场景<el-select v-model="form.scenario"><el-option label="科研项目立项" value="科研项目立项" /><el-option label="技术方案论证" value="技术方案论证" /><el-option label="成果总结" value="成果总结" /></el-select></label><label>研究起止时间<el-date-picker v-model="form.period" type="daterange" start-placeholder="开始日期" end-placeholder="结束日期" /></label><label>关键词<el-select v-model="form.keywords" multiple allow-create filterable default-first-option placeholder="输入后回车添加"><el-option v-for="item in ['应力监测', '磁各向异性', '完整性管理']" :key="item" :label="item" :value="item" /></el-select></label><label class="ps-field-full">生成要求<el-input v-model="form.requirements" type="textarea" :rows="5" placeholder="描述关注问题、技术边界、必须引用的标准和期望结论……" /></label></div><div class="ps-option-row"><el-checkbox v-model="form.diagram">生成技术路线图</el-checkbox><el-checkbox v-model="form.publicSupplement" disabled>公开资料补充（暂未开放，仅使用已选资料）</el-checkbox><el-checkbox v-model="form.citationCheck">提交前执行引用完整性检查</el-checkbox></div></div>
      <div v-else class="ps-step-content"><div class="ps-step-title"><span>04</span><div><h2>确认报告大纲</h2><p>可调整章节顺序、字数目标和章节说明。</p></div></div><div class="ps-outline-editor"><div v-for="(section, index) in outline" :key="section.id" class="ps-outline-row"><Rank /><span class="ps-outline-index">{{ index + 1 }}</span><el-input v-model="section.title" /><el-input-number v-model="section.words" :step="500" :min="500" :max="8000" /><span class="ps-coverage">提交后校验证据</span><button type="button" :aria-label="`删除${section.title}`" @click="removeOutline(section.id)"><Delete /></button></div><el-button class="ps-block-action" @click="addOutline"><Plus />新增章节</el-button></div><div class="ps-submit-review"><div><span>报告类型</span><strong>{{ selectedTemplate?.name }}</strong></div><div><span>已选资料</span><strong>{{ selectedIds.length }} 条</strong></div><div><span>预计篇幅</span><strong>{{ totalWords.toLocaleString() }} 字</strong></div><div><span>生成图形</span><strong>{{ form.diagram ? '是' : '否' }}</strong></div></div></div>
      <footer class="ps-step-footer"><el-button v-if="activeStep > 0" @click="activeStep--">上一步</el-button><span></span><el-button v-if="activeStep < 3" type="primary" @click="nextStep">下一步</el-button><el-button v-else type="primary" :loading="submitting" @click="submitTask">提交生成任务</el-button></footer>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Check, Close, Delete, Plus, Rank, Search, UploadFilled } from '@element-plus/icons-vue'
import usePortalStore from '@/store/modules/portal'
import { createPipelineResearchJob, getPipelineResearchJob, listPipelineTemplates, uploadPipelineKnowledgeDocument } from '@/api/pipeline/intelligence'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const activeStep = ref(0)
const materialTab = ref('全部')
const materialKeyword = ref('')
const materialTabs = ['全部', '科技资讯', '论文', '内部资料']
const submitting = ref(false)
const uploading = ref(false)
const reportTemplates = ref([])
const fileInput = ref()
const form = reactive({ template: String(route.query.template || 'template-01'), version: 'v2.1', language: 'zh', length: 'standard', name: '', direction: '', project: '', scenario: '科研项目立项', period: [], keywords: [], requirements: '', diagram: true, publicSupplement: false, citationCheck: true })
const baseMaterials = computed(() => [
  ...portalStore.newsItems.map(item => ({ id: item.id, title: item.title, type: '科技资讯', meta: `${item.source} · ${String(item.time || '').slice(0, 10)}`, ready: item.status !== 'rejected' })),
  ...portalStore.paperItems.map(item => ({ id: item.id, title: item.titleZh, type: '论文', meta: `${item.journal} · ${item.year}`, ready: item.access !== '访问受限' && item.status !== 'rejected' })),
  ...portalStore.knowledgeDocuments.map(item => ({ id: item.id, title: item.name, type: '内部资料', meta: `${item.owner} · ${item.pages ? `${item.pages}页` : '页数待补充'} · ${item.permission}`, ready: item.status === '已解析' && item.allowAiUse !== false }))
])
const selectedIds = ref([])
const outline = ref([{ id: 1, title: '项目背景与问题分析', words: 1800 }, { id: 2, title: '国内外技术现状', words: 2200 }, { id: 3, title: '研究目标与主要内容', words: 2000 }, { id: 4, title: '技术路线与试验方案', words: 2800 }, { id: 5, title: '考核指标与预期成果', words: 1200 }, { id: 6, title: '进度计划与经费需求', words: 1000 }])
const availableMaterials = computed(() => baseMaterials.value.filter(item => (materialTab.value === '全部' || item.type === materialTab.value) && (!materialKeyword.value || `${item.title}${item.meta}`.includes(materialKeyword.value))))
const selectedMaterials = computed(() => baseMaterials.value.filter(item => selectedIds.value.includes(item.id)))
const selectedTemplate = computed(() => reportTemplates.value.find(item => item.id === form.template || item.templateKey === form.template))
const totalWords = computed(() => outline.value.reduce((sum, item) => sum + item.words, 0))
function removeMaterial(id) { selectedIds.value = selectedIds.value.filter(item => item !== id) }
function removeOutline(id) { outline.value = outline.value.filter(item => item.id !== id) }
function addOutline() { outline.value.push({ id: Date.now(), title: '新增章节', words: 1000, sources: 0 }) }
function nextStep() { if (activeStep.value === 1 && !selectedIds.value.length) return ElMessage.warning('请至少选择一条可用资料'); if (activeStep.value === 2 && (!form.name || !form.direction)) return ElMessage.warning('请填写任务名称和研究方向'); activeStep.value += 1 }
function formatDate(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? String(value) : date.toISOString().slice(0, 10)
}
function resolveReportType() {
  return selectedTemplate.value?.reportType || ({ 'template-01': 'project-demand', 'template-02': 'research-demand', 'template-03': 'technology-route' })[form.template] || 'research-demand'
}
const outlineByTemplate = {
  'template-01': [{ id: 1, title: '生产需求及技术问题', words: 1800 }, { id: 2, title: '国内外技术现状分析', words: 2200 }, { id: 3, title: '研究目标', words: 1600 }, { id: 4, title: '研究内容', words: 2200 }, { id: 5, title: '预期研究成果', words: 1600 }, { id: 6, title: '经费需求', words: 1000 }],
  'template-02': [{ id: 1, title: '问题与必要性', words: 1800 }, { id: 2, title: '研究现状与差距', words: 2200 }, { id: 3, title: '研究目标', words: 1800 }, { id: 4, title: '研究内容与创新点', words: 2400 }, { id: 5, title: '考核指标', words: 1200 }, { id: 6, title: '预期成果与应用', words: 1200 }],
  'template-03': [{ id: 1, title: '需求边界与现状评估', words: 1800 }, { id: 2, title: '关键问题', words: 1800 }, { id: 3, title: '技术路线与阶段任务', words: 2800 }, { id: 4, title: '试验验证方案', words: 2200 }, { id: 5, title: '里程碑与阶段成果', words: 1400 }, { id: 6, title: '风险与备选方案', words: 1000 }]
}
watch(() => form.template, template => {
  const configured = reportTemplates.value.find(item => item.id === template || item.templateKey === template)
  if (configured?.sections?.length) {
    form.version = configured.version || form.version
    outline.value = configured.sections.map(item => ({ ...item }))
  } else if (outlineByTemplate[template]) {
    outline.value = outlineByTemplate[template].map(item => ({ ...item }))
  }
}, { immediate: true })
async function uploadResearchMaterial(event) {
  const file = event.target.files?.[0]
  if (!file || uploading.value) return
  const extension = file.name.includes('.') ? file.name.split('.').pop().toLowerCase() : ''
  if (!['pdf', 'docx', 'md', 'txt'].includes(extension)) {
    ElMessage.warning('仅支持可搜索 PDF、DOCX、MD、TXT；旧版 DOC 请先转换为 DOCX')
    event.target.value = ''
    return
  }
  if (!file.size || file.size > 100 * 1024 * 1024) {
    ElMessage.warning(file.size ? '单个文件不能超过 100MB' : '文件内容为空')
    event.target.value = ''
    return
  }
  uploading.value = true
  try {
    const data = new FormData()
    data.append('file', file)
    data.append('category', '内部资料')
    data.append('permissionScope', 'private')
    const res = await uploadPipelineKnowledgeDocument(data)
    await portalStore.hydrate(true)
    const uploadedId = res.data?.id
    if (uploadedId && res.data?.status === '已解析' && !selectedIds.value.includes(uploadedId)) selectedIds.value.push(uploadedId)
    ElMessage.success(res.data?.status === '已解析' ? '资料上传并解析完成，已加入选择' : '资料上传成功，解析完成后即可选择')
  } catch (error) {
    ElMessage.error('资料上传失败，请检查文件或后端服务')
  } finally {
    uploading.value = false
    event.target.value = ''
  }
}
async function submitTask() {
  if (submitting.value) return
  submitting.value = true
  try {
    const res = await createPipelineResearchJob({
      title: form.name,
      reportType: resolveReportType(),
      templateId: form.template,
      templateVersion: form.version,
      direction: form.direction,
      project: form.project,
      scenario: form.scenario,
      period: (form.period || []).map(formatDate).filter(Boolean),
      keywords: form.keywords,
      requirements: form.requirements,
      diagram: form.diagram,
      citationCheck: form.citationCheck,
      selectedItemIds: selectedIds.value,
      outline: outline.value.map(item => ({ ...item })),
      options: { language: form.language, length: form.length, publicSupplement: form.publicSupplement }
    })
    await portalStore.hydrate(true)
    ElMessage.success('任务已进入后台生成队列，可在任务页查看实时进度')
    router.push(`/portal/research/tasks/${res.data.jobId || res.data.id}`)
  } catch (error) {
    ElMessage.error('任务创建失败，请确认后端已启动并完成业务表初始化')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    const res = await listPipelineTemplates({ category: 'research', publishedOnly: true })
    reportTemplates.value = (res.data?.rows || []).map(item => ({ ...item, id: item.templateKey }))
    if (!reportTemplates.value.some(item => item.id === form.template)) form.template = reportTemplates.value[0]?.id || form.template
  } catch (error) {
    ElMessage.warning('模板列表暂时无法加载')
  }
  await portalStore.hydrate()
  const readyIds = new Set(baseMaterials.value.filter(item => item.ready).map(item => item.id))
  selectedIds.value = [...new Set(portalStore.basket.map(item => item.id).filter(id => readyIds.has(id)))]
  if (route.query.sourceTask) await loadSourceTask(String(route.query.sourceTask), readyIds)
})

async function loadSourceTask(taskId, readyIds) {
  try {
    const res = await getPipelineResearchJob(taskId)
    const task = res.data || {}
    const config = task.config || {}
    form.template = config.templateId || config.template_id || task.templateId || form.template
    form.version = config.templateVersion || config.template_version || task.templateVersion || form.version
    form.language = config.options?.language || form.language
    form.length = config.options?.length || form.length
    form.name = `${task.title || form.name}（副本）`
    form.direction = config.direction || form.direction
    form.project = config.project || form.project
    form.scenario = config.scenario || form.scenario
    form.period = Array.isArray(config.period) ? [...config.period] : form.period
    form.keywords = Array.isArray(config.keywords) ? [...config.keywords] : form.keywords
    form.requirements = config.requirements || form.requirements
    form.diagram = config.diagram !== false
    form.publicSupplement = false
    form.citationCheck = config.citationCheck !== false && config.citation_check !== false
    const copiedOutline = Array.isArray(task.outline) && task.outline.length
      ? task.outline
      : (outlineByTemplate[form.template] || outline.value)
    outline.value = copiedOutline.map(item => ({ ...item }))
    selectedIds.value = (task.selectedItems || []).map(item => item.id).filter(id => readyIds.has(id))
    ElMessage.success('已载入原任务配置，可在提交前继续调整')
  } catch (error) {
    ElMessage.warning('原任务配置暂时无法加载，已按新任务处理')
  }
}
</script>
