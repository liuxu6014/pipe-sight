<template>
  <div class="ps-page ps-create-page ps-research-create-page">
    <header class="ps-create-context">
      <button class="ps-create-back" type="button" aria-label="返回科研工作台" title="返回科研工作台" @click="router.push('/portal/research')">
        <Back />
      </button>
      <div class="ps-create-heading">
        <h1>新建报告</h1>
      </div>
    </header>
    <div v-if="sourceTaskLoading || sourceTaskError" class="ps-inline-state is-warning" role="status">
      <span>{{ sourceTaskLoading ? '正在载入原任务，尚未确认选材范围…' : sourceTaskError }}</span>
      <el-button v-if="sourceTaskError" text @click="loadSourceTask(String(route.query.sourceTask))">重试载入原任务</el-button>
    </div>
    <el-alert v-if="templateUpgradeNotice" :title="templateUpgradeNotice" type="warning" :closable="false" />
    <el-steps :active="activeStep" finish-status="success" align-center class="ps-create-steps"><el-step title="类型与模板" /><el-step title="选择资料" /><el-step title="任务参数" /><el-step title="确认大纲" /></el-steps>
    <section ref="stepCard" class="ps-step-card">
      <div v-if="activeStep === 1 && !verifying && selectionProblems.length" class="ps-inline-state is-warning" role="status">
        <span>部分资料暂不可用，请取消勾选或重试。</span>
        <el-button :loading="verifying" :disabled="submitting" @click="verifySelected(true)">重试</el-button>
      </div>
      <div v-if="activeStep === 0" class="ps-step-content">
        <div v-if="templatesLoading" class="ps-inspector-empty">正在加载已发布模板…</div>
        <PortalEmptyState v-else-if="templatesError || !reportTemplates.length" title="暂无可用报告模板" :description="templatesError || '请先在管理端配置并启用科研报告模板。'" action-label="重新加载" @action="loadTemplates" />
        <div v-else class="ps-template-choice"><button v-for="template in reportTemplates" :key="template.id" type="button" :class="{ 'is-selected': form.template === template.id }" @click="form.template = template.id"><i :style="{ background: template.color }"></i><Check v-if="form.template === template.id" /><strong>{{ template.name }}</strong><p>{{ template.description }}</p></button></div>
        <div class="ps-form-grid ps-template-options">
          <label>输出语言<el-select v-model="form.language"><el-option label="简体中文" value="zh" /><el-option label="中英双语（暂未开放）" value="bilingual" disabled /></el-select></label>
          <label>预计篇幅<el-select v-model="form.length"><el-option label="标准（8,000-12,000字）" value="standard" /><el-option label="详细（暂未开放）" value="long" disabled /></el-select></label>
        </div>
      </div>
      <div v-else-if="activeStep === 1" class="ps-step-content ps-material-step">
        <div class="ps-material-picker">
          <div class="ps-material-source">
            <div class="ps-research-material-toolbar">
              <div class="ps-search-inline"><Search /><input v-model="materialKeyword" aria-label="搜索研究资料" placeholder="搜索资讯、论文或内部资料" /></div>
              <el-button :disabled="submitting || materialLoading || Boolean(materialError) || !selectableMaterialPageIds.length" @click="selectCurrentMaterialPage">{{ currentMaterialPageSelected ? '取消当前页选择' : '全选当前页' }}</el-button>
              <el-button :disabled="uploading || submitting" @click="uploadDialogVisible = true">上传资料</el-button>
              <span class="ps-material-selected-count" role="status">已选 {{ selectedIds.length }} 条</span>
            </div>
            <div class="ps-tabs-line"><button v-for="tab in materialTabs" :key="tab" type="button" :class="{ 'is-active': materialTab === tab }" @click="materialTab = tab">{{ tab }}</button></div>
            <div class="ps-research-material-scroll">
            <p v-if="parsingRefreshError" class="ps-inspector-empty" role="status">{{ parsingRefreshError }}</p>
            <p v-if="materialLoading" class="ps-inspector-empty" role="status">加载中…</p>
            <div v-else-if="materialError" class="ps-inline-state is-warning" role="alert"><span>{{ materialError }}</span><el-button @click="loadMaterials">重试</el-button></div>
            <div v-for="item in availableMaterials" :key="item.id" class="ps-material-option" :class="{ 'is-selected': selectedIds.includes(item.id) }">
              <el-checkbox :model-value="selectedIds.includes(item.id)" :aria-label="`选择研究资料：${item.title}`" :disabled="submitting || (item.state === 'unavailable' && !selectedIds.includes(item.id))" @change="toggleMaterial(item.id, $event)" />
              <span><strong>{{ item.title }}</strong><small>{{ item.state === 'unavailable' && item.reason !== materialParseLabel(item.detail) ? item.reason : materialDescription(item) }}</small></span>
              <span v-if="item.itemType === 'material' && materialParseLabel(item.detail)" class="ps-material-parse-status"><span role="status">{{ materialParseLabel(item.detail) }}</span><el-button v-if="materialParseLabel(item.detail) === '解析失败' && item.detail?.canManage !== false" text type="primary" :loading="retryingMaterialIds.includes(item.id)" :disabled="submitting" :aria-label="`重试解析：${item.title}`" @click="retryMaterial(item)">重试</el-button></span>
            </div>
            <p v-if="!materialLoading && !materialError && !availableMaterials.length" class="ps-inspector-empty">暂无资料</p>
            </div>
          </div>
        </div>
      </div>
      <div v-else-if="activeStep === 2" class="ps-step-content"><div class="ps-form-grid ps-form-grid-wide"><label>任务名称<el-input v-model="form.name" aria-required="true" placeholder="例如：管道本体应力监测科研需求报告" /></label><label>研究方向<el-input v-model="form.direction" aria-required="true" placeholder="例如：管道应力监测" /></label><label>项目名称 / 需求名称<el-input v-model="form.project" placeholder="请输入正式项目名称" /></label><label>业务场景<el-select v-model="form.scenario"><el-option label="科研项目立项" value="科研项目立项" /><el-option label="技术方案论证" value="技术方案论证" /><el-option label="成果总结" value="成果总结" /></el-select></label><label>研究起止时间<el-date-picker v-model="form.period" type="daterange" start-placeholder="开始日期" end-placeholder="结束日期" /></label><label>关键词<el-select v-model="form.keywords" multiple allow-create filterable default-first-option placeholder="输入后回车添加"><el-option v-for="item in ['应力监测', '磁各向异性', '完整性管理']" :key="item" :label="item" :value="item" /></el-select></label><label class="ps-field-full">生成要求<el-input v-model="form.requirements" type="textarea" :rows="5" placeholder="描述关注问题、技术边界、必须引用的标准和期望结论……" /></label></div><div class="ps-option-row"><el-checkbox v-model="form.diagram">生成配图（需后台配置生图模型）</el-checkbox><el-checkbox v-model="form.publicSupplement" disabled>公开资料补充（暂未开放，仅使用已选资料）</el-checkbox><el-checkbox v-model="form.citationCheck">提交前执行引用完整性检查</el-checkbox></div></div>
      <div v-else class="ps-step-content"><div class="ps-outline-editor"><div v-for="(section, index) in outline" :key="section.id" class="ps-outline-row"><span class="ps-outline-index">{{ index + 1 }}</span><el-input v-model="section.title" :aria-label="`第 ${index + 1} 章标题`" /><el-input-number v-model="section.words" :aria-label="`第 ${index + 1} 章目标字数`" :step="500" :min="500" :max="8000" /><span class="ps-outline-controls"><el-button text :disabled="index === 0" :aria-label="`上移${section.title}`" @click="moveOutline(index, -1)"><ArrowUp /></el-button><el-button text :disabled="index === outline.length - 1" :aria-label="`下移${section.title}`" @click="moveOutline(index, 1)"><ArrowDown /></el-button><el-button text type="danger" :disabled="outline.length <= 1" :aria-label="`删除${section.title}`" @click="removeOutline(section.id)"><Delete /></el-button></span></div><el-button class="ps-block-action" @click="addOutline"><Plus />新增章节</el-button></div><div class="ps-submit-review"><div><span>报告类型</span><strong>{{ selectedTemplate?.name }}</strong></div><div><span>已选资料</span><strong>{{ selectedIds.length }} 条</strong></div><div><span>预计篇幅</span><strong>{{ totalWords.toLocaleString() }} 字</strong></div><div><span>生成配图</span><strong>{{ form.diagram ? '是' : '否' }}</strong></div></div></div>
      <div v-if="activeStep === 1 && !materialError" class="ps-pagination ps-material-pagination" aria-label="研究资料列表分页">
        <el-pagination v-model:current-page="materialPage" v-model:page-size="materialPageSize" :page-sizes="[10, 20, 50]" :total="materialTotal" :pager-count="5" :disabled="materialLoading || submitting" layout="total, sizes, ->, prev, pager, next, jumper" background />
      </div>
      <el-alert v-if="selectedTemplate && templateGenerationError(selectedTemplate, { images: form.diagram })" :title="templateGenerationError(selectedTemplate, { images: form.diagram })" type="warning" :closable="false" show-icon />
      <footer class="ps-step-footer">
        <el-button v-if="activeStep > 0" :disabled="submitting" @click="activeStep--">上一步</el-button>
        <div class="ps-step-footer-actions">
          <el-button v-if="activeStep === 0" @click="router.push('/portal/research')">取消</el-button>
          <el-button v-if="activeStep < 3" type="primary" :disabled="nextStepBlocked" @click="nextStep">下一步</el-button>
          <el-button v-else type="primary" :loading="submitting" @click="submitTask">提交生成任务</el-button>
        </div>
      </footer>
    </section>
    <el-dialog v-model="uploadDialogVisible" title="上传资料" width="min(480px, calc(100vw - 32px))" append-to-body @open="uploadError = ''" :close-on-click-modal="!uploading" :close-on-press-escape="!uploading" :show-close="!uploading">
      <input ref="fileInput" class="ps-visually-hidden" type="file" accept=".pdf,.docx,.md,.txt" aria-label="选择上传资料" :disabled="uploading || submitting" @change="uploadResearchMaterial" />
      <button type="button" class="ps-upload-drop" style="width: 100%; margin: 0" :disabled="uploading || submitting" @click="fileInput?.click()">
        <UploadFilled /><span>{{ uploading ? '正在上传…' : '选择文件上传' }}</span><small>支持可搜索 PDF、DOCX、MD、TXT，最大 16MB</small>
      </button>
      <p v-if="uploadError" class="ps-upload-error" role="alert">{{ uploadError }}</p>
      <template #footer><el-button :disabled="uploading" @click="uploadDialogVisible = false">取消</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { displayId, decimalId, requireBusinessId, ID_UPGRADE_NOTICE } from '@/utils/portal/businessId'
