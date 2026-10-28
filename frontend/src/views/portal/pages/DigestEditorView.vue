<template>
  <div class="ps-editor-page ps-digest-editor">
    <div v-if="loading && !loaded" class="ps-detail-loading" aria-live="polite" aria-label="正在加载简报">
      <i></i><div><span></span><span></span><span></span></div>
    </div>
    <div v-else-if="loadError && !loaded" class="ps-inline-state is-warning" role="alert">
      <WarningFilled /><span>{{ loadError }}</span><el-button class="ps-ui-action" @click="loadDigest">重新加载</el-button>
    </div>
    <template v-else-if="loaded">
    <header class="ps-editor-topbar">
      <div class="ps-editor-title">
        <el-button class="ps-ui-action" aria-label="返回情报简报" @click="router.push('/portal/digests')"><ArrowLeft /></el-button>
        <span><strong>{{ digest.title }}</strong><small>{{ digestPeriod }} · {{ reportTypeLabel }}</small></span>
      </div>
      <div class="ps-save-state"><span :class="{ 'is-saving': saving }"></span>{{ saveLabel }}</div>
      <div class="ps-editor-actions">
        <el-button :disabled="digest.readOnly" @click="router.push(`/portal/research/reports/${digest.id}/diagram`)">查看配图</el-button>
        <el-button :disabled="isReadOnly" :loading="versionSaving" @click="saveVersion"><CollectionTag />保存修改</el-button>
        <el-button v-if="digest.requiresReview" :disabled="isReadOnly" type="success" @click="finalizeDigest"><CircleCheck />确认复核并定稿</el-button>
        <el-dropdown trigger="click" @command="exportDigest">
          <el-button type="primary" :disabled="digest.readOnly || exporting" :loading="exporting"><Download />{{ digest.requiresReview ? '导出草稿' : '导出简报' }}</el-button>
          <template #dropdown><el-dropdown-menu>
            <el-dropdown-item command="markdown">Markdown 文档</el-dropdown-item>
            <el-dropdown-item command="docx">Word 文档</el-dropdown-item>
            <el-dropdown-item command="pdf">PDF 文档</el-dropdown-item>
          </el-dropdown-menu></template>
        </el-dropdown>
      </div>
    </header>
    <el-alert v-if="digest.readOnly" title="正在只读查看其他用户的简报" description="可查看正文和来源；编辑、定稿及文件导出由简报所有者操作。" type="info" :closable="false" show-icon />
    <el-alert v-else-if="isReadOnly" title="当前简报已正式发布，处于只读状态" description="来源查看和导出仍可使用；如需修改，请先由管理员撤销发布。" type="info" :closable="false" show-icon />
    <el-alert v-if="digest.requiresReview" title="当前简报为待复核草稿" :description="digest.generationWarning || '该简报未完成全量模型生成，请配置可用模型或人工复核后再作为正式成果使用。'" type="warning" :closable="false" show-icon />

    <div class="ps-editor-layout ps-digest-editor-layout">
      <aside class="ps-outline-panel">
        <div class="ps-editor-panel-head"><span>栏目目录</span><el-button class="ps-ui-action" aria-label="新增栏目" :disabled="isReadOnly" @click="addSection"><Plus /></el-button></div>
        <button v-for="(section, index) in sections" :key="section.id" type="button" :class="['ps-outline-item', { 'is-active': currentSectionId === section.id }]" @click="currentSectionId = section.id">
          <Rank /><span>{{ index + 1 }}</span><span><strong>{{ section.title }}</strong><small>{{ section.words || 0 }} 字 · {{ sectionSources(section).length }} 条来源</small></span><i :class="`is-${section.status || 'draft'}`"></i>
        </button>
        <el-button class="ps-ui-action ps-add-section" :disabled="isReadOnly" @click="addSection"><Plus />新增栏目</el-button>
      </aside>

      <main class="ps-digest-canvas">
        <article class="ps-digest-paper">
          <header><span>管网科技情报简报</span><h1>{{ digest.title }}</h1><p>{{ digest.readOnly ? '当前仅供查阅，修改和文件导出由简报所有者操作。' : isReadOnly ? '正式发布后内容锁定，来源查看与导出仍可使用。' : '所有栏目均可编辑，引用可回到来源条目，保存后跨会话保留。' }}</p><div><span>{{ digestPeriod }}</span><span>{{ digest.owner || '编制人待补充' }}</span></div></header>
          <section v-if="currentSection">
            <div class="ps-digest-section-title">
              <span>{{ sectionNumber }}</span>
              <div><h2>{{ currentSection.title }}</h2><p>本栏目关联 {{ currentSectionSources.length }} 条来源</p></div>
              <el-button class="ps-ui-action" :disabled="isReadOnly" @click="rebuildSection"><MagicStick />按证据重组研判</el-button>
            </div>
            <div :key="currentSection.id" class="ps-digest-intro" aria-label="栏目正文" role="textbox" aria-multiline="true" :class="{ 'is-empty': !currentSection.content }" data-placeholder="当前栏目暂无正文，请在此补充。" :contenteditable="!isReadOnly" @input="updateSectionContent"><template v-for="(part, partIndex) in reportCitationParts(currentSection.content, currentSection.title, Math.max(0, ...citations.map(item => Number(item.id) || 0)))" :key="partIndex"><sup v-if="part.citation" class="ps-citation-marker"><router-link v-if="citationPath(part.text)" :to="citationPath(part.text)" :contenteditable="false" :aria-label="`查看引用 ${part.text} 的资料详情`">{{ part.text }}</router-link><template v-else>{{ part.text }}</template></sup><span v-else>{{ part.text }}</span></template></div>
            <article v-for="(source, index) in currentSectionSources" :key="source.id" class="ps-digest-news">
              <span class="ps-digest-index">{{ String(index + 1).padStart(2, '0') }}</span>
              <div><h3><router-link v-if="getCitationPath(source)" :to="getCitationPath(source)">{{ source.title }}</router-link><template v-else>{{ source.title }}</template></h3><p v-if="source.quote">{{ source.quote }}</p><small>{{ citationSourceLabel(source) }}<template v-if="source.location"> · {{ source.location }}</template></small></div>
              <div class="ps-digest-item-actions"><el-button class="ps-ui-action" title="从当前栏目移除" :disabled="isReadOnly" @click="removeSource(source.id)"><Delete /></el-button><Rank /></div>
            </article>
          </section>
        </article>
      </main>

      <aside class="ps-editor-inspector" :class="{ 'is-picking-candidates': activeTab === '候选资讯' }">
        <div class="ps-inspector-tabs"><button v-for="tab in tabs" :key="tab" type="button" :class="{ 'is-active': activeTab === tab }" @click="activeTab = tab">{{ tab }}</button></div>
        <div v-show="activeTab === '候选资讯'" class="ps-inspector-content ps-digest-candidate-content"><DigestCandidatePicker :selected-ids="currentArticleIds" :read-only="isReadOnly" :enabled="activeTab === '候选资讯' && loaded" @select="addCandidate" /></div>
        <div v-if="activeTab === '来源清单'" class="ps-inspector-content">
          <ol class="ps-digest-sources"><li v-for="(item, index) in citations" :key="item.id"><span>{{ index + 1 }}</span><div><router-link v-if="getCitationPath(item)" :to="getCitationPath(item)">{{ item.title }}</router-link><strong v-else>{{ item.title }}</strong><small>{{ citationSourceLabel(item) }}<template v-if="item.location"> · {{ item.location }}</template></small></div></li></ol>
          <p v-if="!citations.length" class="ps-inspector-empty">当前报告尚未关联来源</p>
        </div>
        <div v-if="activeTab === '导出记录'" class="ps-inspector-content"><ReportExportHistory :report-id="String(digest.id)" :title="digest.title" :read-only="Boolean(digest.readOnly)" :refresh-key="exportRefreshKey" /></div>
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
import { cleanReportCitationNotes, reportCitationParts } from '@/utils/portal/reportDocument'
import { getCitationPath } from '@/utils/portal/citationRouting'
import ReportExportHistory from '../components/ReportExportHistory.vue'
import DigestCandidatePicker from '../components/DigestCandidatePicker.vue'
import { decimalId } from '@/utils/portal/businessId'
import { ArrowLeft, CircleCheck, CollectionTag, Delete, Download, MagicStick, Plus, Rank, WarningFilled } from '@element-plus/icons-vue'
import usePortalStore from '@/store/modules/portal'
import { createPipelineResearchReportExport, downloadPipelineResearchReportExport, exportPipelineResearchReport, finalizePipelineResearchReport, getPipelineResearchReport, listPipelineResearchReportExports, updatePipelineResearchReport } from '@/api/pipeline/intelligence'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const fallbackDigest = portalStore.digestReports.find(item => item.id === route.params.id) || {}
const digest = ref({ ...fallbackDigest, id: String(route.params.id), title: fallbackDigest.title || '简报标题待补充' })
const sections = ref(Array.isArray(fallbackDigest.sections) && fallbackDigest.sections.length ? fallbackDigest.sections : [{ id: 1, title: '本期要闻', content: '', words: 0, sources: 0, citations: 0, citationIds: [], status: 'draft' }])
const citations = ref(fallbackDigest.citations || [])
const issues = ref(fallbackDigest.qualityIssues || [])
const activeTab = ref(({ sources: '来源清单', exports: '导出记录' })[route.query.panel] || '候选资讯')
const currentSectionId = ref(sections.value[0]?.id)
const loading = ref(false)
const loaded = ref(false)
const loadError = ref('')
const saving = ref(false)
const saveState = ref('saved')
const versionSaving = ref(false)
const exporting = ref(false)
const exportRefreshKey = ref(0)
const tabs = ['候选资讯', '来源清单', '导出记录']
let saveTimer
let dirty = false
let editRevision = 0
let savePromise = Promise.resolve()
let active = true
let loadGeneration = 0
const saveLabel = computed(() => ({ saved: '已保存', dirty: '有未保存修改', saving: '正在保存…', error: '保存失败，请重试' })[saveState.value] || '保存状态未知')
const isReadOnly = computed(() => Boolean(digest.value.readOnly) || digest.value.status === 'published')

