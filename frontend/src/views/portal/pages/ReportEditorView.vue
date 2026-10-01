<template>
  <div class="ps-editor-page">
    <header class="ps-editor-topbar">
      <div class="ps-editor-title"><button type="button" aria-label="返回科研工作台" @click="router.push('/portal/research')"><ArrowLeft /></button><span><strong>{{ report.title }}</strong><small>{{ reportTypeLabel }} · {{ report.version }}</small></span></div>
      <div class="ps-save-state"><span :class="{ 'is-saving': saving }"></span>{{ saveLabel }}<b>{{ wordCount.toLocaleString() }} 字</b></div>
      <div class="ps-editor-actions"><el-button @click="saveVersion"><CollectionTag />保存版本</el-button><el-button @click="openCurrentPreview"><View />预览</el-button><el-button type="primary" @click="exportReport"><Download />导出 Markdown</el-button></div>
    </header>
    <div class="ps-editor-layout">
      <aside class="ps-outline-panel">
        <div class="ps-editor-panel-head"><span>报告目录</span><button type="button" @click="addSection"><Plus /></button></div>
        <div class="ps-completeness"><span><b>完整性</b><strong>{{ completeness }}%</strong></span><i><span :style="{ width: `${completeness}%` }"></span></i><small>{{ incompleteCount ? `${incompleteCount} 个章节需要补充正文或证据` : '章节正文与证据已完成基础覆盖' }}</small></div>
        <button v-for="(section, index) in sections" :key="section.id" type="button" :class="['ps-outline-item', { 'is-active': currentSectionId === section.id }]" @click="currentSectionId = section.id"><Rank /><span>{{ index + 1 }}</span><span><strong>{{ section.title }}</strong><small>{{ section.words }} 字 · {{ section.citations }} 条引用</small></span><i :class="`is-${section.status}`"></i></button>
        <button class="ps-add-section" type="button" @click="addSection"><Plus />新增章节</button>
      </aside>

      <main class="ps-document-editor">
        <div class="ps-format-toolbar"><button v-for="tool in formatTools" :key="tool" type="button" :title="tool">{{ tool }}</button><span></span><button type="button" title="插入链接"><Link /></button><button type="button" title="插入引用"><CollectionTag /></button><button type="button" title="插入表格"><Grid /></button><button type="button" title="插入图片"><Picture /></button></div>
        <article class="ps-document-canvas">
          <div class="ps-doc-kicker">{{ report.type }} · {{ report.version }}</div>
          <h1 contenteditable="true" @input="updateTitle">{{ report.title }}</h1>
          <div class="ps-doc-meta"><span>编制部门：完整性技术中心</span><span>编制日期：2026年8月</span></div>
          <section ref="editorContentRef" contenteditable="true" class="ps-editable-content" @input="updateSectionContent">
            <h2>{{ currentSection.title }}</h2>
            <p v-for="paragraph in sectionParagraphs" :key="paragraph">{{ paragraph }}</p>
          </section>
        </article>
      </main>

      <aside class="ps-editor-inspector">
        <div class="ps-inspector-tabs"><button v-for="tab in rightTabs" :key="tab" type="button" :class="{ 'is-active': activeRightTab === tab }" @click="activeRightTab = tab">{{ tab }}</button></div>
        <div v-if="activeRightTab === '引用来源'" class="ps-inspector-content"><div class="ps-inspector-summary"><strong>{{ citations.length }} 条引用</strong><span>引用均可回到来源条目</span></div><button v-for="source in citations" :key="source.id" type="button" class="ps-citation-card"><span>{{ source.type }}</span><strong>{{ source.title }}</strong><small>{{ source.location }}</small><p>{{ source.quote }}</p></button></div>
        <div v-else-if="activeRightTab === '质量问题'" class="ps-inspector-content"><div v-for="issue in issues" :key="issue.title" class="ps-quality-card" :class="`is-${issue.level}`"><span>{{ issue.levelLabel }}</span><strong>{{ issue.title }}</strong><p>{{ issue.description }}</p><el-button text @click="locateIssue(issue)">定位并处理</el-button></div><p v-if="!issues.length" class="ps-inspector-empty">当前没有待处理的质量问题</p></div>
        <div v-else class="ps-inspector-content"><div v-for="version in versions" :key="version.versionNo" class="ps-version-row"><span></span><div><strong>{{ version.name }}</strong><small>{{ version.time }} · {{ version.owner }}</small></div><el-dropdown @command="handleVersionCommand($event, version)"><button type="button" :aria-label="`${version.name}操作`"><MoreFilled /></button><template #dropdown><el-dropdown-menu><el-dropdown-item command="preview">预览</el-dropdown-item><el-dropdown-item command="compare">与当前版本对比</el-dropdown-item><el-dropdown-item command="restore">恢复此版本</el-dropdown-item></el-dropdown-menu></template></el-dropdown></div><p v-if="!versions.length" class="ps-inspector-empty">还没有可用的历史版本</p></div>
      </aside>
    </div>
    <el-dialog v-model="previewVisible" :title="previewDocument.version ? `报告预览 · ${previewDocument.version}` : '报告预览'" width="880px"><div class="ps-preview-paper"><h1>{{ previewDocument.title }}</h1><template v-for="(section, index) in previewDocument.sections" :key="section.id || index"><h2>{{ index + 1 }}. {{ section.title }}</h2><p v-for="paragraph in String(section.content || '本章节暂无正文').split(/\n+/).filter(Boolean)" :key="paragraph">{{ paragraph }}</p></template></div></el-dialog>
    <el-dialog v-model="compareVisible" title="版本对比" width="1120px"><div class="ps-version-compare"><section><h3>当前版本 · {{ report.version }}</h3><pre>{{ buildMarkdown() }}</pre></section><section><h3>历史版本 · {{ comparisonVersion.version }}</h3><pre>{{ comparisonVersion.content }}</pre></section></div></el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, CollectionTag, Download, Grid, Link, MoreFilled, Picture, Plus, Rank, View } from '@element-plus/icons-vue'
