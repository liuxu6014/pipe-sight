<template>
  <div class="ps-editor-page ps-digest-editor">
    <div v-if="loading && !loaded" class="ps-detail-loading" aria-live="polite" aria-label="正在加载简报">
      <i></i><div><span></span><span></span><span></span></div>
    </div>
    <div v-else-if="loadError && !loaded" class="ps-inline-state is-warning" role="alert">
      <WarningFilled /><span>{{ loadError }}</span><button type="button" @click="loadDigest">重新加载</button>
    </div>
    <template v-else-if="loaded">
    <header class="ps-editor-topbar">
      <div class="ps-editor-title">
        <button type="button" aria-label="返回情报简报" @click="router.push('/portal/digests')"><ArrowLeft /></button>
        <span><strong>{{ digest.title }}</strong><small>{{ digestPeriod }} · {{ reportTypeLabel }}</small></span>
      </div>
      <div class="ps-save-state"><span :class="{ 'is-saving': saving }"></span>{{ saveLabel }}<b>{{ digest.version || '版本待补充' }}</b></div>
      <div class="ps-editor-actions">
        <el-button @click="router.push(`/portal/research/reports/${digest.id}/diagram`)">查看配图</el-button>
        <el-button :disabled="isReadOnly" :loading="versionSaving" @click="saveVersion"><CollectionTag />保存版本</el-button>
        <el-button v-if="digest.requiresReview" type="success" @click="finalizeDigest"><CircleCheck />确认复核并定稿</el-button>
        <el-button :disabled="isReadOnly" @click="runQualityCheck"><CircleCheck />导出前检查</el-button>
        <el-dropdown trigger="click" @command="exportDigest">
          <el-button type="primary"><Download />{{ digest.requiresReview ? '导出草稿' : '导出简报' }}</el-button>
          <template #dropdown><el-dropdown-menu>
            <el-dropdown-item command="markdown">Markdown 文档</el-dropdown-item>
            <el-dropdown-item command="docx">Word 文档</el-dropdown-item>
            <el-dropdown-item command="pdf">PDF 文档</el-dropdown-item>
          </el-dropdown-menu></template>
        </el-dropdown>
      </div>
    </header>
    <el-alert v-if="isReadOnly" title="当前简报已正式发布，处于只读状态" description="来源查看和导出仍可使用；如需修改，请先由管理员撤销发布。" type="info" :closable="false" show-icon />
    <el-alert v-if="digest.requiresReview" title="当前简报为待复核草稿" :description="digest.generationWarning || '该简报未完成全量模型生成，请配置可用模型或人工复核后再作为正式成果使用。'" type="warning" :closable="false" show-icon />

    <div class="ps-editor-layout ps-digest-editor-layout">
      <aside class="ps-outline-panel">
        <div class="ps-editor-panel-head"><span>栏目目录</span><button type="button" aria-label="新增栏目" :disabled="isReadOnly" @click="addSection"><Plus /></button></div>
        <button v-for="(section, index) in sections" :key="section.id" type="button" :class="['ps-outline-item', { 'is-active': currentSectionId === section.id }]" @click="currentSectionId = section.id">
          <Rank /><span>{{ index + 1 }}</span><span><strong>{{ section.title }}</strong><small>{{ section.words || 0 }} 字 · {{ section.sources || 0 }} 条来源</small></span><i :class="`is-${section.status || 'draft'}`"></i>
        </button>
        <button class="ps-add-section" type="button" :disabled="isReadOnly" @click="addSection"><Plus />新增栏目</button>
      </aside>

      <main class="ps-digest-canvas">
        <article class="ps-digest-paper">
          <header><span>管网科技情报简报</span><h1>{{ digest.title }}</h1><p>{{ isReadOnly ? '正式发布后内容锁定，来源查看与导出仍可使用。' : '所有栏目均可编辑，引用可回到来源条目，保存后跨会话保留。' }}</p><div><span>{{ digestPeriod }}</span><span>{{ digest.version || '版本待补充' }}</span><span>{{ digest.owner || '编制人待补充' }}</span></div></header>
          <section v-if="currentSection">
            <div class="ps-digest-section-title">
              <span>{{ sectionNumber }}</span>
              <div><h2>{{ currentSection.title }}</h2><p>本栏目关联 {{ currentSectionSources.length }} 条可信来源</p></div>
              <button type="button" :disabled="isReadOnly" @click="rebuildSection"><MagicStick />按证据重组研判</button>
            </div>
            <div :key="currentSection.id" class="ps-digest-intro" aria-label="栏目正文" role="textbox" aria-multiline="true" :class="{ 'is-empty': !currentSection.content }" data-placeholder="当前栏目暂无正文，请在此补充。" v-text="currentSection.content" :contenteditable="!isReadOnly" @input="updateSectionContent"></div>
            <article v-for="(source, index) in currentSectionSources" :key="source.id" class="ps-digest-news">
              <span class="ps-digest-index">{{ String(index + 1).padStart(2, '0') }}</span>
              <div><h3>{{ source.title }}</h3><p>{{ source.quote }}</p><small>{{ source.source || source.type }} · {{ source.location }} · <b>{{ source.type }}</b></small></div>
              <div class="ps-digest-item-actions"><button type="button" title="从当前栏目移除" :disabled="isReadOnly" @click="removeSource(source.id)"><Delete /></button><Rank /></div>
            </article>
          </section>
        </article>
      </main>

      <aside class="ps-editor-inspector">
        <div class="ps-inspector-tabs"><button v-for="tab in tabs" :key="tab" type="button" :class="{ 'is-active': activeTab === tab }" @click="activeTab = tab">{{ tab }}</button></div>
        <div v-if="activeTab === '候选资讯'" class="ps-inspector-content">
          <div class="ps-search-inline"><Search /><input v-model="candidateKeyword" aria-label="搜索候选资讯" placeholder="搜索候选资讯" /></div>
          <button v-for="item in candidateNews" :key="item.id" type="button" class="ps-candidate-news" :disabled="isReadOnly" @click="addCandidate(item)"><strong>{{ item.title }}</strong><small>{{ item.source }} · {{ item.category }}</small><span><Plus />添加</span></button>
          <p v-if="!candidateNews.length" class="ps-inspector-empty">没有匹配的候选资讯</p>
        </div>
        <div v-else-if="activeTab === '来源清单'" class="ps-inspector-content">
          <div v-for="item in citations" :key="item.id" class="ps-source-check"><CircleCheckFilled /><span><strong>{{ item.title }}</strong><small>{{ item.source || item.type }} · {{ item.location }}</small></span></div>
          <p v-if="!citations.length" class="ps-inspector-empty">当前报告尚未关联来源</p>
        </div>
        <div v-else class="ps-inspector-content">
          <div v-for="issue in issues" :key="`${issue.sectionId || 'report'}-${issue.title}`" class="ps-quality-card" :class="`is-${issue.level}`"><span>{{ issueLevel(issue.level) }}</span><strong>{{ issue.title }}</strong><p>{{ issue.description }}</p><el-button v-if="issue.sectionId" text @click="locateIssue(issue)">定位栏目</el-button></div>
          <div v-if="!issues.length" class="ps-quality-card is-low"><span>通过</span><strong>未发现阻断导出的问题</strong><p>栏目正文、来源关联和报告结构已完成基础检查。</p></div>
        </div>
      </aside>
    </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getToken } from '@/utils/auth'