import { templateGenerationError } from '@/utils/pipeline/compactContract'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { calendarDate } from '@/utils/portal/businessTime'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowDown, ArrowUp, Back, Check, Delete, Plus, Search, UploadFilled } from '@element-plus/icons-vue'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'
import { createPipelineResearchJob, getPipelineResearchJob, getPipelineIntelligenceDetail, getPipelineKnowledgeDocument, listPipelineTemplates, uploadPipelineKnowledgeDocument, searchPipelineResearchMaterials, reparsePipelineKnowledgeDocument } from '@/api/pipeline/intelligence'
import { mapEvidence, materialParseLabel, selectionReferences, useEvidenceSelection } from '@/utils/portal/evidenceInput'
import { resolveBasketSelection } from '@/utils/portal/basketSelection'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const activeStep = ref(0)
const stepCard = ref()
watch(activeStep, async () => {
  await nextTick()
  stepCard.value?.querySelector('.ps-step-content')?.scrollTo({ top: 0 })
})
const materialTab = ref('全部')
const materialKeyword = ref('')
const materialTabs = ['全部', '新闻资讯', '公众号', '论文', '内部资料']
const submitting = ref(false)
const requestId = ref('')
let requestFingerprint = ''
const uploading = ref(false)
const uploadDialogVisible = ref(false)
const uploadError = ref('')
const reportTemplates = ref([])
const templatesLoading = ref(false)
const templatesError = ref('')
const templateUpgradeNotice = ref('')
const fileInput = ref()
const sourceTaskLoading = ref(false)
const sourceTaskError = ref('')
let sourceTaskGeneration = 0
onBeforeUnmount(() => { sourceTaskGeneration += 1 })
const { selectedIds, selectedMaterials, verifying, problems: selectionProblems, setHint, setSelection, verifySelected, refreshEvidence } = useEvidenceSelection({ getIntelligence: getPipelineIntelligenceDetail, getMaterial: getPipelineKnowledgeDocument }, () => portalStore.workspaceEpoch)
const form = reactive({ template: String(route.query.template || ''), version: '', language: 'zh', length: 'standard', name: '', direction: '', project: '', scenario: '科研项目立项', period: [], keywords: [], requirements: '', diagram: false, publicSupplement: false, citationCheck: true })
watch(() => route.query.template, value => {
  if (value === undefined) return
  form.template = String(value)
  if (!decimalId(form.template)) templateUpgradeNotice.value = ID_UPGRADE_NOTICE
})
const materialPage = ref(1)
const materialPageSize = ref(10)
const materialTotal = ref(0)
const materialRows = ref([])
const materialLoading = ref(false)
const materialError = ref('')
let materialRequest = 0
let materialStopped = false
onBeforeUnmount(() => { materialStopped = true; materialRequest += 1 })
const materialQuery = computed(() => JSON.stringify({
  keyword: materialKeyword.value.trim(),
  type: ({ '全部': 'all', '新闻资讯': 'news', '公众号': 'wechat', '论文': 'paper', '内部资料': 'document' })[materialTab.value],
  pageSize: materialPageSize.value
}))
watch(materialQuery, () => { materialPage.value = 1 }, { flush: 'sync' })
watch([materialQuery, materialPage, () => portalStore.workspaceEpoch], () => { void loadMaterials() }, { immediate: true })
async function loadMaterials() {
  const request = ++materialRequest
  const epoch = portalStore.workspaceEpoch
  materialLoading.value = true
  materialError.value = ''
  materialRows.value = []
  try {
    const response = await searchPipelineResearchMaterials({ ...JSON.parse(materialQuery.value), pageNum: materialPage.value })
    if (materialStopped || request !== materialRequest || epoch !== portalStore.workspaceEpoch) return
    const data = response?.data
    if (!Array.isArray(data?.rows) || !Number.isInteger(Number(data.total)) || Number(data.total) < 0) throw new Error('资料分页数据无效，请重试')
    materialTotal.value = Number(data.total)
    const lastPage = Math.max(1, Math.ceil(materialTotal.value / materialPageSize.value))
    if (materialPage.value > lastPage) { materialPage.value = lastPage; return }
    materialRows.value = data.rows.map(row => {
      const itemType = ({ news: 'article', paper: 'paper', document: 'material' })[row.type]
      if (!row.id || !itemType) throw new Error('资料列表数据无效，请重试')
      setHint(String(row.id), itemType)
      return { id: String(row.id), title: row.title || '题名未提供', itemType, type: itemType === 'article' ? (row.source_type === 'wechat' ? '公众号' : '新闻资讯') : ({ paper: '论文', material: '内部资料' })[itemType], meta: row.meta || '', detail: row, ready: false, state: 'unchecked', reason: '选择后核验' }
    })
  } catch (error) {
    if (!materialStopped && request === materialRequest && epoch === portalStore.workspaceEpoch) {
      materialError.value = error?.msg || error?.message || '资料加载失败，请重试'
      materialTotal.value = 0
    }
  } finally {
    if (!materialStopped && request === materialRequest) materialLoading.value = false
  }
}
const outline = ref([])
const availableMaterials = computed(() => {
  const selected = new Map(selectedMaterials.value.map(item => [item.id, item]))
  return materialRows.value.map(item => {
    const checked = selected.get(item.id)
    return checked ? { ...item, ...checked, title: item.title, type: item.type } : item
  })
})
const retryingMaterialIds = ref([])
const parsingRefreshError = ref('')
const parsingMaterialIds = computed(() => [...new Set([...materialRows.value, ...selectedMaterials.value]
  .filter(item => item.itemType === 'material' && materialParseLabel(item.detail) === '解析中')
  .map(item => item.id))])
