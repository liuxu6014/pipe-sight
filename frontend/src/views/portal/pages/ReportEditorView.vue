<template>
  <div class="ps-editor-page">
    <div v-if="loading && !loaded" class="ps-detail-loading" aria-live="polite" aria-label="正在加载报告">
      <i></i><div><span></span><span></span><span></span></div>
    </div>
    <div v-else-if="loadError && !loaded" class="ps-inline-state is-warning" role="alert">
      <WarningFilled /><span>{{ loadError }}</span><button type="button" @click="loadReport">重新加载</button>
    </div>
    <template v-else-if="loaded">
    <header class="ps-editor-topbar">
      <div class="ps-editor-title"><button type="button" aria-label="返回科研工作台" @click="router.push('/portal/research')"><ArrowLeft /></button><span><strong>{{ report.title }}</strong><small>{{ reportTypeLabel }} · {{ report.version }}</small></span></div>
      <div class="ps-save-state"><span :class="{ 'is-saving': saving }"></span>{{ saveLabel }}<b>{{ wordCount.toLocaleString() }} 字</b></div>
      <div class="ps-editor-actions">
        <el-button :disabled="isReadOnly" :loading="versionSaving" @click="saveVersion"><CollectionTag />保存版本</el-button>
        <el-button :disabled="report.readOnly" @click="router.push(`/portal/research/reports/${report.id}/diagram`)"><Picture />查看配图</el-button>
        <el-button @click="openCurrentPreview"><View />预览</el-button>
        <el-button v-if="report.requiresReview" :disabled="isReadOnly" type="success" @click="finalizeReport"><CircleCheck />确认复核并定稿</el-button>
        <el-dropdown trigger="click" @command="exportReport">
          <el-button type="primary" :disabled="report.readOnly"><Download />{{ report.requiresReview ? '导出草稿' : '导出报告' }}<ArrowDown /></el-button>
          <template #dropdown><el-dropdown-menu>
            <el-dropdown-item command="markdown">Markdown 文档</el-dropdown-item>
            <el-dropdown-item command="docx">Word 文档</el-dropdown-item>
            <el-dropdown-item command="pdf">PDF 文档</el-dropdown-item>
          </el-dropdown-menu></template>
        </el-dropdown>
      </div>
    </header>
    <el-alert v-if="report.readOnly" title="正在只读查看其他用户的报告" description="可查看正文、引用和版本记录；编辑、恢复及导出文件由报告所有者操作。" type="info" :closable="false" show-icon />
    <el-alert v-else-if="isReadOnly" title="当前报告已正式发布，处于只读状态" description="预览、引用查看和导出仍可使用；如需修改，请先由管理员撤销发布。" type="info" :closable="false" show-icon />
    <el-alert v-if="report.requiresReview" title="当前报告为待复核草稿" :description="report.generationWarning || '该报告未完成全量模型生成，请配置可用模型或人工复核后再作为正式成果使用。'" type="warning" :closable="false" show-icon />
    <div class="ps-editor-layout">
      <aside class="ps-outline-panel">
        <div class="ps-editor-panel-head"><span>报告目录</span><button type="button" aria-label="新增章节" :disabled="isReadOnly" @click="addSection"><Plus /></button></div>
        <button v-for="(section, index) in sections" :key="section.id" type="button" :class="['ps-outline-item', { 'is-active': currentSectionId === section.id }]" :aria-current="currentSectionId === section.id ? 'location' : undefined" @click="scrollToSection(section.id)"><Rank /><span>{{ index + 1 }}</span><span><strong>{{ section.title }}</strong><small>{{ section.words }} 字 · {{ sectionCitationCount(section) }} 条引用</small></span><i :class="`is-${section.status}`"></i></button>
        <button class="ps-add-section" type="button" :disabled="isReadOnly" @click="addSection"><Plus />新增章节</button>
      </aside>

      <main ref="documentScrollRef" class="ps-document-editor" @scroll.passive="syncVisibleSection">
        <div class="ps-format-toolbar"><button v-for="tool in formatTools" :key="tool" type="button" :title="formatToolLabel(tool)" :aria-label="formatToolLabel(tool)" :disabled="isReadOnly" @click="applyFormat(tool)">{{ tool }}</button><span></span><button type="button" title="插入链接" aria-label="插入链接" disabled><Link /></button><button type="button" title="插入引用" aria-label="插入引用" disabled><CollectionTag /></button><button type="button" title="插入表格" aria-label="插入表格" disabled><Grid /></button><button type="button" title="插入图片" aria-label="插入图片" disabled><Picture /></button></div>
        <article class="ps-document-canvas" :class="{ 'is-read-only': isReadOnly }">
          <h1 :contenteditable="!isReadOnly" aria-label="编辑报告标题" @input="updateTitle">{{ report.title }}</h1>
          <div class="ps-doc-meta"><span>编制日期：{{ reportDateLabel }}</span></div>
          <section v-for="(section, index) in sections" :key="section.id" :ref="el => setSectionElement(section.id, el)" class="ps-editable-content ps-report-section" :aria-label="section.title" @focusin="activateSection(section.id)">
            <div class="ps-section-heading"><h2 :contenteditable="!isReadOnly" aria-label="编辑章节标题" @input="updateSectionTitle($event, section)">{{ section.title }}</h2><div class="ps-section-actions"><button type="button" title="章节上移" aria-label="章节上移" :disabled="isReadOnly || index <= 0" @click.stop="moveSection(-1, section.id)"><ArrowUp /></button><button type="button" title="章节下移" aria-label="章节下移" :disabled="isReadOnly || index >= sections.length - 1" @click.stop="moveSection(1, section.id)"><ArrowDown /></button><button type="button" title="删除章节" aria-label="删除章节" :disabled="isReadOnly || sections.length <= 1" @click.stop="removeSection(section.id)"><Delete /></button></div></div>
            <div :ref="el => setSectionBody(section.id, el)" class="ps-report-section-body" :contenteditable="!isReadOnly" :aria-label="`${section.title}正文`" @input="updateSectionContent($event, section)">
              <p v-for="(paragraph, paragraphIndex) in paragraphsFor(section)" :key="paragraphIndex" :class="{ 'ps-report-body-paragraph': isBodyParagraph(paragraph, section.title) }"><template v-for="(part, partIndex) in reportCitationParts(paragraph, section.title, citations.length)" :key="partIndex"><sup v-if="part.citation" class="ps-report-citation">{{ part.text }}</sup><template v-else>{{ part.text }}</template></template></p>
            </div>
          </section>
        </article>
      </main>

      <aside class="ps-editor-inspector">
        <div class="ps-inspector-tabs ps-report-inspector-tabs"><button v-for="tab in rightTabs" :key="tab" type="button" :class="{ 'is-active': activeRightTab === tab }" @click="activeRightTab = tab">{{ tab }}</button></div>
        <div v-if="activeRightTab === '引用来源'" class="ps-inspector-content"><div class="ps-inspector-summary"><strong>{{ citations.length }} 条引用</strong><span>引用均可回到来源条目</span></div><button v-for="source in citations" :key="source.id" type="button" class="ps-citation-card" :aria-label="`打开引用：${source.title}`" @click="openCitation(source)"><span>{{ source.type }}</span><strong>{{ source.title }}</strong><small>{{ source.location }}</small><p>{{ source.quote }}</p></button></div>
        <div v-else-if="activeRightTab === '版本记录'" class="ps-inspector-content"><div v-for="version in versions" :key="version.versionNo" class="ps-version-row"><span></span><div><strong>{{ version.name }}</strong><small>{{ version.time }} · {{ version.owner }}</small></div><el-dropdown @command="handleVersionCommand($event, version)"><button type="button" :aria-label="`${version.name}操作`"><MoreFilled /></button><template #dropdown><el-dropdown-menu><el-dropdown-item command="preview">预览</el-dropdown-item><el-dropdown-item command="compare">与当前版本对比</el-dropdown-item><el-dropdown-item command="restore" :disabled="isReadOnly">恢复此版本</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div><p v-if="!versions.length" class="ps-inspector-empty">还没有可用的历史版本</p><div v-if="publications.length" class="ps-publication-history"><strong>正式发布记录</strong><p v-for="item in publications" :key="item.publicationId"><span>{{ item.actionLabel }} · V{{ item.reportVersionNo }}.0</span><small>{{ item.createdAt }} · {{ item.operator }}<br />{{ item.note || '未填写说明' }}</small></p></div></div>
        <div v-else class="ps-inspector-content"><div class="ps-inspector-summary"><strong>{{ exports.length }} 次导出</strong><el-button text size="small" @click="loadExports">刷新</el-button></div><div v-for="item in exports" :key="item.exportId" class="ps-export-row"><div><strong>{{ exportFormatLabel(item.format) }} · {{ item.fileName }}</strong><small>{{ exportStatusLabel(item.status) }} · {{ item.updatedAt || item.createdAt }}</small><p v-if="item.errorMessage">{{ item.errorMessage }}</p></div><div class="ps-export-actions"><el-button v-if="item.status === 'completed'" :disabled="report.readOnly" text type="primary" @click="downloadExportItem(item)">下载</el-button><el-button v-else-if="item.status === 'failed'" :disabled="report.readOnly" text type="warning" @click="reExport(item)">重新导出</el-button></div></div><p v-if="!exports.length" class="ps-inspector-empty">还没有导出记录</p></div>
      </aside>
    </div>
    <el-dialog v-model="previewVisible" :title="previewDocument.version ? `报告预览 · ${previewDocument.version}` : '报告预览'" width="880px"><div class="ps-preview-paper"><h1>{{ previewDocument.title }}</h1><template v-for="(section, index) in previewDocument.sections" :key="section.id || index"><h2>{{ index + 1 }}. {{ section.title }}</h2><p v-for="paragraph in String(section.content || '本章节暂无正文').split(/\n+/).filter(Boolean)" :key="paragraph" :class="{ 'ps-report-body-paragraph': isBodyParagraph(paragraph, section.title) }"><template v-for="(part, partIndex) in reportCitationParts(paragraph, section.title, previewDocument.citations?.length ?? citations.length)" :key="partIndex"><sup v-if="part.citation" class="ps-report-citation">{{ part.text }}</sup><template v-else>{{ part.text }}</template></template></p></template></div></el-dialog>
    <el-dialog v-model="compareVisible" title="版本对比" width="1120px"><div class="ps-version-compare"><section><h3>当前版本 · {{ report.version }}</h3><pre>{{ buildMarkdown() }}</pre></section><section><h3>历史版本 · {{ comparisonVersion.version }}</h3><pre>{{ comparisonVersion.content }}</pre></section></div></el-dialog>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getToken } from '@/utils/auth'
