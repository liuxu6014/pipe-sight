<template>
  <div class="ps-editor-page">
    <div v-if="loading && !loaded" class="ps-detail-loading" aria-live="polite" aria-label="正在加载报告">
      <i></i><div><span></span><span></span><span></span></div>
    </div>
    <div v-else-if="loadError && !loaded" class="ps-inline-state is-warning" role="alert">
      <WarningFilled /><span>{{ loadError }}</span><el-button class="ps-ui-action" @click="loadReport">重新加载</el-button>
      <el-button @click="returnToPreviousPage(router, isDigest ? '/portal/digests' : '/portal/research')">返回上一页</el-button>
    </div>
    <template v-else-if="loaded">
    <header class="ps-editor-topbar">
      <div class="ps-editor-title"><el-button :icon="ArrowLeft" circle class="ps-ui-action" aria-label="返回上一页" title="返回上一页" @click="returnToPreviousPage(router, isDigest ? '/portal/digests' : '/portal/research')" /><span><strong>{{ report.title }}</strong><small>{{ reportTypeLabel }}</small></span></div>
      <div class="ps-save-state"><span :class="{ 'is-saving': saving }"></span>{{ saveLabel }}<b>{{ wordCount.toLocaleString() }} 字</b></div>
      <div class="ps-editor-actions">
        <el-button :type="outlineVisible ? 'primary' : 'default'" :plain="outlineVisible" :aria-pressed="outlineVisible" @click="outlineVisible = !outlineVisible">目录</el-button>
        <el-button :aria-pressed="inspectorVisible" @click="inspectorVisible = !inspectorVisible">引用与记录</el-button>
        <el-button v-if="!isReadOnly" :type="isEditing ? 'default' : 'primary'" @click="toggleEditing">{{ isEditing ? '完成编辑' : '编辑报告' }}</el-button>
        <el-button :icon="CollectionTag" v-if="isEditing" :disabled="isReadOnly" :loading="versionSaving" @click="saveVersion">保存修改</el-button>
        <el-button :icon="Picture" v-if="isEditing" :disabled="report.readOnly" @click="router.push(`/portal/research/reports/${report.id}/diagram`)">查看配图</el-button>
        <el-button v-if="isDigest" :icon="View" @click="openCurrentPreview">预览</el-button>
        <el-button :icon="CircleCheck" v-if="report.requiresReview" :disabled="isReadOnly" type="success" @click="finalizeReport">确认复核并定稿</el-button>
        <el-dropdown trigger="click" @command="exportReport">
          <el-button :icon="Download" type="primary" :disabled="report.readOnly">{{ report.requiresReview ? '导出草稿' : '导出报告' }}<ArrowDown /></el-button>
          <template #dropdown><el-dropdown-menu>
            <el-dropdown-item command="markdown">Markdown 文档</el-dropdown-item>
            <el-dropdown-item command="docx">Word 文档</el-dropdown-item>
            <el-dropdown-item command="pdf">PDF 文档</el-dropdown-item>
          </el-dropdown-menu></template>
        </el-dropdown>
      </div>
    </header>
    <el-alert v-if="report.readOnly" title="正在只读查看其他用户的报告" description="可查看正文和引用；编辑及导出文件由报告所有者操作。" type="info" :closable="false" show-icon />
    <el-alert v-else-if="isReadOnly" title="当前报告已正式发布，处于只读状态" description="可阅读正文、查看引用和导出报告。如需修改，请先由管理员撤销发布。" type="info" :closable="false" show-icon />
    <el-alert v-if="report.requiresReview" title="当前报告为待复核草稿" :description="report.generationWarning || '该报告未完成全量模型生成，请配置可用模型或人工复核后再作为正式成果使用。'" type="warning" :closable="false" show-icon />
    <el-alert v-if="!isDigest" class="ps-citation-check-status" :title="citationCheckLabel" description="仅检查引用编号、来源与正文位置的对应关系；不代表事实核验通过。" :type="citationCheckState === 'passed' ? 'success' : citationCheckState === 'warning' || citationCheckState === 'stale' ? 'warning' : 'info'" :closable="false" />
    <el-alert v-if="!isDigest && ['warning', 'stale'].includes(outlineCheckState)" class="ps-outline-check-status" :title="outlineCheckLabel" :description="outlineCheckDescription" type="warning" :closable="false" show-icon />
    <div class="ps-editor-layout" :class="{ 'is-reading': !isEditing, 'has-outline': outlineVisible, 'has-inspector': inspectorVisible }">
      <aside v-if="outlineVisible" ref="outlinePanelRef" class="ps-outline-panel">
        <div class="ps-editor-panel-head"><span>报告目录</span><el-button :icon="Plus" circle class="ps-ui-action" v-if="isEditing" aria-label="新增章节" :disabled="isReadOnly" @click="addSection" /></div>
        <el-button :auto-insert-space="false" class="ps-ui-control" v-for="(section, index) in sections" :key="section.id" native-type="button" :class="['ps-outline-item', { 'is-active': currentSectionId === section.id }]" :aria-current="currentSectionId === section.id ? 'location' : undefined" @click="scrollToSection(section.id)"><span class="ps-outline-number">{{ index + 1 }}</span><span class="ps-outline-copy"><strong>{{ section.title }}</strong><small>{{ section.words }} 字 · {{ sectionCitationCount(section) }} 条引用</small></span><i class="ps-outline-status" :class="`is-${section.status}`"></i></el-button>
        <el-button :icon="Plus" v-if="isEditing" class="ps-ui-action ps-add-section" :disabled="isReadOnly" @click="addSection">新增章节</el-button>
      </aside>

      <main ref="documentScrollRef" class="ps-document-editor" @scroll.passive="syncVisibleSection">
        <div v-if="isEditing" class="ps-format-toolbar"><el-button class="ps-ui-action" v-for="tool in formatTools" :key="tool" :title="formatToolLabel(tool)" :aria-label="formatToolLabel(tool)" :disabled="isReadOnly" @click="applyFormat(tool)">{{ tool }}</el-button><span></span><el-button plain type="primary" :disabled="isReadOnly || rewriteBusy" @click="openRewrite()">局部改写</el-button><small>选中正文后改写，先预览再替换</small></div>
        <article class="ps-document-canvas" :class="{ 'is-read-only': isReadOnly, 'is-reference-digest': referenceDigest }">
          <div v-if="projectForm && !isEditing" class="ps-project-form-cover">
            <p>{{ projectForm.organization }}</p>
            <h1>{{ projectForm.title }}</h1>
            <dl>
              <div v-for="[label, value] in projectForm.fields" :key="label"><dt>{{ label }}</dt><dd>{{ value }}</dd></div>
            </dl>
          </div>
          <h1 v-else v-stable-caret :contenteditable="isEditing && !isReadOnly" aria-label="编辑报告标题" @input="updateTitle" @compositionend="updateTitle">{{ documentTitle }}</h1>
          <div class="ps-doc-meta"><span>{{ referenceDigest ? referencePeriod : `编制日期：${reportDateLabel}` }}</span></div>
          <section v-for="(section, index) in sections" :key="section.id" :ref="el => setSectionElement(section.id, el)" class="ps-editable-content ps-report-section" :aria-label="section.title" @focusin="activateSection(section.id)">
            <div v-if="projectForm && !isEditing && section.title === '参考资料'" class="ps-project-budget">
              <table>
                <caption>经费预算表（万元）</caption>
                <thead><tr><th v-for="header in projectForm.budgetHeaders" :key="header" scope="col">{{ header }}</th></tr></thead>
                <tbody><tr v-for="row in projectForm.budgetRows" :key="row[1]"><td v-for="(value, column) in row" :key="column">{{ value }}</td></tr></tbody>
              </table>
            </div>
            <div class="ps-section-heading"><h2 v-stable-caret :contenteditable="isEditing && !isReadOnly" aria-label="编辑章节标题" @input="updateSectionTitle($event, section)" @compositionend="updateSectionTitle($event, section)">{{ referenceDigest && !isEditing ? `${digestCategoryNumber(index + 1)}、${section.title}` : section.title }}</h2><div v-if="isEditing" class="ps-section-actions"><el-button v-if="isBodyParagraph('', section.title)" plain size="small" :disabled="isReadOnly || rewriteBusy" @click.stop="openRewrite(section)">改写本章</el-button><el-button :icon="ArrowUp" circle class="ps-ui-action" title="章节上移" aria-label="章节上移" :disabled="isReadOnly || index <= 0" @click.stop="moveSection(-1, section.id)" /><el-button :icon="ArrowDown" circle class="ps-ui-action" title="章节下移" aria-label="章节下移" :disabled="isReadOnly || index >= sections.length - 1" @click.stop="moveSection(1, section.id)" /><el-button :icon="Delete" circle class="ps-ui-action" title="删除章节" aria-label="删除章节" :disabled="isReadOnly || sections.length <= 1" @click.stop="removeSection(section.id)" /></div></div>
            <DigestSectionContent v-if="referenceDigest" :ref="el => setSectionBody(section.id, el?.$el)" v-model:content="section.content" :editable="isEditing && !isReadOnly" @update:content="section.words = section.content.length; wordCount = sections.reduce((sum, item) => sum + Number(item.words || 0), 0); markSaving()" />
            <div v-else-if="isEditing && !isReadOnly" key="editing" v-stable-caret v-editable-text="section.content" :ref="el => setSectionBody(section.id, el)" class="ps-report-section-body ps-report-section-editable" contenteditable="true" :aria-label="`${section.title}正文`" @mouseup="captureRewriteSelection(section)" @keyup="captureRewriteSelection(section)" @input="updateSectionContent($event, section)" @compositionend="updateSectionContent($event, section)" />
            <div v-else key="reading" :ref="el => setSectionBody(section.id, el)" class="ps-report-section-body" :aria-label="`${section.title}正文`">
              <p v-for="({ paragraph, parts }, paragraphIndex) in bodyParagraphs.get(section.id)" :key="paragraphIndex" :class="{ 'ps-report-body-paragraph': isBodyParagraph(paragraph, section.title) }">
                <template v-for="(part, partIndex) in parts" :key="partIndex">
                  <sup v-if="part.citation" class="ps-report-citation" :data-citation-position="`${paragraphIndex}-${partIndex}`" :contenteditable="false">
                    <el-button class="ps-citation-trigger" :auto-insert-space="false" :aria-label="`查看引用 ${part.text}`" @click.stop="showCitation(part.text)">{{ part.text }}</el-button>
                  </sup>
                  <template v-else>{{ part.text }}</template>
                </template>
              </p>
            </div>
          </section>
        </article>
      </main>

      <aside v-if="inspectorVisible" class="ps-editor-inspector">
        <div class="ps-inspector-tabs ps-report-inspector-tabs ps-segmented-row"><el-segmented v-model="activeRightTab" :options="rightTabs" aria-label="报告辅助信息"  block /></div>
        <div v-if="activeRightTab === '引用来源'" class="ps-inspector-content">
          <div class="ps-inspector-summary"><strong>{{ citations.length }} 条引用</strong><span>查看来源并核对正文</span></div>
          <div v-for="{ source, positions } in citationCards" :id="`report-reference-${source.id}`" :key="source.id" class="ps-citation-card" :class="{ 'is-highlighted': highlightedCitation === String(source.id) }">
            <span>[{{ source.id }}] {{ citationTypeLabel(source.type) }}</span>
            <strong>{{ source.title }}</strong>
            <small v-if="source.location">{{ source.location }}</small>
            <p v-if="source.quote">{{ source.quote }}</p>
            <div class="ps-reference-actions">
              <el-button plain size="small" type="primary" :aria-label="`打开引用：${source.title}`" @click="openCitation(source)">查看来源</el-button>
            </div>
            <details v-if="positions.length" :open="positions.length === 1" class="ps-citation-positions">
              <summary>定位正文（{{ positions.length }} 处）</summary>
              <ol>
                <li v-for="(position, index) in positions" :key="`${position.sectionId}:${position.key}`">
                  <el-button class="ps-citation-position-button" @click="locateCitation(source, position)">
                    <span class="ps-citation-position-label">第 {{ index + 1 }} 处 · {{ position.sectionTitle }}</span>
                    <span class="ps-citation-position-sentence">{{ position.sentence }}</span>
                  </el-button>
                </li>
              </ol>
            </details>
            <small v-else-if="!positions.length && !referenceDigest">正文未引用</small>
          </div>
          <p v-if="!citations.length" class="ps-inspector-empty">本报告暂无引用来源</p>
        </div>
        <ReportExportHistory v-else class="ps-inspector-content" subject="报告" :report-id="String(report.id)" :title="report.title" :read-only="Boolean(report.readOnly)" :refresh-key="exportRefreshKey" />
      </aside>
    </div>
    <el-dialog v-model="rewriteVisible" title="局部改写 · 预览后替换" width="min(1000px, 94vw)" :close-on-click-modal="!rewriteBusy" :close-on-press-escape="!rewriteBusy" :show-close="!rewriteBusy">
      <template v-if="rewriteDraft">
        <div class="ps-rewrite-controls"><strong>{{ rewriteDraft.sectionTitle }}</strong><el-radio-group v-model="rewriteMode" :disabled="rewriteBusy" @change="rewriteResult = ''"><el-radio-button value="polish">润色</el-radio-button><el-radio-button value="shorten">精简</el-radio-button><el-radio-button value="expand">扩写</el-radio-button></el-radio-group></div>
        <p class="ps-rewrite-note">仅处理所选内容，不会自动覆盖正文。请核对事实与引用，确认后再替换。</p>
        <div class="ps-rewrite-comparison"><section><h3>原文</h3><pre>{{ rewriteDraft.original }}</pre></section><section><h3>改写建议</h3><p v-if="rewriteBusy" role="status">正在生成建议，原文保持不变…</p><el-input v-else-if="rewriteResult" v-model="rewriteResult" type="textarea" :rows="14" aria-label="改写建议" /><p v-else>选择改写方式，点击“生成建议”。</p></section></div>
        <el-alert v-if="rewriteError" :title="rewriteError" type="error" :closable="false" show-icon />
      </template>
      <template #footer><el-button :disabled="rewriteBusy" @click="rewriteVisible = false">取消</el-button><el-button :loading="rewriteBusy" @click="generateRewrite">{{ rewriteResult ? '重新生成' : '生成建议' }}</el-button><el-button type="primary" :disabled="rewriteBusy || !rewriteResult" @click="acceptRewrite">确认替换</el-button></template>
    </el-dialog>
    <el-dialog v-if="isDigest" v-model="previewVisible" title="报告预览" width="880px"><div class="ps-preview-paper"><h1>{{ previewDocument.title }}</h1><template v-for="(section, index) in previewDocument.sections" :key="section.id || index"><h2>{{ index + 1 }}. {{ section.title }}</h2><p v-for="paragraph in String(section.content || '本章节暂无正文').split(/\n+/).filter(Boolean)" :key="paragraph" :class="{ 'ps-report-body-paragraph': isBodyParagraph(paragraph, section.title) }"><template v-for="(part, partIndex) in reportCitationParts(paragraph, section.title, previewDocument.citations?.length ?? citations.length)" :key="partIndex"><sup v-if="part.citation" class="ps-report-citation">{{ part.text }}</sup><template v-else>{{ part.text }}</template></template></p></template></div></el-dialog>
    </template>
  </div>