let parsingTimer
let parsingRefreshRunning = false
const parsingVersions = new Map()
function scheduleParsingRefresh() {
  if (!materialStopped && !parsingTimer && parsingMaterialIds.value.length) {
    parsingTimer = setTimeout(() => { parsingTimer = undefined; void refreshParsingMaterials() }, 3000)
  }
}
watch(parsingMaterialIds, ids => {
  if (!ids.length) { clearTimeout(parsingTimer); parsingTimer = undefined; parsingRefreshError.value = '' }
  else scheduleParsingRefresh()
})
watch(() => portalStore.workspaceEpoch, () => {
  clearTimeout(parsingTimer); parsingTimer = undefined; parsingVersions.clear()
  retryingMaterialIds.value = []; parsingRefreshError.value = ''
})
onBeforeUnmount(() => { clearTimeout(parsingTimer); parsingVersions.clear() })
async function refreshParsingMaterials() {
  if (materialStopped || parsingRefreshRunning) return
  if (submitting.value) { scheduleParsingRefresh(); return }
  parsingRefreshRunning = true
  const epoch = portalStore.workspaceEpoch
  const pageRequest = materialRequest
  let failed = false
  try {
    await mapEvidence(parsingMaterialIds.value.filter(id => !retryingMaterialIds.value.includes(id)), async id => {
      const version = parsingVersions.get(id)
      try {
        let detail
        if (selectedIds.value.includes(id)) {
          detail = (await refreshEvidence(id))?.detail
          if (!detail) throw new Error('资料状态获取失败')
        } else {
          detail = (await getPipelineKnowledgeDocument(id)).data
          if (!detail || String(detail.id) !== id) throw new Error('资料状态获取失败')
        }
        if (materialStopped || epoch !== portalStore.workspaceEpoch || version !== parsingVersions.get(id)) return
        if (pageRequest === materialRequest) materialRows.value = materialRows.value.map(item => item.id === id ? { ...item, detail } : item)
      } catch { failed = true }
    })
    if (!materialStopped && epoch === portalStore.workspaceEpoch) parsingRefreshError.value = failed ? '状态更新暂时失败，正在自动重试' : ''
  } finally {
    parsingRefreshRunning = false
    scheduleParsingRefresh()
  }
}
async function retryMaterial(item) {
  const id = item.id
  if (materialStopped || submitting.value || retryingMaterialIds.value.includes(id) || item.detail?.canManage === false || materialParseLabel(item.detail) !== '解析失败') return
  const epoch = portalStore.workspaceEpoch
  const version = (parsingVersions.get(id) || 0) + 1
  parsingVersions.set(id, version)
  retryingMaterialIds.value = [...retryingMaterialIds.value, id]
  try {
    const response = await reparsePipelineKnowledgeDocument(id)
    if (materialStopped || epoch !== portalStore.workspaceEpoch || version !== parsingVersions.get(id)) return
    const detail = response.data
    if (!detail || String(detail.id) !== id) throw new Error('重试状态获取失败')
    materialRows.value = materialRows.value.map(row => row.id === id ? { ...row, detail } : row)
    if (selectedIds.value.includes(id)) await refreshEvidence(id)
    if (!materialStopped && epoch === portalStore.workspaceEpoch) ElMessage.success('已提交重新解析')
  } catch (error) {
    if (!materialStopped && epoch === portalStore.workspaceEpoch) ElMessage.error(error?.msg || error?.message || '重试失败，请稍后再试')
  } finally {
    if (!materialStopped && epoch === portalStore.workspaceEpoch && version === parsingVersions.get(id)) retryingMaterialIds.value = retryingMaterialIds.value.filter(value => value !== id)
    scheduleParsingRefresh()
  }
}
const selectableMaterialPageIds = computed(() => availableMaterials.value
  .filter(item => item.state !== 'unavailable' || selectedIds.value.includes(item.id))
  .map(item => item.id))