import { ArrowLeft, CircleCheck, CircleCheckFilled, CollectionTag, Delete, Download, MagicStick, Plus, Rank, Search, WarningFilled } from '@element-plus/icons-vue'
import usePortalStore from '@/store/modules/portal'
import { createPipelineResearchReportExport, downloadPipelineResearchReportExport, exportPipelineResearchReport, finalizePipelineResearchReport, getPipelineResearchReport, listPipelineResearchReportExports, updatePipelineResearchReport } from '@/api/pipeline/intelligence'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const fallbackDigest = portalStore.digestReports.find(item => item.id === route.params.id) || {}
const digest = ref({ ...fallbackDigest, id: String(route.params.id), title: fallbackDigest.title || '简报标题待补充', version: fallbackDigest.version || '版本待补充' })
const sections = ref(Array.isArray(fallbackDigest.sections) && fallbackDigest.sections.length ? fallbackDigest.sections : [{ id: 1, title: '本期要闻', content: '', words: 0, sources: 0, citations: 0, citationIds: [], status: 'draft' }])
const citations = ref(fallbackDigest.citations || [])
const issues = ref(fallbackDigest.qualityIssues || [])
const activeTab = ref(route.query.panel === 'sources' ? '来源清单' : '候选资讯')
const currentSectionId = ref(sections.value[0]?.id)
const candidateKeyword = ref('')
const loading = ref(false)
const loaded = ref(false)
const loadError = ref('')
const saving = ref(false)
const saveState = ref('saved')
const versionSaving = ref(false)
const tabs = ['候选资讯', '来源清单', '质量检查']
let saveTimer
let dirty = false
let editRevision = 0
let savePromise = Promise.resolve()
const saveLabel = computed(() => ({ saved: '已保存', dirty: '有未保存修改', saving: '正在保存…', error: '保存失败，请重试' })[saveState.value] || '保存状态未知')
const isReadOnly = computed(() => digest.value.status === 'published')