</template>

<script setup>
import { returnToPreviousPage } from '@/utils/portal/openContent'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getToken } from '@/utils/auth'
import { openPortalContent } from '@/utils/portal/openContent'
import { getCitationPath } from '@/utils/portal/citationRouting'
import { isDigestType } from '../utils/routing'
import DigestSectionContent from '../components/DigestSectionContent.vue'
import { buildReportMarkdown, cleanReportCitationNotes, reportCitationParts } from '@/utils/portal/reportDocument'
import { digestMasthead, digestPeriodLabel } from '@/utils/portal/digestDocument'
import { vEditableText, vStableCaret } from '@/utils/portal/stableCaret'
import { citationSentenceBounds, citationSentenceRange } from '@/utils/portal/citationHighlight'
import { makeRewriteDraft, applyRewriteDraft, rewriteRequest } from '@/utils/portal/reportRewrite'
import { proposePipelineReportRewrite } from '@/api/pipeline/intelligence'
import { ArrowDown, ArrowLeft, ArrowUp, CircleCheck, CollectionTag, Delete, Download, Grid, Link, MoreFilled, Picture, Plus, View, WarningFilled } from '@element-plus/icons-vue'
import usePortalStore from '@/store/modules/portal'
import ReportExportHistory from '../components/ReportExportHistory.vue'
import { createPipelineResearchReportExport, downloadPipelineResearchReportExport, exportPipelineResearchReport, finalizePipelineResearchReport, getPipelineResearchReport, listPipelineResearchReportExports, updatePipelineResearchReport } from '@/api/pipeline/intelligence'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const isDigest = computed(() => route.path.startsWith('/portal/digests/'))
const report = ref([...portalStore.researchReports, ...portalStore.digestReports].find(item => item.id === route.params.id) || { id: String(route.params.id), title: '报告标题待补充', type: isDigest.value ? 'daily' : 'research-demand', words: 0 })
const loading = ref(false)
const loaded = ref(false)
const loadError = ref('')
const saving = ref(false)
const versionSaving = ref(false)
const saveState = ref('saved')
const isEditing = ref(false)
const outlineVisible = ref(true)
const outlinePanelRef = ref(null)
const inspectorVisible = ref(false)
const highlightedCitation = ref('')
const rewriteVisible = ref(false)
const rewriteBusy = ref(false)
const rewriteDraft = ref(null)
const rewriteSelection = ref(null)
const rewriteMode = ref('polish')
const rewriteResult = ref('')
const rewriteError = ref('')
let rewriteSequence = 0
let editorDisposed = false
let reportLoadSequence = 0
const previewVisible = ref(false)
const editorContentRef = ref()
const documentScrollRef = ref()
const sectionElements = new Map()
const sectionBodies = new Map()
const currentSectionId = ref(1)
const activeRightTab = ref('引用来源')
const wordCount = ref(0)
const formatTools = ['H1', 'H2', 'B', 'I', '•', '1.']
const rightTabs = ['引用来源', '导出记录']
const sections = ref([{ id: 1, title: '新建章节', content: '', words: 0, citations: 0, status: 'draft' }])
const citations = ref([])
const exportRefreshKey = ref(0)
const currentSection = computed(() => sections.value.find(item => item.id === currentSectionId.value) || sections.value[0])
const currentSectionIndex = computed(() => sections.value.findIndex(item => item.id === currentSectionId.value))
const isReadOnly = computed(() => Boolean(report.value.readOnly) || report.value.status === 'published')
async function toggleEditing() {
  if (isReadOnly.value) return
  if (isEditing.value) {
    try { await ensureSaved() } catch { return ElMessage.warning('修改尚未保存，暂不能退出编辑') }
  }
  isEditing.value = !isEditing.value
}
function citationTypeLabel(type) { return ({ paper: '论文', article: '新闻资讯', file: '上传资料', material: '上传资料', document: '上传资料' })[type] || '资料' }
function showCitation(marker) {
  const identity = String(marker).replace(/[\[\]]/g, '')
  if (!citations.value.some(item => String(item.id) === identity)) return
  highlightedCitation.value = identity
  activeRightTab.value = '引用来源'
  inspectorVisible.value = true
  nextTick(() => document.getElementById(`report-reference-${identity}`)?.scrollIntoView({ block: 'nearest' }))
}
function clearLocatedCitation() {
  window.CSS?.highlights?.delete('report-located-citation')
  documentScrollRef.value?.querySelectorAll('.is-located-citation').forEach(node => node.classList.remove('is-located-citation'))
}
async function locateCitation(source, position) {
  await nextTick()
  clearLocatedCitation()
  const marker = sectionBodies.get(position.sectionId)?.querySelector(`[data-citation-position="${position.key}"]`)
  const paragraph = marker?.closest('p')
  if (!paragraph || marker.textContent.trim() !== `[${source.id}]`) {
    ElMessage.info('当前正文没有使用这条引用')
    return
  }
  const range = citationSentenceRange(paragraph, marker)
  if (range && window.CSS?.highlights && window.Highlight) {
    window.CSS.highlights.set('report-located-citation', new window.Highlight(range))
  } else paragraph.classList.add('is-located-citation')
  activateSection(position.sectionId)
  highlightedCitation.value = String(source.id)
  // Only move the reading pane, leaving the source card and keyboard focus in place.
  const scroller = documentScrollRef.value
  const rect = range?.getBoundingClientRect() || paragraph.getBoundingClientRect()
  scroller.scrollTop += rect.top - scroller.getBoundingClientRect().top - 100
}
function captureRewriteSelection(section) {
  rewriteSelection.value = null
  if (!isEditing.value || isReadOnly.value || !isBodyParagraph('', section.title)) return
  const selection = window.getSelection?.()
  const body = sectionBodies.get(section.id)
  if (!selection?.rangeCount || !body?.contains(selection.anchorNode) || !body.contains(selection.focusNode)) return
  try { rewriteSelection.value = makeRewriteDraft(section, selection.toString()) } catch { /* 仅在点击改写时提示。 */ }
}
function openRewrite(section) {
  if (!isEditing.value || isReadOnly.value || rewriteBusy.value) return
  try {
    const draft = section ? makeRewriteDraft(section, section.content) : rewriteSelection.value
    if (!draft) throw new Error('请先选中一段正文，或使用章节旁的“改写本章”')
    if (!isBodyParagraph('', draft.sectionTitle)) throw new Error('参考资料不参与改写')
    rewriteDraft.value = { ...draft, reportId: String(report.value.id) }
    rewriteError.value = ''; rewriteResult.value = ''; rewriteMode.value = 'polish'
    rewriteVisible.value = true
  } catch (error) { ElMessage.warning(error.message) }
}
async function generateRewrite() {
  if (!rewriteDraft.value || rewriteBusy.value || isReadOnly.value || !isEditing.value) return
  const draft = rewriteDraft.value
  const sequence = ++rewriteSequence
  rewriteBusy.value = true; rewriteError.value = ''; rewriteResult.value = ''
  try {
    await ensureSaved()
    if (String(report.value.id) !== draft.reportId || !sections.value.some(item => String(item.id) === draft.sectionId && item.content === draft.content)) throw new Error('原章节已修改，请重新选择后改写')
    const response = await proposePipelineReportRewrite(draft.reportId, rewriteRequest(draft, report.value, rewriteMode.value))
    if (editorDisposed || sequence !== rewriteSequence || String(route.params.id) !== draft.reportId) return
    if (response.data?.revision !== report.value.revision) throw new Error('报告已发生变化，请重新生成建议')
    rewriteResult.value = response.data.text || ''
    if (!rewriteResult.value) throw new Error('模型未返回可用的改写建议')
  } catch (error) {
    if (!editorDisposed && sequence === rewriteSequence) rewriteError.value = error?.msg || error?.message || '生成建议失败，请重试'
  } finally { if (sequence === rewriteSequence) rewriteBusy.value = false }
}
async function acceptRewrite() {
  if (!rewriteDraft.value || rewriteBusy.value || isReadOnly.value || !isEditing.value) return
  try {
    if (String(report.value.id) !== rewriteDraft.value.reportId) throw new Error('报告已切换，建议未应用')
    applyRewriteDraft(sections.value, rewriteDraft.value, rewriteResult.value)
    wordCount.value = sections.value.reduce((sum, item) => sum + Number(item.words || 0), 0)
    markSaving()
    rewriteVisible.value = false; rewriteSelection.value = null
    await ensureSaved()
    ElMessage.success('已替换所选正文并保存')
  } catch (error) { rewriteError.value = error.message; ElMessage.warning(error.message === 'report has unsaved changes' ? '正文已替换但保存失败，请重试保存' : error.message) }
}
const bodyParagraphs = computed(() => new Map(sections.value.map(section => [
  section.id,
  String(section.content || '').split(/\n+/).filter(Boolean).map(paragraph => ({
    paragraph,
    parts: reportCitationParts(paragraph, section.title, citations.value.length)
  }))
])))
const citationCards = computed(() => {
  const positionsBySource = new Map(citations.value.map(source => [`[${source.id}]`, []]))
  if (!referenceDigest.value) {
    for (const section of sections.value) {
      if (!isBodyParagraph('', section.title)) continue
      bodyParagraphs.value.get(section.id).forEach(({ parts }, paragraphIndex) => {
        const text = parts.map(part => part.text).join('')
        let offset = 0
        parts.forEach((part, partIndex) => {
          const partStart = offset
          offset += part.text.length
          const positions = part.citation && positionsBySource.get(part.text)
          if (!positions) return
          const { start, end } = citationSentenceBounds(text, partStart, offset)
          positions.push({
            sectionId: section.id,
            sectionTitle: section.title,
            key: `${paragraphIndex}-${partIndex}`,
            sentence: text.slice(start, end).trim()
          })
        })
      })
    }
  }
  return citations.value.map(source => ({ source, positions: positionsBySource.get(`[${source.id}]`) }))
})
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
function keepActiveOutlineVisible() {
  const panel = outlinePanelRef.value
  const item = panel?.querySelector('[aria-current="location"]')
  if (!item) return
  const bounds = panel.getBoundingClientRect()
  const head = panel.querySelector('.ps-editor-panel-head')
  const top = bounds.top + (head?.getBoundingClientRect().height || 0) + 8
  const bottom = bounds.bottom - 8
  const row = item.getBoundingClientRect()
  // Scroll only the directory; never move the document or steal keyboard focus.
  if (row.top < top) panel.scrollTop += row.top - top
  else if (row.bottom > bottom) panel.scrollTop += row.bottom - bottom
}
watch([currentSectionId, outlinePanelRef], keepActiveOutlineVisible, { flush: 'post' })
const reportTypeLabel = computed(() => {
  const type = report.value.reportType || report.value.type
  if (isDigestType(type)) return ({ daily: '日报', weekly: '周报', monthly: '月报' })[type] || '情报简报'
  return ({ research: '科研报告', 'research-demand': '科研需求报告', 'technology-route': '技术路线报告', 'project-demand': '科技项目需求表' })[type] || type || '科研报告'
})
function digestCategoryNumber(number) {
  const digits = '零一二三四五六七八九'
  return number < 10 ? digits[number] : `${number >= 20 ? digits[Math.floor(number / 10)] : ''}十${number % 10 ? digits[number % 10] : ''}`
}
const citationCheckState = computed(() => saveState.value !== 'saved' ? 'stale' : report.value.metadata?.modelSnapshot?.checks?.citation?.status || 'not_run')
const citationCheckLabel = computed(() => ({ passed: '引用完整性检查已通过', warning: '引用完整性检查存在提示，请核对来源', stale: '正文已修改，请重新核对引用；旧版检查已失效', not_run: '尚未执行引用完整性检查' })[citationCheckState.value] || '尚未执行引用完整性检查')
const outlineCheck = computed(() => report.value.metadata?.modelSnapshot?.checks?.outline)
const outlineIssues = computed(() => {
  const recorded = outlineCheck.value?.issues
  return Array.isArray(recorded) && recorded.length ? recorded : Array.isArray(report.value.qualityIssues) ? report.value.qualityIssues : []
})
const outlineCheckState = computed(() => {
  if (saveState.value !== 'saved') return 'stale'
  const check = outlineCheck.value
  if (check?.version != null && report.value.versionNo != null && Number(check.version) !== Number(report.value.versionNo)) return 'stale'
  if (outlineIssues.value.length || check?.status === 'warning') return 'warning'
  return check?.status === 'passed' ? 'passed' : 'not_run'
})
const outlineCheckLabel = computed(() => outlineCheckState.value === 'stale' ? '正文已修改，旧版篇幅检查已失效' : '生成篇幅与规划存在偏差，请核对')
const outlineCheckDescription = computed(() => {
  if (outlineCheckState.value === 'stale') return '修改后的篇幅尚未校验，上次生成的检查结果不能代表当前版本。'
  return outlineIssues.value.map(issue => issue?.message || (issue?.actualWords != null && issue?.targetWords != null
    ? `章节“${issue.section || '未命名'}”约 ${issue.actualWords} 字词，规划 ${issue.targetWords} 字。` : '存在篇幅偏差，请核对章节正文与规划字数。')).join('；')
    || '存在篇幅偏差，请核对章节正文与规划字数。引用检查通过不代表篇幅符合要求。'
})
const referenceDigest = computed(() => isDigest.value && report.value.metadata?.modelSnapshot?.document_format === 'digest-reference-v1')
const projectForm = computed(() => report.value.metadata?.projectDemandForm)
const referencePeriod = computed(() => digestPeriodLabel(report.value.metadata?.period))
const documentTitle = computed(() => referenceDigest.value && !isEditing.value
  ? digestMasthead(report.value.title, report.value.metadata?.period) : report.value.title)