const currentMaterialPageSelected = computed(() => selectableMaterialPageIds.value.length > 0
  && selectableMaterialPageIds.value.every(id => selectedIds.value.includes(id)))
const selectedTemplate = computed(() => reportTemplates.value.find(item => item.id === form.template || item.templateKey === form.template))
const totalWords = computed(() => outline.value.reduce((sum, item) => sum + item.words, 0))
const nextStepBlocked = computed(() => activeStep.value === 0 ? !selectedTemplate.value || templatesLoading.value
  : activeStep.value === 1 ? uploading.value || !selectedIds.value.length || verifying.value || Boolean(selectionProblems.value.length) || sourceTaskLoading.value || Boolean(sourceTaskError.value)
  : activeStep.value === 2 ? !form.name.trim() || !form.direction.trim() : false)
function materialDescription(item) {
  const detail = item.detail || {}
  return [detail.journal || detail.source || detail.owner, detail.year || detail.publish_time || detail.publishTime].filter(Boolean).join(' · ') || item.meta || (item.itemType === 'material' ? '内部资料' : '')
}
function selectCurrentMaterialPage() {
  if (submitting.value || materialLoading.value || materialError.value) return
  if (currentMaterialPageSelected.value) {
    const pageIds = new Set(availableMaterials.value.map(item => item.id))
    selectedIds.value = selectedIds.value.filter(id => !pageIds.has(id))
  } else {
    selectedIds.value = [...new Set([...selectedIds.value, ...selectableMaterialPageIds.value])]
  }
}
function toggleMaterial(id, checked) {
  if (submitting.value) return
  id = displayId(id)
  selectedIds.value = checked ? [...new Set([...selectedIds.value, id])] : selectedIds.value.filter(item => item !== id)
}
function removeOutline(id) { if (outline.value.length > 1) outline.value = outline.value.filter(item => item.id !== id) }
function moveOutline(index, direction) {
  const target = index + direction
  if (target < 0 || target >= outline.value.length) return
  const [section] = outline.value.splice(index, 1)
  outline.value.splice(target, 0, section)
}
function addOutline() { outline.value.push({ id: Date.now(), title: '新增章节', words: 1000, sources: 0 }) }
function nextStep() {
  if (activeStep.value === 0 && !selectedTemplate.value) return ElMessage.warning('请选择一个已发布的报告模板')
  if (activeStep.value === 1 && !selectedIds.value.length) return ElMessage.warning('请至少选择一条可用资料')
  if (activeStep.value === 1 && (sourceTaskLoading.value || sourceTaskError.value || verifying.value || selectionProblems.value.length)) return ElMessage.warning('请完成全部选材核验，重试或明确移除不可用项后继续')
  if (activeStep.value === 2 && (!form.name.trim() || !form.direction.trim())) return ElMessage.warning('请填写任务名称和研究方向')
  activeStep.value += 1
}
function formatDate(value) {
  return calendarDate(value)
}
function resolveReportType() {
  return selectedTemplate.value?.purpose || selectedTemplate.value?.reportType || 'research'
}
function ensureRequestId(payload) {
  const fingerprint = JSON.stringify(payload)
  if (!requestId.value || requestFingerprint !== fingerprint) {
    requestId.value = globalThis.crypto?.randomUUID?.() || `research-${Date.now()}-${Math.random().toString(16).slice(2)}`
    requestFingerprint = fingerprint
  }
  return requestId.value
}
// 同时响应模板编码和异步模板数据，不能只监听初始 URL 中的编码。
watch(selectedTemplate, configured => {
  if (!configured) return
  templateUpgradeNotice.value = ''
  form.version = configured?.version || ''
  form.diagram = Boolean(configured?.imageConfig?.enabled)
  outline.value = (configured?.sections || []).map(item => ({ ...item }))
}, { immediate: true })
async function uploadResearchMaterial(event) {
  const file = event.target.files?.[0]
  if (!file || uploading.value || submitting.value) return
  uploadError.value = ''
  const extension = file.name.includes('.') ? file.name.split('.').pop().toLowerCase() : ''
  if (!['pdf', 'docx', 'md', 'txt'].includes(extension)) {
    ElMessage.warning('仅支持可搜索 PDF、DOCX、MD、TXT；旧版 DOC 请先转换为 DOCX')
    event.target.value = ''
    return
  }
  if (!file.size || file.size > 16 * 1024 * 1024) {
    ElMessage.warning(file.size ? '单个文件不能超过 16MB' : '文件内容为空')
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
    if (uploadedId) { setHint(uploadedId, 'material'); selectedIds.value = [...new Set([...selectedIds.value, String(uploadedId)])] }
    await loadMaterials()
    ElMessage.success('已保存到资料库')
    uploadDialogVisible.value = false
  } catch (error) {
    uploadError.value = error?.msg || '资料上传失败，请检查文件或后端服务'
    ElMessage.error(uploadError.value)
  } finally {
    uploading.value = false
    event.target.value = ''
  }
}
async function submitTask() {
  if (submitting.value) return
  if (form.template && !decimalId(form.template)) return ElMessage.warning(ID_UPGRADE_NOTICE)
  if (!selectedTemplate.value) return ElMessage.warning('当前模板不可用，请重新选择启用模板')
  const modelError = templateGenerationError(selectedTemplate.value, { images: form.diagram })
  if (modelError) return ElMessage.warning(modelError)
  if (sourceTaskLoading.value || sourceTaskError.value) return ElMessage.warning('原任务尚未成功载入，请先重试')
  submitting.value = true
  try {
    const idsBefore = JSON.stringify(selectedIds.value)
    const session = portalStore.workspaceEpoch
    if (!await verifySelected(true)) return ElMessage.warning('选材核验未通过，请重试或移除列出的不可用资料')
    if (session !== portalStore.workspaceEpoch || idsBefore !== JSON.stringify(selectedIds.value)) return ElMessage.warning('账号或选材已变化，请重新确认后提交')
    const payload = buildResearchPayload()
    const res = await createPipelineResearchJob({ ...payload, requestId: ensureRequestId(payload) })
    await portalStore.hydrate(true)
    ElMessage.success('任务已进入后台生成队列，可在任务页查看实时进度')
    router.push(`/portal/research/tasks/${res.data.jobId || res.data.id}`)
  } catch (error) {
    ElMessage.error(error?.msg || error?.message || '任务创建失败，请确认后端已启动并完成业务表初始化')
  } finally {
    submitting.value = false
  }
}
function buildResearchPayload() {
  const modelError = templateGenerationError(selectedTemplate.value, { images: form.diagram })
  if (modelError) throw new Error(modelError)
  if (selectedIds.value.length > 50) throw new Error('每次生成最多选择 50 篇资料，请减少勾选')
  if (!selectedIds.value.length || selectionProblems.value.length || verifying.value) throw new Error('存在未核验或不可用选材，不能提交')
  if (sourceTaskLoading.value || sourceTaskError.value) throw new Error('原任务尚未成功载入')
  return {
      title: form.name,
      reportType: resolveReportType(),
      templateId: requireBusinessId(form.template),
      templateVersion: form.version,
      direction: form.direction,
      project: form.project,
      scenario: form.scenario,
      period: (form.period || []).map(formatDate).filter(Boolean),
      keywords: form.keywords,
      requirements: form.requirements,
      diagram: form.diagram,
      citationCheck: form.citationCheck,
      selectedItemIds: selectedIds.value.map(requireBusinessId),
      outline: outline.value.map(item => ({ ...item })),
      options: { language: form.language, length: form.length, publicSupplement: form.publicSupplement }
  }
}