const currentSection = computed(() => sections.value.find(item => item.id === currentSectionId.value) || sections.value[0])
const currentSectionIndex = computed(() => Math.max(sections.value.findIndex(item => item.id === currentSectionId.value), 0))
const sectionNumber = computed(() => String(currentSectionIndex.value + 1).padStart(2, '0'))
const digestPeriod = computed(() => digest.value.period || (digest.value.metadata?.period || []).join(' 至 ') || String(digest.value.updatedAt || '').slice(0, 10) || '当前周期')
const reportTypeLabel = computed(() => ({ daily: '科技情报日报', weekly: '科技情报周报', monthly: '科技情报月报', 日报: '科技情报日报', 周报: '科技情报周报', 月报: '科技情报月报' })[digest.value.reportType || digest.value.type] || '科技情报简报')
const currentSectionSources = computed(() => {
  const ids = currentSection.value?.citationIds || []
  if (ids.length) return citations.value.filter(item => ids.includes(item.id))
  const count = Number(currentSection.value?.sources || currentSection.value?.citations || 0)
  return citations.value.slice(currentSectionIndex.value, currentSectionIndex.value + count)
})
const candidateNews = computed(() => portalStore.newsItems.filter(item => !candidateKeyword.value || `${item.title}${item.summary}${item.source}`.includes(candidateKeyword.value)).slice(0, 12))