import { openPortalContent } from '@/utils/portal/openContent'
import { getCitationPath } from '@/utils/portal/citationRouting'
import { buildReportMarkdown, cleanReportCitationNotes, reportCitationParts } from '@/utils/portal/reportDocument'
import { ArrowDown, ArrowLeft, ArrowUp, CircleCheck, CollectionTag, Delete, Download, Grid, Link, MoreFilled, Picture, Plus, Rank, View, WarningFilled } from '@element-plus/icons-vue'
import usePortalStore from '@/store/modules/portal'
import { createPipelineResearchReportExport, downloadPipelineResearchReportExport, exportPipelineResearchReport, finalizePipelineResearchReport, getPipelineResearchReport, getPipelineResearchReportVersion, listPipelineResearchReportExports, listPipelineResearchReportPublications, listPipelineResearchReportVersions, restorePipelineResearchReportVersion, updatePipelineResearchReport } from '@/api/pipeline/intelligence'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const report = ref(portalStore.researchReports.find(item => item.id === route.params.id) || { id: String(route.params.id), title: '报告标题待补充', type: 'research-demand', version: '版本待补充', words: 0 })
const loading = ref(false)
const loaded = ref(false)
const loadError = ref('')
const saving = ref(false)
const versionSaving = ref(false)
const saveState = ref('saved')
const previewVisible = ref(false)
const editorContentRef = ref()
const documentScrollRef = ref()
const sectionElements = new Map()
const sectionBodies = new Map()
const currentSectionId = ref(1)
const activeRightTab = ref('引用来源')
const wordCount = ref(0)
const versionPreview = ref(null)
const compareVisible = ref(false)
const comparisonVersion = ref({ version: '', content: '' })
const formatTools = ['H1', 'H2', 'B', 'I', '•', '1.']
const rightTabs = ['引用来源', '版本记录', '导出记录']
const sections = ref([{ id: 1, title: '新建章节', content: '', words: 0, citations: 0, status: 'draft' }])
const citations = ref([])
const versions = ref([])
const publications = ref([])
const exports = ref([])
const currentSection = computed(() => sections.value.find(item => item.id === currentSectionId.value) || sections.value[0])
const currentSectionIndex = computed(() => sections.value.findIndex(item => item.id === currentSectionId.value))
const isReadOnly = computed(() => Boolean(report.value.readOnly) || report.value.status === 'published')
function paragraphsFor(section) { return String(section?.content || '').split(/\n+/).filter(Boolean) }
function setSectionElement(id, element) {
  if (element) sectionElements.set(id, element)
  else sectionElements.delete(id)
}
function setSectionBody(id, element) {
  if (element) sectionBodies.set(id, element)
  else sectionBodies.delete(id)
  if (id === currentSectionId.value) editorContentRef.value = element
}
function activateSection(id) {
  currentSectionId.value = id
  editorContentRef.value = sectionBodies.get(id)
}
function scrollToSection(id) {
  activateSection(id)
  sectionElements.get(id)?.scrollIntoView({ block: 'start', behavior: 'auto' })
}
function syncVisibleSection() {
  if (!documentScrollRef.value) return
  const top = documentScrollRef.value.getBoundingClientRect().top + 80
  let active = sections.value[0]?.id
  for (const section of sections.value) {
    const element = sectionElements.get(section.id)
    if (element && element.getBoundingClientRect().top <= top) active = section.id
  }
  const scroller = documentScrollRef.value
  if (scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 2) active = sections.value.at(-1)?.id
  if (active != null && active !== currentSectionId.value) activateSection(active)
}
const reportTypeLabel = computed(() => ({ research: '科研报告', 'research-demand': '科研需求报告', 'technology-route': '技术路线报告', 'project-demand': '科技项目需求填报表' })[report.value.type] || report.value.type || '科研报告')
const reportDateLabel = computed(() => {
  const value = report.value.createdAt || report.value.created_at || report.value.updatedAt || report.value.updated_at || ''
  return value ? String(value).slice(0, 10) : '编制日期待补充'
})
const previewDocument = computed(() => versionPreview.value || { title: report.value.title, version: report.value.version, sections: sections.value })
function sectionCitationCount(section) {
  if (Array.isArray(section?.citationIds)) {
    const available = new Set(citations.value.map(item => String(item?.id)))
    return section.citationIds.filter(id => available.has(String(id))).length
  }
  return Number(section?.citations || 0)
}
let saveTimer
let dirty = false
let editRevision = 0
let savePromise = Promise.resolve()
const saveLabel = computed(() => ({ saved: '已保存', dirty: '有未保存修改', saving: '正在保存…', error: '保存失败，请重试' })[saveState.value] || '保存状态未知')
watch(() => [report.value?.id, report.value?.words], ([, words]) => { wordCount.value = Number(words || 0) }, { immediate: true })
watch(activeRightTab, tab => { if (tab === '导出记录') loadExports() })
function isBodyParagraph(paragraph, title) {
  return !['参考资料', '参考文献', 'references'].includes(String(title || '').trim().toLowerCase())
    && !/^(?:#{1,6}\s|[一二三四五六七八九十百]+[、．])/.test(String(paragraph || '').trim())
}
function buildMarkdown() { return buildReportMarkdown({ title: report.value.title, sections: sections.value, citations: citations.value }) }
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
    const snapshot = JSON.parse(JSON.stringify({ title: report.value.title, content: buildMarkdown(), sections: sections.value.map(section => ({ ...section, content: cleanReportCitationNotes(section.content, section.title) })), citations: citations.value, expectedVersion: report.value.versionNo, expectedRevision: report.value.revision, ...options }))
    const res = await updatePipelineResearchReport(report.value.id, snapshot)
    // 只更新服务端版本等信息，保留请求期间产生的本地编辑。
    report.value = { ...report.value, ...res.data, title: report.value.title }
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
  if (dirty || saveState.value === 'error') throw new Error('report has unsaved changes')
}
function updateTitle(event) { if (isReadOnly.value) return; report.value.title = event.currentTarget.innerText.trim() || report.value.title; markSaving() }
function updateSectionTitle(event, section = currentSection.value) {
  if (isReadOnly.value) return
  const title = event.currentTarget.innerText.trim()
  if (!title) return
  section.title = title
  markSaving()
}
function updateSectionContent(event, section = currentSection.value) { if (isReadOnly.value) return; section.content = event.currentTarget.innerText.trim(); section.words = section.content.length; wordCount.value = sections.value.reduce((sum, item) => sum + Number(item.words || 0), 0); markSaving() }
function formatToolLabel(tool) { return ({ H1: '一级标题', H2: '二级标题', B: '粗体', I: '斜体', '•': '无序列表', '1.': '有序列表' })[tool] || tool }
function formatText(value, tool) {
  const text = String(value || '').trim() || ({ H1: '一级标题', H2: '二级标题', B: '粗体文本', I: '斜体文本', '•': '列表项', '1.': '列表项' })[tool] || '请输入内容'
  if (tool === 'H1') return `# ${text.replace(/^#{1,6}\s+/, '')}`
  if (tool === 'H2') return `## ${text.replace(/^#{1,6}\s+/, '')}`
  if (tool === 'B') return text.startsWith('**') && text.endsWith('**') ? text.slice(2, -2) : `**${text}**`
  if (tool === 'I') return text.startsWith('*') && text.endsWith('*') ? text.slice(1, -1) : `*${text}*`
  if (tool === '•') return text.split(/\n+/).map(line => /^\s*[-*+]\s+/.test(line) ? line : `- ${line}`).join('\n')
  if (tool === '1.') return text.split(/\n+/).map((line, index) => /^\s*\d+[.)]\s+/.test(line) ? line : `${index + 1}. ${line}`).join('\n')
  return text
}
function applyFormat(tool) {
  if (isReadOnly.value) return
  const selection = window.getSelection?.()
  const selectedText = selection?.toString?.().trim() || ''
  const selectedSection = selection?.rangeCount && sections.value.find(section => sectionBodies.get(section.id)?.contains(selection.anchorNode))
  if (selectedText && selectedSection && document.execCommand?.('insertText', false, formatText(selectedText, tool))) {
    activateSection(selectedSection.id)
    updateSectionContent({ currentTarget: sectionBodies.get(selectedSection.id) }, selectedSection)
    return
  }
  currentSection.value.content = formatText(currentSection.value.content, tool)
  currentSection.value.words = currentSection.value.content.length
  wordCount.value = sections.value.reduce((sum, item) => sum + Number(item.words || 0), 0)
  markSaving()
}
function handleBeforeUnload(event) {
  if (!dirty) return
  event.preventDefault()
  event.returnValue = ''
}
function addSection() { if (isReadOnly.value) return; const id = Date.now(); sections.value.push({ id, title: '新增章节', content: '', words: 0, citations: 0, status: 'draft' }); currentSectionId.value = id; markSaving(); nextTick(() => scrollToSection(id)) }
function moveSection(offset, sectionId = currentSectionId.value) {
  if (isReadOnly.value) return
  activateSection(sectionId)
  const index = currentSectionIndex.value
  const target = index + offset
  if (index < 0 || target < 0 || target >= sections.value.length) return
  const reordered = sections.value.slice()
  ;[reordered[index], reordered[target]] = [reordered[target], reordered[index]]
  sections.value = reordered
  markSaving()
}
async function removeSection(sectionId = currentSectionId.value) {
  if (isReadOnly.value || sections.value.length <= 1) return
  activateSection(sectionId)
  const section = currentSection.value
  try {
    await ElMessageBox.confirm(`删除“${section.title}”后将从当前报告中移除该章节，是否继续？`, '删除章节', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    const index = sections.value.findIndex(item => item.id === sectionId)
    if (index < 0) return
    sections.value.splice(index, 1)
    currentSectionId.value = sections.value[Math.max(0, index - 1)]?.id || sections.value[0].id
    markSaving()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error('删除章节失败，请稍后重试')
  }
}
async function saveVersion() {
  if (isReadOnly.value || versionSaving.value) return
  versionSaving.value = true
  clearTimeout(saveTimer)
  try {
    const versionSave = savePromise.then(() => saveCurrent({ saveVersion: true, versionSource: 'manual' }))
    savePromise = versionSave
    if (!await versionSave) throw new Error('version save failed')
    await loadVersions()
    ElMessage.success('已保存为新的可恢复版本')
  } catch (error) {
    ElMessage.error('版本保存失败，当前修改仍保留在编辑页，请重试')
  } finally {
    versionSaving.value = false
  }
}
async function finalizeReport() {
  try {
    await ensureSaved()
    await ElMessageBox.confirm('定稿后将保留当前版本并结束待复核状态，后续修改会重新进入草稿状态。', '确认复核并定稿', { confirmButtonText: '确认定稿', cancelButtonText: '继续编辑', type: 'warning' })
    const res = await finalizePipelineResearchReport(report.value.id, { expectedVersion: report.value.versionNo, expectedRevision: report.value.revision })
    report.value = { ...report.value, ...res.data, title: report.value.title }
    await portalStore.hydrate(true)
    ElMessage.success('报告已定稿')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error?.msg || '报告定稿失败，请刷新后重试')
  }
}
async function waitAndDownloadExport(format) {
  const prefix = report.value.requiresReview ? '草稿_' : ''
  const filename = `${prefix}${report.value.title}.${format}`.replace(/[\\/:*?"<>|]/g, '_')
  const created = await createPipelineResearchReportExport(report.value.id, { format, allowDraft: report.value.requiresReview })
  const exportId = created.data?.exportId
  if (!exportId) throw new Error('导出任务创建失败')
  for (let attempt = 0; attempt < 60; attempt += 1) {
    await new Promise(resolve => setTimeout(resolve, 500))
    const result = await listPipelineResearchReportExports(report.value.id)
    const item = (result.data?.rows || []).find(row => row.exportId === exportId)
    if (item?.status === 'completed') {
      await downloadPipelineResearchReportExport(exportId, filename)
      await loadExports()
      return
    }
    if (item?.status === 'failed') throw new Error(item.errorMessage || '导出任务失败')
  }
  throw new Error('导出任务处理超时，请稍后在导出记录中重试')
}

function exportFormatLabel(format) { return ({ markdown: 'Markdown', docx: 'Word', pdf: 'PDF' })[format] || String(format || '').toUpperCase() }
function exportStatusLabel(status) { return ({ queued: '排队中', running: '生成中', completed: '已完成', failed: '失败' })[status] || '处理中' }
async function loadExports() {
  try {
    const res = await listPipelineResearchReportExports(report.value.id)
    exports.value = res.data?.rows || []
  } catch (error) {
    exports.value = []
  }
}
async function downloadExportItem(item) {
  if (report.value.readOnly) return
  try {
    const filename = item.fileName || `${report.value.title}.${item.format}`
    await downloadPipelineResearchReportExport(item.exportId, filename)
  } catch (error) {
    ElMessage.error('导出文件下载失败，请稍后重试')
  }
}
async function reExport(item) {
  if (report.value.readOnly) return
  try {
    await ensureSaved()
    await createPipelineResearchReportExport(report.value.id, { format: item.format, allowDraft: report.value.requiresReview })
    await loadExports()
    ElMessage.success('已重新创建导出任务')
  } catch (error) {
    ElMessage.error(error?.msg || '重新导出失败，请稍后重试')
  }
}

async function exportReport(format = 'markdown') { try { await ensureSaved(); const params = { allowDraft: report.value.requiresReview }; if (format === 'markdown') { const res = await exportPipelineResearchReport(report.value.id, params); const blob = new Blob([res.data.content], { type: 'text/markdown;charset=utf-8' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = res.data.fileName || `${report.value.title}.md`; link.click(); URL.revokeObjectURL(url); ElMessage.success(res.data.isDraft ? '草稿已导出' : 'Markdown 报告已导出') } else { await waitAndDownloadExport(format); ElMessage.success(`${format.toUpperCase()} 报告已导出`) } } catch (error) { ElMessage.error(error.message === 'report has unsaved changes' ? '当前修改未保存，请先重试保存' : error?.msg || '报告导出失败') } }
async function loadVersions() {
  try {
    const res = await listPipelineResearchReportVersions(report.value.id)
    versions.value = (res.data?.rows || []).map(item => ({ ...item, name: `${item.version} ${item.source === 'generated' ? '生成版本' : item.source === 'restored' ? '恢复版本' : '人工版本'}`, time: item.createdAt, owner: item.operator }))
  } catch (error) {
    versions.value = []
    ElMessage.warning('版本记录暂时无法加载')
  }
}
async function loadPublications() {
  try {
    const res = await listPipelineResearchReportPublications(report.value.id)
    publications.value = res.data?.rows || []
  } catch (error) {
    publications.value = []
  }
}
function openCitation(source) {
  const path = getCitationPath(source)
  if (path) return openPortalContent(router, path)
  const externalUrl = source?.url || source?.sourceUrl || ''
  if (/^https?:\/\//i.test(String(externalUrl))) {
    window.open(externalUrl, '_blank', 'noopener,noreferrer')
    return
  }
  ElMessage.info('该引用只有快照信息，当前没有可跳转的来源地址')
}
function openCurrentPreview() { versionPreview.value = null; previewVisible.value = true }
async function loadVersion(version) {
  const res = await getPipelineResearchReportVersion(report.value.id, version.versionNo)
  return res.data
}
async function previewVersion(version) {
  try {
    versionPreview.value = await loadVersion(version)
    previewVisible.value = true
  } catch (error) {
    ElMessage.error('历史版本加载失败')
  }
}
async function compareVersion(version) {
  try {
    comparisonVersion.value = await loadVersion(version)
    compareVisible.value = true
  } catch (error) {
    ElMessage.error('版本对比加载失败')
  }
}
async function restoreVersion(version) {
  if (isReadOnly.value) {
    ElMessage.info('已发布报告为只读状态，请先由管理员撤销发布')
    return
  }
  try {
    await ElMessageBox.confirm(`恢复 ${version.name} 后，系统会保留当前内容并生成一个新的恢复版本。`, '恢复历史版本', { confirmButtonText: '确认恢复', cancelButtonText: '取消', type: 'warning' })
    await restorePipelineResearchReportVersion(report.value.id, version.versionNo)
    await loadReport()
    ElMessage.success('历史版本已恢复，并保存为新的可追溯版本')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error('历史版本恢复失败')
  }
}
function handleVersionCommand(command, version) {
  if (command === 'preview') return previewVersion(version)
  if (command === 'compare') return compareVersion(version)
  if (command === 'restore') return restoreVersion(version)
}
async function loadReport() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await getPipelineResearchReport(String(route.params.id))
    if (!res.data) throw new Error('empty report response')
    report.value = { ...report.value, ...res.data }
    if (res.data.sections?.length) { sections.value = res.data.sections; currentSectionId.value = sections.value[0].id }
    citations.value = res.data.citations || []
    wordCount.value = Number(res.data.words || 0)
    await Promise.all([loadVersions(), loadExports()])
    loaded.value = true
  } catch (error) {
    loadError.value = error?.msg || '报告加载失败，请确认后端服务和访问权限。'
    ElMessage.error('报告加载失败，请确认后端服务和访问权限')
  } finally {
    loading.value = false
  }
}
onMounted(() => {
  loadReport()
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

<style scoped>
.ps-report-section {
  scroll-margin-top: 64px;
}
.ps-report-section-body {
  min-height: 2em;
  outline: none;
}
.ps-report-inspector-tabs {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.ps-report-body-paragraph {
  text-indent: 2em;
}
.ps-report-citation {
  position: static;
  vertical-align: super;
  font-size: .75em;
  line-height: 0;
}
</style>