async function loadTemplates() {
  templatesLoading.value = true
  templatesError.value = ''
  try {
    const res = await listPipelineTemplates({ category: 'research', publishedOnly: true })
    reportTemplates.value = (res.data?.rows || []).map(item => ({ ...item, id: displayId(item.id || item.templateKey) }))
    if (!form.template) form.template = reportTemplates.value[0]?.id || ''
    else if (!reportTemplates.value.some(item => item.id === form.template)) templateUpgradeNotice.value = ID_UPGRADE_NOTICE
  } catch (error) {
    reportTemplates.value = []
    templatesError.value = error?.msg || '模板服务暂时不可用，请稍后重试。'
  } finally {
    templatesLoading.value = false
  }
}

onMounted(async () => {
  const generation = sourceTaskGeneration
  await Promise.all([loadTemplates(), portalStore.hydrate()])
  if (generation !== sourceTaskGeneration) return
  const selection = resolveBasketSelection(portalStore.basket, route.query.selected)
  setSelection(selection.items)
  if (selection.upgraded) ElMessage.warning(ID_UPGRADE_NOTICE)
  else if (selection.missing) ElMessage.warning(`${selection.missing} 条选材已不在当前资料篮中，请重新选择`)
  if (route.query.sourceTask) await loadSourceTask(String(route.query.sourceTask))
})
watch(() => route.query.sourceTask, taskId => { if (taskId) void loadSourceTask(String(taskId)) })