const currentSection = computed(() => sections.value.find(item => item.id === currentSectionId.value) || sections.value[0])
const currentSectionIndex = computed(() => Math.max(sections.value.findIndex(item => item.id === currentSectionId.value), 0))
const sectionNumber = computed(() => String(currentSectionIndex.value + 1).padStart(2, '0'))
const digestPeriod = computed(() => digest.value.period || (digest.value.metadata?.period || []).join(' 至 ') || String(digest.value.updatedAt || '').slice(0, 10) || '当前周期')
const reportTypeLabel = computed(() => ({ daily: '科技情报日报', weekly: '科技情报周报', monthly: '科技情报月报', 日报: '科技情报日报', 周报: '科技情报周报', 月报: '科技情报月报' })[digest.value.reportType || digest.value.type] || '科技情报简报')
function sectionSources(section) {
  const ids = new Set((section?.citationIds || []).map(String))
  return citations.value.filter(item => ids.has(String(item.id)))
}
const currentSectionSources = computed(() => sectionSources(currentSection.value))
const currentArticleIds = computed(() => currentSectionSources.value.filter(item => getCitationPath(item)?.startsWith('/portal/news/')).map(item => String(item.sourceId ?? item.source_id)))

function citationSourceLabel(item) {
  if (typeof item.source === 'string' && item.source.trim()) return item.source.trim()
  const source = item.source || {}
  return ['name', 'title', 'sourceName', 'publisher', 'journal', 'filename', 'url']
    .map(key => source[key]).find(value => typeof value === 'string' && value.trim()) || item.type || '来源未提供'
}
function citationPath(text) {
  const id = String(text || '').replace(/^\[|\]$/g, '')
  return getCitationPath(citations.value.find(item => String(item.id) === id))
}
function buildMarkdown() { return [`# ${digest.value.title}`, '', ...sections.value.flatMap((section, index) => [`## ${index + 1}. ${section.title}`, '', cleanReportCitationNotes(section.content || '', section.title), '']), '## 参考资料', '', ...citations.value.map(item => `[${item.id}] ${item.title}（${citationSourceLabel(item)}，${item.location || '来源条目'}）`)].join('\n') }
function markSaving() {
  if (!active || isReadOnly.value) return
  editRevision += 1
  dirty = true
  saveState.value = 'dirty'
  saving.value = true
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => { savePromise = savePromise.then(saveCurrent) }, 700)
}
async function saveCurrent(options = {}) {
  if (!active || (!dirty && !options.saveVersion) || isReadOnly.value) return
  const id = String(digest.value.id), generation = loadGeneration
  const savedRevision = editRevision
  saving.value = true
  saveState.value = 'saving'
  try {
    const snapshot = JSON.parse(JSON.stringify({ title: digest.value.title, content: buildMarkdown(), sections: sections.value.map(section => ({ ...section, content: cleanReportCitationNotes(section.content, section.title) })), citations: citations.value, qualityIssues: issues.value, expectedVersion: digest.value.versionNo, expectedRevision: digest.value.revision, ...options }))
    const res = await updatePipelineResearchReport(id, snapshot)
    if (!active || generation !== loadGeneration || String(digest.value.id) !== id) return
    digest.value = { ...digest.value, ...res.data, title: digest.value.title }
    dirty = editRevision !== savedRevision
    saveState.value = dirty ? 'dirty' : 'saved'
    return true
  } catch (error) {
    if (!active || generation !== loadGeneration) return
    dirty = true
    saveState.value = 'error'
    ElMessage.error(error?.msg || error?.message || '自动保存失败，当前修改尚未保存')
  } finally {
    if (active && generation === loadGeneration) saving.value = false
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
  if (!active || isReadOnly.value || !currentSection.value) return
  const id = decimalId(item?.id)
  if (!id || item.category === 'paper' || item.type === 'paper') return ElMessage.warning('请选择有效的新闻资讯')
  const existing = citations.value.find(source => getCitationPath(source) === `/portal/news/${id}`)
  if (existing && (currentSection.value.citationIds || []).some(value => String(value) === String(existing.id))) return ElMessage.info('当前栏目已添加该资讯')
  const citation = existing || { id: citations.value.reduce((max, source) => Math.max(max, Number(source.id) || 0), 0) + 1, sourceId: id, type: 'article', title: item.title, location: item.time || item.publishTime || item.publish_time || item.published_at || '', quote: item.summary || '', source: item.source || '' }
  if (!existing) citations.value.push(citation)
  currentSection.value.citationIds = [...new Set([...(currentSection.value.citationIds || []), citation.id])]
  currentSection.value.sources = currentSection.value.citationIds.length
  currentSection.value.citations = currentSection.value.citationIds.length
  currentSection.value.status = String(currentSection.value.content || '').trim() ? 'complete' : 'draft'
  markSaving()
  ElMessage.success('已添加到当前栏目，并纳入来源清单')
}
function removeSource(id) {
  if (isReadOnly.value) return
  const section = currentSection.value
  section.citationIds = (section.citationIds || []).filter(item => String(item) !== String(id))
  // Protect Markdown links and code; match the whole reference number, never a prefix.
  let fence = null
  section.content = String(section.content || '').split('\n').map(line => {
    const marker = line.match(/^\s*(`{3,}|~{3,})/)
    if (marker) {
      if (!fence) fence = marker[1]
      else if (marker[1][0] === fence[0] && marker[1].length >= fence.length) fence = null
      return line
    }
    if (fence) return line
    return line.replace(/`+[^`\n]*`+|\[[^\]\n]*\]\([^\n)]*\)|\[([1-9]\d*)\](?!\()/g,
      (text, number) => number && number === String(id) ? '' : text)
  }).join('\n')
  section.words = section.content.length
  section.sources = section.citationIds.length
  section.citations = section.citationIds.length
  section.status = section.sources ? 'complete' : 'warning'
  markSaving()
}
function rebuildSection() {
  if (isReadOnly.value) return
  if (!currentSectionSources.value.length) {
    return ElMessage.warning('当前栏目没有关联来源，暂不能按证据重组')
  }
  if (currentSectionSources.value.some(item => typeof item.quote !== 'string' || !item.quote.trim())) {
    return ElMessage.warning('关联来源缺少摘录，请补充摘录后再重组')
  }
  const evidence = currentSectionSources.value.map(item => `${item.title}显示“${String(item.quote || '').slice(0, 90)}”[${item.id}]`).join('；')
  currentSection.value.content = `基于已关联来源整理：${evidence}\n\n以上内容仅作证据摘录与编辑起点，涉及工程决策时请打开原文复核。`
  currentSection.value.words = currentSection.value.content.length
  currentSection.value.status = currentSectionSources.value.length ? 'complete' : 'warning'
  markSaving()
  ElMessage.success('已按当前证据重组栏目研判')
}
async function saveVersion() {
  if (isReadOnly.value || versionSaving.value) return
  versionSaving.value = true
  clearTimeout(saveTimer)
  try {
    const versionSave = savePromise.then(() => saveCurrent())
    savePromise = versionSave
    if (!await versionSave) throw new Error('version save failed')
    ElMessage.success('修改已保存')
  } catch (error) {
    ElMessage.error('保存失败，当前修改仍保留在编辑页，请重试')
  } finally {
    versionSaving.value = false
  }
}
async function finalizeDigest() {
  if (isReadOnly.value) return
  try {
    await ensureSaved()
    await ElMessageBox.confirm('定稿后将保存当前内容并结束待复核状态，后续修改会重新进入草稿状态。', '确认复核并定稿', { confirmButtonText: '确认定稿', cancelButtonText: '继续编辑', type: 'warning' })
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
  if (!active || digest.value.readOnly) return false
  const id = String(digest.value.id), generation = loadGeneration
  const current = () => active && generation === loadGeneration && id === String(digest.value.id)
  const prefix = digest.value.requiresReview ? '草稿_' : ''
  const filename = `${prefix}${digest.value.title}.${format}`.replace(/[\\/:*?"<>|]/g, '_')
  const created = await createPipelineResearchReportExport(id, { format, allowDraft: digest.value.requiresReview })
  if (!current()) return false
  const exportId = created.data?.exportId
  if (!exportId) throw new Error('导出任务创建失败')
  activeTab.value = '导出记录'
  exportRefreshKey.value++
  for (let attempt = 0; attempt < 60; attempt += 1) {
    await new Promise(resolve => setTimeout(resolve, 500))
    if (!current()) return false
    let result
    try { result = await listPipelineResearchReportExports(id) }
    catch { throw new Error('导出任务已创建，状态暂时读取失败，可在导出记录中继续查看，无需重复提交。') }
    if (!current()) return false
    const item = (result.data?.rows || []).find(row => String(row.exportId) === String(exportId))
    if (item?.status === 'completed') {
      await downloadPipelineResearchReportExport(exportId, filename)
      if (current()) exportRefreshKey.value++
      return current()
    }
    if (item?.status === 'failed') throw new Error(item.errorMessage || '导出任务失败')
  }
  throw new Error('导出等待超时，请在导出记录中查看后续状态，完成后可直接下载，无需重复提交。')
}

async function exportDigest(format = 'markdown') {
  if (!active || digest.value.readOnly || exporting.value || !['markdown', 'docx', 'pdf'].includes(format)) return
  const id = String(digest.value.id), generation = loadGeneration
  const current = () => active && generation === loadGeneration && id === String(digest.value.id)
  exporting.value = true
  try {
    await ensureSaved()
    if (!current()) return
    const params = { allowDraft: digest.value.requiresReview }
    if (format === 'markdown') {
      const res = await exportPipelineResearchReport(id, params)
      if (!current()) return
      const blob = new Blob([res.data.content], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      try {
        const link = document.createElement('a')
        link.href = url; link.download = res.data.fileName || `${digest.value.title}.md`; link.click()
      } finally { URL.revokeObjectURL(url) }
      ElMessage.success(res.data.isDraft ? '草稿已导出' : '情报简报已导出')
    } else if (await waitAndDownloadExport(format)) ElMessage.success(`${format.toUpperCase()} 简报已导出`)
  } catch (error) {
    if (current()) ElMessage.error(error?.message === 'digest has unsaved changes' ? '当前修改未保存，请先重试保存' : error?.msg || error?.message || '导出失败，请稍后重试')
  } finally { if (current()) exporting.value = false }
}
async function loadDigest() {
  if (!active || loading.value) return
  const id = String(route.params.id), generation = ++loadGeneration
  loading.value = true
  loadError.value = ''
  try {
    const res = await getPipelineResearchReport(id)
    if (!active || generation !== loadGeneration || id !== String(route.params.id)) return
    if (!res.data) throw new Error('empty digest response')
    digest.value = { ...digest.value, ...res.data }
    sections.value = Array.isArray(res.data.sections) ? res.data.sections : []
    citations.value = res.data.citations || []
    issues.value = res.data.qualityIssues || []
    currentSectionId.value = sections.value[0]?.id
    loaded.value = true
  } catch (error) {
    if (!active || generation !== loadGeneration) return
    loadError.value = error?.msg || '情报简报加载失败，请确认后端服务和访问权限。'
    ElMessage.error('情报简报加载失败，请确认后端服务和访问权限')
  } finally {
    if (active && generation === loadGeneration) loading.value = false
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
  active = false
  loadGeneration++
  clearTimeout(saveTimer)
  window.removeEventListener('beforeunload', handleBeforeUnload)
})
</script>

<style scoped>
.ps-digest-intro { white-space: pre-wrap; }
.ps-citation-marker { position: static; vertical-align: super; font-size: .75em; line-height: 0; }
.ps-citation-marker a, .ps-digest-news h3 a, .ps-digest-sources a { color: var(--ps-blue); text-decoration: none; }
.ps-citation-marker a:hover, .ps-digest-news h3 a:hover, .ps-digest-sources a:hover { text-decoration: underline; }
.ps-digest-sources { list-style: none; padding: 0; margin: 0; }
.ps-digest-sources li { display: flex; gap: 10px; padding: 12px 0; border-bottom: 1px solid var(--ps-line-soft); }
.ps-digest-sources li > span { min-width: 20px; color: var(--ps-muted); }
.ps-digest-sources li > div { min-width: 0; }
.ps-digest-sources a, .ps-digest-sources strong { font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.ps-digest-sources small { display: block; color: var(--ps-muted); margin-top: 5px; overflow-wrap: anywhere; }
.ps-digest-candidate-content { padding: 0; }
@media (min-width: 1051px) {
  .ps-editor-inspector.is-picking-candidates { display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
  .is-picking-candidates .ps-inspector-tabs { flex-shrink: 0; }
  .is-picking-candidates .ps-digest-candidate-content { display: flex; flex: 1; min-height: 0; overflow: hidden; }
}
</style>