import usePortalStore from '@/store/modules/portal'
import { exportPipelineResearchReport, getPipelineResearchReport, getPipelineResearchReportVersion, listPipelineResearchReportVersions, restorePipelineResearchReportVersion, updatePipelineResearchReport } from '@/api/pipeline/intelligence'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const report = ref(portalStore.researchReports.find(item => item.id === route.params.id) || { id: String(route.params.id), title: '科研报告', type: 'research-demand', version: 'V1.0', words: 0 })
const saving = ref(false)
const saveState = ref('saved')
const previewVisible = ref(false)
const editorContentRef = ref()
const currentSectionId = ref(1)
const activeRightTab = ref('引用来源')
const wordCount = ref(0)
const versionPreview = ref(null)
const compareVisible = ref(false)
const comparisonVersion = ref({ version: '', content: '' })
const formatTools = ['H1', 'H2', 'B', 'I', '•', '1.']
const rightTabs = ['引用来源', '质量问题', '版本记录']
const sections = ref([{ id: 1, title: '新建章节', content: '', words: 0, citations: 0, status: 'draft' }])
const citations = ref([])
const issues = ref([])
const versions = ref([])
const currentSection = computed(() => sections.value.find(item => item.id === currentSectionId.value) || sections.value[0])
const sectionParagraphs = computed(() => String(currentSection.value?.content || '当前章节暂无正文，请直接编辑补充。').split(/\n+/).filter(Boolean))
const reportTypeLabel = computed(() => ({ 'research-demand': '科研需求报告', 'technology-route': '技术路线报告', 'project-demand': '科技项目需求填报表' })[report.value.type] || report.value.type || '科研报告')
const previewDocument = computed(() => versionPreview.value || { title: report.value.title, version: report.value.version, sections: sections.value })
const incompleteCount = computed(() => sections.value.filter(section => !section.content?.trim() || Number(section.citations || 0) < 1).length)
const completeness = computed(() => {
  if (!sections.value.length) return 0
  const earned = sections.value.reduce((score, section) => score + (section.content?.trim() ? 60 : 0) + (Number(section.citations || 0) > 0 ? 40 : 0), 0)
  return Math.round(earned / sections.value.length)
})
let saveTimer
let dirty = false
let savePromise = Promise.resolve()
const saveLabel = computed(() => ({ saved: '已保存', dirty: '有未保存修改', saving: '正在保存…', error: '保存失败，请重试' })[saveState.value] || '保存状态未知')
watch(() => [report.value?.id, report.value?.words], ([, words]) => { wordCount.value = Number(words || 0) }, { immediate: true })
function buildMarkdown() { return [`# ${report.value.title}`, '', ...sections.value.flatMap((section, index) => [`## ${index + 1}. ${section.title}`, '', section.content || '', '']), '## 参考资料', '', ...citations.value.map(item => `[${item.id}] ${item.title}（${item.source || item.type}，${item.location || '来源条目'}）`)].join('\n') }
function markSaving() {
  dirty = true
  saveState.value = 'dirty'
  saving.value = true
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => { savePromise = savePromise.then(saveCurrent) }, 700)
}
async function saveCurrent() {
  if (!dirty) return
  dirty = false
  saving.value = true
  saveState.value = 'saving'
  try {
    const res = await updatePipelineResearchReport(report.value.id, { title: report.value.title, content: buildMarkdown(), sections: sections.value, citations: citations.value, expectedVersion: report.value.versionNo, expectedRevision: report.value.revision })
    report.value = { ...report.value, ...res.data }
    saveState.value = dirty ? 'dirty' : 'saved'
  } catch (error) {
    dirty = true
    saveState.value = 'error'
    ElMessage.error('自动保存失败，当前修改尚未保存')
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
function updateTitle(event) { report.value.title = event.currentTarget.innerText.trim() || report.value.title; markSaving() }
function updateSectionContent(event) { currentSection.value.content = event.currentTarget.innerText.replace(currentSection.value.title, '').trim(); currentSection.value.words = currentSection.value.content.length; wordCount.value = sections.value.reduce((sum, item) => sum + Number(item.words || 0), 0); markSaving() }
function handleBeforeUnload(event) {
  if (!dirty) return
  event.preventDefault()
  event.returnValue = ''
}
function addSection() { const id = Date.now(); sections.value.push({ id, title: '新增章节', content: '', words: 0, citations: 0, status: 'draft' }); currentSectionId.value = id; markSaving() }
async function saveVersion() { try { await ensureSaved(); const res = await updatePipelineResearchReport(report.value.id, { title: report.value.title, content: buildMarkdown(), sections: sections.value, citations: citations.value, expectedVersion: report.value.versionNo, expectedRevision: report.value.revision, saveVersion: true, versionSource: 'manual' }); report.value = { ...report.value, ...res.data }; await loadVersions(); ElMessage.success('已保存为新的可恢复版本') } catch (error) { ElMessage.error(error.message === 'report has unsaved changes' ? '当前修改未保存，无法创建版本' : '版本保存失败，请刷新后重试') } }
async function exportReport() { try { await ensureSaved(); const res = await exportPipelineResearchReport(report.value.id); const blob = new Blob([res.data.content], { type: 'text/markdown;charset=utf-8' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = res.data.fileName || `${report.value.title}.md`; link.click(); URL.revokeObjectURL(url); ElMessage.success('Markdown 报告已导出') } catch (error) { ElMessage.error(error.message === 'report has unsaved changes' ? '当前修改未保存，请先重试保存' : '报告导出失败') } }
async function loadVersions() {
  try {
    const res = await listPipelineResearchReportVersions(report.value.id)
    versions.value = (res.data?.rows || []).map(item => ({ ...item, name: `${item.version} ${item.source === 'generated' ? '生成版本' : item.source === 'restored' ? '恢复版本' : '人工版本'}`, time: item.createdAt, owner: item.operator }))
  } catch (error) {
    versions.value = []
    ElMessage.warning('版本记录暂时无法加载')
  }
}
function locateIssue(issue) {
  if (issue.sectionId && sections.value.some(section => section.id === issue.sectionId)) currentSectionId.value = issue.sectionId
  activeRightTab.value = '引用来源'
  editorContentRef.value?.focus()
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
  try {
    const res = await getPipelineResearchReport(String(route.params.id))
    report.value = { ...report.value, ...res.data }
    if (res.data.sections?.length) { sections.value = res.data.sections; currentSectionId.value = sections.value[0].id }
    citations.value = res.data.citations || []
    issues.value = (res.data.qualityIssues || []).map(item => ({ ...item, levelLabel: ({ high: '高', medium: '中', low: '低' })[item.level] || item.level }))
    wordCount.value = Number(res.data.words || 0)
    await loadVersions()
  } catch (error) {
    ElMessage.error('报告加载失败，请确认后端服务和访问权限')
  }
}
onMounted(() => {
  loadReport()
  window.addEventListener('beforeunload', handleBeforeUnload)
})
onBeforeRouteLeave(async () => {
  if (!dirty) return true
  try {
    await ensureSaved()
    return true
  } catch (error) {
    ElMessage.warning('当前修改尚未保存，已留在编辑页')
    return false
  }
})
onBeforeUnmount(() => {
  clearTimeout(saveTimer)
  window.removeEventListener('beforeunload', handleBeforeUnload)
})
</script>