async function loadSourceTask(taskId) {
  if (!decimalId(taskId)) { sourceTaskError.value = ID_UPGRADE_NOTICE; return }
  const generation = ++sourceTaskGeneration
  const session = portalStore.workspaceEpoch
  sourceTaskLoading.value = true
  sourceTaskError.value = ''
  try {
    const res = await getPipelineResearchJob(taskId)
    if (generation !== sourceTaskGeneration || session !== portalStore.workspaceEpoch) return
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
    form.diagram = config.diagram === true || selectedTemplate.value?.imageConfig?.enabled === true
    form.publicSupplement = false
    form.citationCheck = config.citationCheck !== false && config.citation_check !== false
    await nextTick()
    if (generation !== sourceTaskGeneration || session !== portalStore.workspaceEpoch) return
    const copiedOutline = Array.isArray(task.outline) && task.outline.length
      ? task.outline
      : outline.value
    outline.value = copiedOutline.map(item => ({ ...item }))
    setSelection([...selectionReferences(task.selectedItems || []), ...selectionReferences(config.selectedItemIds || config.selected_item_ids || [])])
    ElMessage.success('已载入原任务配置及全部选材 ID，正在核验当前授权和可用性')
  } catch (error) {
    if (generation === sourceTaskGeneration && session === portalStore.workspaceEpoch) sourceTaskError.value = error?.msg || '原任务配置加载失败，选材范围尚未确认，请重试'
  } finally {
    if (generation === sourceTaskGeneration) sourceTaskLoading.value = false
  }
}
</script>