const reportDateLabel = computed(() => {
  const value = report.value.createdAt || report.value.created_at || report.value.updatedAt || report.value.updated_at || ''
  return value ? String(value).slice(0, 10) : '编制日期待补充'
})
const previewDocument = computed(() => ({ title: report.value.title, sections: sections.value }))
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
function buildMarkdown() { return buildReportMarkdown({ title: report.value.title, sections: sections.value, citations: citations.value, documentFormat: referenceDigest.value ? 'digest-reference-v1' : '' }) }
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
  if (isReadOnly.value) return
  if (!dirty && !options.saveVersion) return true
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
function updateTitle(event) { if (isReadOnly.value || event.isComposing) return; report.value.title = event.currentTarget.innerText.trim() || report.value.title; markSaving() }
function updateSectionTitle(event, section = currentSection.value) {
  if (isReadOnly.value || event.isComposing) return
  const title = event.currentTarget.innerText.trim()
  if (!title) return
  section.title = title
  markSaving()
}
function updateSectionContent(event, section = currentSection.value) { if (isReadOnly.value || event.isComposing) return; section.content = event.currentTarget.innerText.trim(); section.words = section.content.length; wordCount.value = sections.value.reduce((sum, item) => sum + Number(item.words || 0), 0); markSaving() }
function formatToolLabel(tool) { return ({ H1: '一级标题', H2: '二级标题', B: '粗体', I: '斜体', '•': '无序列表', '1.': '有序列表' })[tool] || tool }
function formatText(value, tool) {
  const text = String(value || '').trim() || ({ H1: '一级标题', H2: '二级标题', B: '粗体文本', I: '斜体文本', '•': '列表项', '1.': '列表项' })[tool] || '请输入内容'
  if (tool === 'H1') return `**${text.replace(/^\*+|\*+$/g, '')}**`
  if (tool === 'H2') return `**${text.replace(/^\*+|\*+$/g, '')}**`
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
async function finalizeReport() {
  try {
    await ensureSaved()
    await ElMessageBox.confirm('定稿后将保存当前内容并结束待复核状态，后续修改会重新进入草稿状态。', '确认复核并定稿', { confirmButtonText: '确认定稿', cancelButtonText: '继续编辑', type: 'warning' })
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

function loadExports() { exportRefreshKey.value++ }

async function exportReport(format = 'markdown') { try { await ensureSaved(); const params = { allowDraft: report.value.requiresReview }; if (format === 'markdown') { const res = await exportPipelineResearchReport(report.value.id, params); const blob = new Blob([res.data.content], { type: 'text/markdown;charset=utf-8' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = res.data.fileName || `${report.value.title}.md`; link.click(); URL.revokeObjectURL(url); ElMessage.success(res.data.isDraft ? '草稿已导出' : 'Markdown 报告已导出') } else { await waitAndDownloadExport(format); ElMessage.success(`${format.toUpperCase()} 报告已导出`) } } catch (error) { ElMessage.error(error.message === 'report has unsaved changes' ? '当前修改未保存，请先重试保存' : error?.msg || '报告导出失败') } }
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
function openCurrentPreview() { previewVisible.value = true }
async function loadReport() {
  const sequence = ++reportLoadSequence
  const reportId = String(route.params.id)
  loading.value = true
  loadError.value = ''
  try {
    const res = await getPipelineResearchReport(reportId)
    if (editorDisposed || sequence !== reportLoadSequence || String(route.params.id) !== reportId) return
    if (!res.data) throw new Error('empty report response')
    report.value = { ...report.value, ...res.data }
    if (res.data.sections?.length) { sections.value = res.data.sections; currentSectionId.value = sections.value[0].id }
    citations.value = res.data.citations || []
    wordCount.value = Number(res.data.words || 0)
    if (editorDisposed || sequence !== reportLoadSequence) return
    loaded.value = true
    isEditing.value = route.query?.mode === 'edit' && !isReadOnly.value
    if (route.query?.panel === 'sources') { inspectorVisible.value = true; activeRightTab.value = '引用来源' }
  } catch (error) {
    if (editorDisposed || sequence !== reportLoadSequence) return
    loadError.value = error?.msg || '报告加载失败，请确认后端服务和访问权限。'
    ElMessage.error('报告加载失败，请确认后端服务和访问权限')
  } finally {
    if (sequence === reportLoadSequence) loading.value = false
  }
}
watch(() => route.params.id, () => {
  rewriteSequence += 1
  rewriteVisible.value = false; rewriteBusy.value = false; rewriteDraft.value = null
  rewriteSelection.value = null; rewriteResult.value = ''; rewriteError.value = ''
  isEditing.value = false; loaded.value = false; inspectorVisible.value = false
  void loadReport()
})
watch(() => route.query?.mode, mode => { if (loaded.value) isEditing.value = mode === 'edit' && !isReadOnly.value })
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
  clearLocatedCitation()
  editorDisposed = true
  rewriteSequence += 1
  reportLoadSequence += 1
  clearTimeout(saveTimer)
  window.removeEventListener('beforeunload', handleBeforeUnload)
})
</script>

<style scoped>
.is-reference-digest { font-family: '仿宋_GB2312', FangSong, 'Songti SC', serif; }
.is-reference-digest > h1 { color: #f00; text-align: center; font-size: clamp(21px, 2.2vw, 24px); font-weight: 700; }
.is-reference-digest .ps-doc-meta { display: block; text-align: center; color: #111; font-size: clamp(16px, 1.8vw, 21px); padding-bottom: 14px; margin-bottom: 18px; border-bottom: 3px solid #f00; }
.is-reference-digest .ps-section-heading h2 { font-family: inherit; font-size: 20px; font-weight: 700; }
.ps-project-form-cover { padding: 24px 0; margin-bottom: 28px; border-bottom: 1px solid var(--ps-line); }
.ps-project-form-cover > p, .ps-project-form-cover > h1 { text-align: center; }
.ps-project-form-cover > p { margin-bottom: 14px; font-size: 18px; }
.ps-project-form-cover > h1 { margin: 0; font-size: 26px; }
.ps-project-form-cover dl { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 230px), 1fr)); gap: 10px 24px; margin: 24px 0 0; }
.ps-project-form-cover dl div { display: grid; grid-template-columns: 7em minmax(0, 1fr); gap: 10px; }
.ps-project-form-cover dd { margin: 0; border-bottom: 1px solid var(--ps-line); overflow-wrap: anywhere; }
.ps-project-budget { margin: 24px 0; overflow-x: auto; }
.ps-project-budget table { width: 100%; min-width: 360px; border-collapse: collapse; font-size: 14px; }
.ps-project-budget caption { margin-bottom: 10px; text-align: left; font-size: 18px; font-weight: 600; }
.ps-project-budget th, .ps-project-budget td { padding: 5px 8px; border: 1px solid var(--ps-line); }
.ps-project-budget th { text-align: left; background: var(--ps-blue-soft); }

.ps-editor-page { container: report-workspace / inline-size; }
.ps-editor-page .ps-editor-layout {
  --outline-width: 220px;
  --inspector-width: 300px;
  grid-template-columns: var(--outline-column, 0px) minmax(0, 1fr) var(--inspector-column, 0px);
  grid-template-rows: minmax(0, 1fr);
}
.ps-editor-layout.has-outline { --outline-column: var(--outline-width); }
.ps-editor-layout.has-inspector { --inspector-column: var(--inspector-width); }
.ps-editor-layout > .ps-outline-panel { grid-column: 1; }
.ps-editor-layout > .ps-document-editor { grid-column: 2; }
.ps-editor-layout > .ps-editor-inspector { grid-column: 3; }
.ps-editor-page .ps-document-canvas { width: min(900px, calc(100% - 40px)); min-height: 100%; margin: 20px auto 36px; padding: 40px clamp(24px, 4vw, 64px); box-shadow: 0 2px 14px rgb(18 38 68 / 5%); }
.ps-editor-page .ps-editable-content { font-size: 16px; line-height: 1.9; }
.is-reading .ps-outline-item { min-height: 40px; grid-template-columns: 22px minmax(0, 1fr); gap: 8px; }
.is-reading .ps-outline-status, .is-reading .ps-outline-item small { display: none; }
.ps-editor-page .ps-outline-panel { padding-bottom: 8px; }
.ps-editor-page .ps-outline-panel > .ps-editor-panel-head { position: sticky; top: 0; z-index: 2; background: #fff; }
.ps-editor-page .ps-outline-panel .ps-outline-item { position: relative; width: calc(100% - 16px); margin: 4px 8px; transition: background-color 160ms ease, box-shadow 160ms ease, transform 160ms ease; }
.ps-editor-page .ps-outline-panel .ps-outline-item.is-active { background: var(--el-color-primary-light-9); color: var(--el-color-primary); box-shadow: 0 3px 10px rgb(64 158 255 / 16%); transform: translateY(-1px); }
.ps-editor-page .ps-outline-item.is-active::before { content: ''; position: absolute; inset: 9px auto 9px 0; width: 3px; border-radius: 3px; background: var(--el-color-primary); }
@media (prefers-reduced-motion: reduce) { .ps-editor-page .ps-outline-panel .ps-outline-item { transition: none; } .ps-editor-page .ps-outline-panel .ps-outline-item.is-active { transform: none; } }
.ps-editor-page .ps-document-editor { scrollbar-gutter: stable; }
.ps-format-toolbar :deep(.el-button), .ps-section-actions :deep(.el-button) { width: auto; }
.ps-format-toolbar small { color: var(--ps-muted); margin-left: 8px; }
.ps-reference-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.ps-citation-positions { margin-top: 8px; font-size: 13px; }
.ps-citation-positions summary { color: var(--ps-blue); cursor: pointer; padding-block: 4px; }
.ps-citation-positions ol { list-style: none; margin: 4px 0 0; padding: 0; }
.ps-citation-positions li + li { border-top: 1px solid var(--ps-line-soft); }
.ps-citation-position-button { width: 100%; height: auto; margin: 4px 0; padding: 8px; color: var(--ps-ink); font: inherit; line-height: 1.55; white-space: normal; text-align: left; overflow-wrap: anywhere; }
.ps-citation-position-button :deep(> span) { display: grid; gap: 3px; width: 100%; }
.ps-citation-position-label { color: var(--ps-muted); font-size: 12px; }
.ps-citation-positions button:hover, .ps-citation-positions button:focus-visible { background: var(--el-color-primary-light-8); }
.ps-citation-card.is-highlighted { border-color: var(--ps-blue); background: var(--ps-blue-soft); }
.ps-report-section-body .ps-report-citation { cursor: pointer; color: var(--ps-blue); }
.ps-report-section-editable { white-space: pre-wrap; }
.ps-report-section-body .ps-report-citation:focus-visible { outline: 2px solid var(--ps-blue); outline-offset: 3px; border-radius: 2px; }
.ps-rewrite-controls { display: flex; justify-content: space-between; flex-wrap: wrap; align-items: center; gap: 12px; }
.ps-rewrite-note { color: var(--ps-muted); line-height: 1.6; }
.ps-rewrite-comparison { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.ps-rewrite-comparison > section { min-width: 0; border: 1px solid var(--ps-line); border-radius: 8px; padding: 16px; }
.ps-rewrite-comparison h3 { margin: 0 0 12px; font-size: 15px; }
.ps-rewrite-comparison pre { white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; line-height: 1.8; max-height: 400px; overflow-y: auto; margin: 0; }
@media (max-width: 900px) {
  .ps-rewrite-comparison { grid-template-columns: minmax(0, 1fr); }
  .ps-format-toolbar { flex-wrap: wrap; }
}
.ps-report-section {
  scroll-margin-top: 64px;
}
.ps-report-section-body {
  min-height: 2em;
  outline: none;
}
:global(::highlight(report-located-citation)) { background-color: #fff0a6; color: #303133; }
.ps-report-section-body :deep(.is-located-citation) { background: #fff0a6; border-radius: 4px; }
.ps-report-inspector-tabs {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.ps-report-body-paragraph {
  text-indent: 2em;
}
.ps-report-citation {
  position: static;
  vertical-align: super;
  font-size: .75em;
  line-height: 0;
  padding: 2px 4px;
  border-radius: 3px;
  background: var(--ps-blue-soft, #eaf3fa);
  box-decoration-break: clone;
}
@container report-workspace (max-width: 1100px) {
  .ps-editor-page .ps-editor-layout { --outline-width: clamp(150px, 18cqw, 200px); --inspector-width: clamp(200px, 24cqw, 260px); }
  .ps-editor-page .ps-document-canvas { width: calc(100% - 24px); padding: 28px clamp(20px, 4vw, 48px); }
}
@media (max-width: 780px) {
  .ps-editor-page { display: flex; flex-direction: column; height: calc(100dvh - 70px); min-height: 0; }
  .ps-editor-page > .ps-editor-topbar, .ps-editor-page > .el-alert { flex-shrink: 0; }
  .ps-editor-page > .ps-editor-layout { flex: 1; min-height: 0; overflow: hidden; }
}
@container report-workspace (max-width: 780px) {
  .ps-editor-page .ps-editor-layout { grid-template-columns: minmax(0, 1fr); grid-template-rows: auto minmax(0, 1fr) auto; }
  .ps-editor-layout > .ps-outline-panel { grid-row: 1; border-right: 0; border-bottom: 1px solid var(--ps-line); }
  .ps-editor-layout > .ps-document-editor { grid-row: 2; }
  .ps-editor-layout > .ps-editor-inspector { grid-row: 3; border-left: 0; border-top: 1px solid var(--ps-line); }
  .ps-editor-layout > .ps-outline-panel,
  .ps-editor-layout > .ps-editor-inspector { grid-column: 1; max-height: min(24dvh, 180px); overflow-y: auto; }
  .ps-editor-layout > .ps-document-editor { grid-column: 1; min-height: 0; }
}
</style>