function buildMarkdown() { return [`# ${digest.value.title}`, '', ...sections.value.flatMap((section, index) => [`## ${index + 1}. ${section.title}`, '', section.content || '', '']), '## 参考资料', '', ...citations.value.map(item => `[${item.id}] ${item.title}（${item.source || item.type}，${item.location || '来源条目'}）`)].join('\n') }
function markSaving() {
  if (isReadOnly.value) return
  editRevision += 1
  dirty = true
  saveState.value = 'dirty'
  saving.value = true
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => { savePromise = savePromise.then(saveCurrent) }, 700)
}
async function saveCurrent(options = {}) {
  if ((!dirty && !options.saveVersion) || isReadOnly.value) return
  const savedRevision = editRevision
  saving.value = true
  saveState.value = 'saving'
  try {
    const snapshot = JSON.parse(JSON.stringify({ title: digest.value.title, content: buildMarkdown(), sections: sections.value, citations: citations.value, qualityIssues: issues.value, expectedVersion: digest.value.versionNo, expectedRevision: digest.value.revision, ...options }))
    const res = await updatePipelineResearchReport(digest.value.id, snapshot)
    digest.value = { ...digest.value, ...res.data, title: digest.value.title }
    dirty = editRevision !== savedRevision
    saveState.value = dirty ? 'dirty' : 'saved'
    return true
  } catch (error) {
    dirty = true
    saveState.value = 'error'
    ElMessage.error(error?.msg || error?.message || '自动保存失败，当前修改尚未保存')
  } finally {
    saving.value = false
  }
}
async function ensureSaved() {
  clearTimeout(saveTimer)
  if (dirty) savePromise = savePromise.then(saveCurrent)
  await savePromise
  if (dirty || saveState.value === 'error') throw new Error('digest has unsaved changes')
}
function updateSectionContent(event) { if (isReadOnly.value) return; currentSection.value.content = event.currentTarget.innerText.trim(); currentSection.value.words = currentSection.value.content.length; currentSection.value.status = currentSection.value.content ? 'complete' : 'draft'; markSaving() }
function handleBeforeUnload(event) {
  if (!dirty) return
  event.preventDefault()
  event.returnValue = ''
}
function addSection() { if (isReadOnly.value) return; const id = Date.now(); sections.value.push({ id, title: `新增栏目 ${sections.value.length + 1}`, content: '', words: 0, sources: 0, citations: 0, citationIds: [], status: 'draft' }); currentSectionId.value = id; markSaving() }
function addCandidate(item) {
  if (isReadOnly.value || !currentSection.value) return
  const existing = citations.value.find(source => source.sourceId === item.id)
  const citation = existing || { id: citations.value.reduce((max, source) => Math.max(max, Number(source.id) || 0), 0) + 1, sourceId: item.id, type: '科技资讯', title: item.title, location: item.time || item.publishTime || '来源条目', quote: item.summary || '', source: item.source || '公开来源' }
  if (!existing) citations.value.push(citation)
  currentSection.value.citationIds = [...new Set([...(currentSection.value.citationIds || []), citation.id])]
  currentSection.value.sources = currentSection.value.citationIds.length
  currentSection.value.citations = currentSection.value.citationIds.length
  currentSection.value.status = 'complete'
  markSaving()
  ElMessage.success('已添加到当前栏目，并纳入来源清单')
}
function removeSource(id) { if (isReadOnly.value) return; currentSection.value.citationIds = (currentSection.value.citationIds || []).filter(item => item !== id); currentSection.value.sources = currentSection.value.citationIds.length; currentSection.value.citations = currentSection.value.citationIds.length; currentSection.value.status = currentSection.value.sources ? 'complete' : 'warning'; markSaving() }
function rebuildSection() {
  if (isReadOnly.value) return
  if (!currentSectionSources.value.length) {
    currentSection.value.content = ''
    currentSection.value.words = 0
    currentSection.value.status = 'warning'
    markSaving()
    return ElMessage.warning('当前栏目没有关联来源，暂不能按证据重组')
  }
  const evidence = currentSectionSources.value.map(item => `${item.title}显示“${String(item.quote || '').slice(0, 90)}”[${item.id}]`).join('；')
  currentSection.value.content = `基于已关联来源整理：${evidence}\n\n以上内容仅作证据摘录与编辑起点，涉及工程决策时请打开原文复核。`
  currentSection.value.words = currentSection.value.content.length
  currentSection.value.status = currentSectionSources.value.length ? 'complete' : 'warning'
  markSaving()
  ElMessage.success('已按当前证据重组栏目研判')
}
function runQualityCheck() {
  if (isReadOnly.value) return
  const nextIssues = []
  if (!citations.value.length) nextIssues.push({ level: 'high', title: '报告缺少可验证来源', description: '请至少为一个栏目添加可信来源。' })
  sections.value.forEach(section => { if (!section.content?.trim()) nextIssues.push({ level: 'high', sectionId: section.id, title: `“${section.title}”缺少正文`, description: '请补充栏目正文后再导出。' }); else if (Number(section.sources || 0) < 2) nextIssues.push({ level: 'medium', sectionId: section.id, title: `“${section.title}”证据覆盖不足`, description: '当前栏目关联来源少于 2 条，建议补充交叉验证资料。' }) })
  issues.value = nextIssues
  activeTab.value = '质量检查'
  markSaving()
  ElMessage[nextIssues.length ? 'warning' : 'success'](nextIssues.length ? `发现 ${nextIssues.length} 项需要确认的问题` : '基础质量检查已通过')
}
function issueLevel(level) { return ({ high: '高', medium: '中', low: '低' })[level] || level }
function locateIssue(issue) { currentSectionId.value = issue.sectionId; activeTab.value = '候选资讯' }
async function saveVersion() {
  if (isReadOnly.value || versionSaving.value) return
  versionSaving.value = true
  clearTimeout(saveTimer)
  try {
    const versionSave = savePromise.then(() => saveCurrent({ saveVersion: true, versionSource: 'manual' }))
    savePromise = versionSave
    if (!await versionSave) throw new Error('version save failed')
    ElMessage.success('已保存为新的可追溯版本')
  } catch (error) {
    ElMessage.error('版本保存失败，当前修改仍保留在编辑页，请重试')
  } finally {
    versionSaving.value = false
  }
}
async function finalizeDigest() {
  if (isReadOnly.value) return
  try {
    await ensureSaved()
    await ElMessageBox.confirm('定稿后将保留当前版本并结束待复核状态，后续修改会重新进入草稿状态。', '确认复核并定稿', { confirmButtonText: '确认定稿', cancelButtonText: '继续编辑', type: 'warning' })
    const res = await finalizePipelineResearchReport(digest.value.id, { expectedVersion: digest.value.versionNo, expectedRevision: digest.value.revision })
    digest.value = { ...digest.value, ...res.data, title: digest.value.title }
    await portalStore.hydrate(true)
    ElMessage.success('简报已定稿')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error?.msg || '简报定稿失败，请刷新后重试')
  }
}
async function waitAndDownloadExport(format) {
  const prefix = digest.value.requiresReview ? '草稿_' : ''
  const filename = `${prefix}${digest.value.title}.${format}`.replace(/[\\/:*?"<>|]/g, '_')
  const created = await createPipelineResearchReportExport(digest.value.id, { format, allowDraft: digest.value.requiresReview })
  const exportId = created.data?.exportId
  if (!exportId) throw new Error('导出任务创建失败')
  for (let attempt = 0; attempt < 60; attempt += 1) {
    await new Promise(resolve => setTimeout(resolve, 500))
    const result = await listPipelineResearchReportExports(digest.value.id)
    const item = (result.data?.rows || []).find(row => row.exportId === exportId)
    if (item?.status === 'completed') {
      await downloadPipelineResearchReportExport(exportId, filename)
      return
    }
    if (item?.status === 'failed') throw new Error(item.errorMessage || '导出任务失败')
  }
  throw new Error('导出任务处理超时，请稍后在导出记录中重试')
}

async function exportDigest(format = 'markdown') { try { await ensureSaved(); const params = { allowDraft: digest.value.requiresReview }; if (format === 'markdown') { const res = await exportPipelineResearchReport(digest.value.id, params); const blob = new Blob([res.data.content], { type: 'text/markdown;charset=utf-8' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = res.data.fileName || `${digest.value.title}.md`; link.click(); URL.revokeObjectURL(url); ElMessage.success(res.data.isDraft ? '草稿已导出' : '情报简报已导出') } else { await waitAndDownloadExport(format); ElMessage.success(`${format.toUpperCase()} 简报已导出`) } } catch (error) { ElMessage.error(error.message === 'digest has unsaved changes' ? '当前修改未保存，请先重试保存' : error?.msg || '导出失败，请确认后端和数据库已启动') } }
async function loadDigest() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await getPipelineResearchReport(String(route.params.id))
    if (!res.data) throw new Error('empty digest response')
    digest.value = { ...digest.value, ...res.data }
    sections.value = Array.isArray(res.data.sections) ? res.data.sections : []
    citations.value = res.data.citations || []
    issues.value = res.data.qualityIssues || []
    currentSectionId.value = sections.value[0]?.id
    loaded.value = true
  } catch (error) {
    loadError.value = error?.msg || '情报简报加载失败，请确认后端服务和访问权限。'
    ElMessage.error('情报简报加载失败，请确认后端服务和访问权限')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadDigest()
  window.addEventListener('beforeunload', handleBeforeUnload)
})
async function protectUnsavedChanges() {
  // 认证已失效时允许离开，避免私有内容滞留在编辑页。
  if (!getToken()) return true
  if (!dirty) return true
  try {
    await ensureSaved()
    return true
  } catch (error) {
    ElMessage.warning('当前修改尚未保存，已留在编辑页')
    return false
  }
}
onBeforeRouteLeave(protectUnsavedChanges)
onBeforeRouteUpdate(protectUnsavedChanges)
onBeforeUnmount(() => {
  clearTimeout(saveTimer)
  window.removeEventListener('beforeunload', handleBeforeUnload)
})
</script>