<style scoped>
.ps-create-context { grid-template-columns: 44px minmax(0, 1fr); gap: 12px; align-items: center; }
.ps-create-back { grid-column: auto; width: 44px; height: 44px; padding: 0; justify-content: center; border: 1px solid var(--ps-line); border-radius: 8px; background: #fff; }
.ps-create-back svg { width: 18px; height: 18px; }
.ps-create-back:hover { border-color: var(--ps-blue); background: var(--ps-blue-soft); }
.ps-create-back:hover svg { transform: none; }
.ps-template-options { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.ps-research-create-page .ps-material-picker { grid-template-columns: minmax(0, 1fr); }
.ps-research-create-page .ps-material-source { min-height: 0; padding: 0; border: 0; }
.ps-research-create-page .ps-material-step { display: flex; flex-direction: column; overflow: hidden; }
.ps-material-step .ps-material-picker,
.ps-material-step .ps-material-source { display: flex; flex-direction: column; flex: 0 1 auto; min-height: 0; overflow: hidden; }
.ps-material-step .ps-research-material-toolbar,
.ps-material-step .ps-tabs-line { flex-shrink: 0; }
.ps-research-material-scroll { flex: 0 1 auto; min-height: 0; overflow-y: auto; scrollbar-gutter: stable; }
.ps-research-material-toolbar { display: flex; align-items: center; gap: 12px; }
.ps-research-material-toolbar .ps-search-inline { flex: 1; min-width: 0; }
.ps-research-material-toolbar .el-button { min-height: 44px; margin: 0; flex-shrink: 0; }
.ps-material-selected-count { flex-shrink: 0; color: var(--ps-muted); font-size: 13px; white-space: nowrap; }
.ps-research-create-page .ps-material-pagination { flex-shrink: 0; margin: 0; padding: 12px 20px; border-top: 1px solid var(--ps-line); background: #fff; }
.ps-research-create-page .ps-material-option { grid-template-columns: 24px minmax(0, 1fr) auto; padding-inline: 8px; }
.ps-material-parse-status { display: flex; flex-direction: row; align-items: center; gap: 8px; color: var(--ps-muted); white-space: nowrap; }
.ps-material-option.is-selected { background: var(--ps-blue-soft); border-radius: 6px; }
.ps-upload-error { color: var(--el-color-danger); line-height: 1.6; }
.ps-upload-drop { display: flex; flex-direction: column; align-items: center; gap: 10px; min-height: 156px; padding: 24px 16px; border: 1px dashed var(--el-border-color); border-radius: 8px; background: var(--el-fill-color-lighter); color: var(--el-color-primary); cursor: pointer; }
.ps-upload-drop svg { width: 28px; height: 28px; flex-shrink: 0; }
.ps-upload-drop small { color: var(--el-text-color-secondary); line-height: 1.6; }
.ps-upload-drop:disabled { cursor: wait; opacity: .65; }
.ps-upload-drop:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: 3px; }
.ps-step-footer { display: flex; gap: 12px; }
.ps-step-footer-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; flex-shrink: 0; }
.ps-step-footer-actions .el-button { margin: 0; }
@media (max-width: 760px) {
  .ps-research-material-toolbar { flex-wrap: wrap; }
  .ps-research-material-toolbar .ps-search-inline { flex-basis: 100%; }
  .ps-template-options { grid-template-columns: minmax(0, 1fr); }
  .ps-create-heading h1 { font-size: 22px; line-height: 1.4; }
}
</style>
