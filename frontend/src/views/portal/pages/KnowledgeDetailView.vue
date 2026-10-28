<template>
  <div class="ps-page ps-knowledge-detail-page" :aria-busy="loading">
    <div v-if="loadError && document" class="ps-inline-state is-warning" role="status">
      <WarningFilled /><span>{{ loadError }}</span><el-button class="ps-ui-action" @click="loadDocument">重新获取</el-button>
    </div>

    <section v-if="loading && !document" class="ps-detail-loading">
      <i></i><div><span></span><span></span><span></span></div>
    </section>

    <PortalEmptyState
      v-else-if="!document"
      title="资料不存在或无权访问"
      :description="loadError || '该资料可能已被删除，或不在当前账号的授权范围内。'"
      action-label="返回"
      @action="returnFromKnowledgeDetail(router)"
    />

    <template v-else>
      <section class="ps-document-detail-head">
        <el-button :icon="ArrowLeft" aria-label="返回" @click="returnFromKnowledgeDetail(router)" />
        <div class="ps-document-heading-copy">
          <el-input v-if="editVisible" v-model="editDraft.name" aria-label="资料名称" maxlength="255" :disabled="editSaving" />
          <h1 v-else>{{ document.name }}</h1>
          <div class="ps-document-meta">
            <span>{{ document.format }}</span>
            <span class="ps-parse-state" :class="statusClass(document.status)">{{ document.status }}</span>
            <span v-if="document.updatedAt">更新于 {{ document.updatedAt }}</span>
          </div>
        </div>
        <div class="ps-page-actions">
          <template v-if="editVisible">
            <el-button :disabled="editSaving" @click="cancelEditing">取消</el-button>
            <el-button type="primary" :loading="editSaving" @click="saveEdits">保存修改</el-button>
          </template>
          <template v-else>
          <el-button v-if="canManage" :disabled="loading || !liveDocument" :icon="Edit" @click="openEditor">编辑资料</el-button>
          <el-button v-if="document.allowDownload !== false" :icon="Download" @click="downloadDocument">下载文件</el-button>
          <el-dropdown v-if="canManage" trigger="click">
            <el-button aria-label="更多资料操作"><MoreFilled /></el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="canManage" :disabled="reparsing" @click="reparse">{{ reparsing ? '正在提交…' : '重新解析' }}</el-dropdown-item>
                <el-dropdown-item v-if="canManage" divided class="ps-danger-menu-item" @click="removeDocument">删除资料</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          </template>
        </div>
      </section>

      <section v-if="editVisible" class="ps-material-inline-editor" aria-label="编辑资料正文" :aria-busy="editSaving">
        <p class="ps-material-edit-note">直接修改正文，保存后用于检索和新报告生成；原始文件保留不变。</p>
        <el-alert v-if="editError" :title="editError" type="error" show-icon :closable="false" />
        <el-input v-model="editDraft.text" aria-label="资料正文" type="textarea" :rows="22" resize="vertical" :disabled="editSaving" />
      </section>
      <section v-else-if="document.status !== '已解析'" class="ps-parse-overview" :class="statusClass(document.status)">
        <span class="ps-parse-overview-icon"><Loading v-if="!securityBlocked && document.status !== '解析失败'" /><WarningFilled v-else /></span>
        <div>
          <h2>{{ securityBlocked ? '资料尚未通过安全检查' : document.status === '解析失败' ? '资料解析未完成' : '资料正在进入可检索状态' }}</h2>
          <p>{{ parseStateDescription }}</p>
        </div>
        <el-button v-if="canManage" :loading="reparsing" @click="reparse">重新解析</el-button>
      </section>

      <div v-else class="ps-document-detail-layout" :class="{ 'is-info-open': showInfo }">
        <section class="ps-document-preview" aria-label="资料正文阅读区">
          <div class="ps-preview-toolbar">
            <div class="ps-reader-context">
              <strong>资料正文</strong>
              <span>{{ parsedCharacterCount.toLocaleString('zh-CN') }} 字</span>
              <el-select v-if="chapters.length > 1" v-model="activeChapter" aria-label="选择文档章节">
                <el-option v-for="(chapter, index) in chapters" :key="index" :label="chapter.title" :value="index" />
              </el-select>
            </div>
            <div class="ps-reader-actions">
            <el-button-group>
              <el-button :icon="ZoomOut" aria-label="缩小预览" :disabled="zoom <= 80" @click="zoom -= 10" />
              <el-button disabled>{{ zoom }}%</el-button>
              <el-button :icon="ZoomIn" aria-label="放大预览" :disabled="zoom >= 130" @click="zoom += 10" />
            </el-button-group>
              <el-button :aria-expanded="showInfo" aria-controls="material-info" @click="showInfo = !showInfo">{{ showInfo ? '收起信息' : '资料信息' }}</el-button>
            </div>
          </div>
          <article :style="{ '--ps-preview-zoom': zoom / 100 }">
            <h2 v-if="chapters.length > 1">{{ chapters[activeChapter]?.title }}</h2>
            <p v-for="(paragraph, index) in activeParagraphs" :key="index">{{ paragraph }}</p>
            <div v-if="!activeParagraphs.length" class="ps-preview-empty">
              <Document /><strong>该章节暂无可展示文本</strong><span>解析结果生成后会自动显示在这里。</span>
            </div>
          </article>
        </section>

        <aside v-if="showInfo" id="material-info" class="ps-document-inspector" aria-label="资料信息">
          <h3 class="ps-material-info-title">资料信息</h3>
          <div class="ps-inspector-content">
            <div class="ps-inspector-facts">
              <div><span>解析状态</span><strong>{{ document.status }}</strong></div>
              <div><span>文本长度</span><strong>{{ parsedCharacterCount.toLocaleString('zh-CN') }} 字</strong></div>
              <div><span>可见范围</span><strong>{{ document.permission }}</strong></div>
            </div>
          </div>
        </aside>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Document, Download, Edit, Loading, MoreFilled, WarningFilled, ZoomIn, ZoomOut } from '@element-plus/icons-vue'
import { useMaterialEditor } from '@/utils/portal/materialEditor'
import { returnFromKnowledgeDetail } from '@/utils/portal/openContent'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'
import {
  deletePipelineKnowledgeDocument,
  downloadPipelineKnowledgeDocument,
  getPipelineKnowledgeDocument,
  updatePipelineKnowledgeDocument,
  reparsePipelineKnowledgeDocument
} from '@/api/pipeline/intelligence'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const liveDocument = ref(null)
const loading = ref(false)
const loadError = ref('')
const activeChapter = ref(0)
const zoom = ref(100)
const showInfo = ref(false)
const reparsing = ref(false)
let parseRefreshTimer
let detailStopped = false
let detailRequest = 0

const storeDocument = computed(() => portalStore.knowledgeDocuments.find(item => String(item.id) === String(route.params.id)) || null)
const document = computed(() => liveDocument.value || storeDocument.value)
const parsedText = computed(() => String(document.value?.editedText ?? document.value?.edited_text ?? document.value?.extractedText ?? document.value?.extracted_text ?? document.value?.parsedText ?? document.value?.content ?? '').trim())
const canManage = computed(() => document.value?.canManage === true)
const { visible: editVisible, saving: editSaving, error: editError, draft: editDraft, dirty: editDirty, canLeave, open: startEditing, save: saveEdits } = useMaterialEditor({
  update: updatePipelineKnowledgeDocument,
  onSaved: saved => {
    if (String(route.params.id) === String(saved.id)) {
      liveDocument.value = normalizeDocument(saved)
      activeChapter.value = 0
    }
    ElMessage.success('资料已更新，后续生成将使用修订后的正文')
    portalStore.hydrate(true).catch(() => {})
  }
})
function openEditor() {
  if (loading.value || !liveDocument.value) return ElMessage.warning('请等待资料正文加载完成后再编辑')
  if (!startEditing(document.value)) ElMessage.warning('当前资料不可编辑，请重新加载详情并确认所有者权限')
}
async function protectEdits() {
  return canLeave(async () => {
    try {
      await ElMessageBox.confirm('修改尚未保存，确定放弃修改？', '未保存的修改', { confirmButtonText: '放弃修改', cancelButtonText: '继续编辑', type: 'warning' })
      return true
    } catch { return false }
  })
}
async function cancelEditing() { if (await protectEdits()) editVisible.value = false }
function protectReload(event) {
  if (editDirty.value || editSaving.value) { event.preventDefault(); event.returnValue = '' }
}
onBeforeRouteLeave(protectEdits)
onBeforeRouteUpdate(protectEdits)
onMounted(() => window.addEventListener('beforeunload', protectReload))
onBeforeUnmount(() => window.removeEventListener('beforeunload', protectReload))
onBeforeUnmount(() => { detailStopped = true; detailRequest++; clearTimeout(parseRefreshTimer) })
function scheduleDetailRefresh() {
  clearTimeout(parseRefreshTimer)
  if (!detailStopped && !editVisible.value && ['解析中', '待解析', '等待解析', '待安全扫描'].includes(document.value?.status)) {
    parseRefreshTimer = setTimeout(() => { void loadDocument() }, 3000)
  }
}
watch([() => document.value?.status, editVisible], scheduleDetailRefresh)
const parsedCharacterCount = computed(() => parsedText.value.length)
const chapters = computed(() => {
  const sections = document.value?.sections
  if (Array.isArray(sections) && sections.length) {
    return sections.map((item, index) => typeof item === 'string' ? { title: `第 ${index + 1} 节`, paragraphs: [item] } : {
      title: item.title || `第 ${index + 1} 节`,
      paragraphs: normalizeParagraphs(item.content || item.text || item.summary)
    })
  }
  return [{ title: parsedText.value ? '资料正文' : '资料摘要', paragraphs: normalizeParagraphs(parsedText.value || document.value?.summary) }]
})
const activeParagraphs = computed(() => chapters.value[activeChapter.value]?.paragraphs || [])
const parseStateDescription = computed(() => {
  const status = document.value?.status
  if (status === '待安全扫描') return document.value?.scanMessage || '当前未配置或尚未完成安全扫描，资料不会进入解析、下载或 AI 使用流程。'
  if (status === '已隔离') return document.value?.scanMessage || '安全扫描发现风险，资料已被隔离，不能解析、下载或用于 AI。'
  if (status === '扫描失败') return document.value?.scanMessage || '安全扫描未完成，请检查扫描服务后重新提交。'
  if (status === '解析失败') return document.value?.parseMessage || document.value?.parseError || '请检查文件是否损坏、加密或格式不受支持，然后重新提交解析。'
  return '解析完成后可用于科研报告、情报简报和资料引用。TXT、MD、DOCX 和可搜索 PDF 可直接提取文字；扫描版 PDF 需先完成 OCR，旧版 DOC 请转换为 DOCX。'
})

function normalizeParagraphs(value) {
  if (Array.isArray(value)) return value.map(String).filter(Boolean)
  return String(value || '').split(/\n{2,}|\r?\n/).map(item => item.trim()).filter(Boolean)
}
function normalizeDocument(item = {}) {
  const permissionScope = item.permissionScope || item.permission_scope || (
    ['公开', '全员可见', 'public'].includes(item.permission) ? 'public' : 'private'
  )
  return {
    ...item,
    id: item.id || item.materialId,
    name: item.name || item.title || '未命名资料',
    type: item.type || item.category || '内部文献',
    format: item.format || item.fileType || item.name?.split('.').pop()?.toUpperCase() || 'FILE',
    pages: Number(item.pages || 0),
    owner: item.owner || item.department || '',
    uploader: item.uploader || item.uploadedBy,
    permissionScope,
    permission: permissionScope === 'public' ? '全员可见' : '仅自己可见',
    allowDownload: item.allowDownload !== false && item.allow_download !== false,
    allowAiUse: item.allowAiUse !== false && item.allow_ai_use !== false,
    parseMessage: item.parseMessage || item.parse_message || '',
    scanStatus: item.scanStatus || item.scan_status || 'clean',
    scanMessage: item.scanMessage || item.scan_message || '',
    status: ({ pending: '待安全扫描', quarantined: '已隔离', failed: '扫描失败' })[item.scanStatus || item.scan_status] || ({ ready: '已解析', indexed: '已解析', parsing: '解析中', queued: '待解析', planned: '待解析', failed: '解析失败' })[item.status] || item.status || '待解析',
    updatedAt: item.updated_at || item.updatedAt || '最近更新',
    summary: item.summary || item.scenario || ''
  }
}
const securityBlocked = computed(() => ['待安全扫描', '已隔离', '扫描失败'].includes(document.value?.status))
function statusClass(status) { return { 'is-processing': ['解析中', '待解析', '待安全扫描'].includes(status), 'is-failed': ['解析失败', '已隔离', '扫描失败'].includes(status) } }
function downloadDocument() {
  if (!document.value?.allowDownload) return ElMessage.warning('当前资料禁止下载')
  downloadPipelineKnowledgeDocument(document.value.id, document.value.name).catch(() => {})
}
async function loadDocument() {
  clearTimeout(parseRefreshTimer)
  const request = ++detailRequest
  loading.value = true
  loadError.value = ''
  try {
    const res = await getPipelineKnowledgeDocument(route.params.id)
    if (detailStopped || request !== detailRequest) return
    const payload = res.data?.data || res.data
    if (payload?.id || payload?.materialId) liveDocument.value = normalizeDocument(payload)
    else if (!storeDocument.value) loadError.value = '接口未返回该资料的详情信息。'
  } catch (error) {
    if (detailStopped || request !== detailRequest) return
    liveDocument.value = null
    loadError.value = storeDocument.value
      ? '详情服务暂不可用，当前显示知识库列表中已同步的信息。'
      : '无法读取该资料，请检查网络、访问权限或资料是否已删除。'
  } finally {
    if (!detailStopped && request === detailRequest) { loading.value = false; scheduleDetailRefresh() }
  }
}
async function reparse() {
  if (!canManage.value) return ElMessage.warning('仅资料所有者可以重新解析')
  if (reparsing.value) return
  reparsing.value = true
  try {
    const res = await reparsePipelineKnowledgeDocument(document.value.id)
    const reparsed = normalizeDocument(res.data?.data || res.data || {})
    if (reparsed.id) liveDocument.value = reparsed
    if (reparsed.status === '已解析') ElMessage.success('重新解析完成，资料已可用于检索和报告生成')
    else if (reparsed.status === '解析失败') ElMessage.warning(reparsed.parseMessage || reparsed.summary || '重新解析未提取到有效正文')
    else ElMessage.success('已提交重新解析')
    await portalStore.hydrate(true)
    await loadDocument()
  } catch (error) {
    ElMessage.error('重新解析提交失败，当前服务可能尚未启用该能力')
  } finally {
    reparsing.value = false
  }
}
async function removeDocument() {
  if (!canManage.value) return ElMessage.warning('仅资料所有者可以删除')
  try {
    await ElMessageBox.confirm(`确认删除“${document.value.name}”？删除后将无法用于检索和报告生成。`, '删除资料', {
      confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning'
    })
    await deletePipelineKnowledgeDocument(document.value.id)
    ElMessage.success('资料已删除')
    await portalStore.hydrate(true)
    router.replace('/portal/basket')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error('删除失败，请确认权限或稍后重试')
  }
}

watch(() => route.params.id, () => {
  liveDocument.value = null
  activeChapter.value = 0
  showInfo.value = false
  editVisible.value = false
  loadDocument()
}, { immediate: true })
watch([() => route.query.mode, () => liveDocument.value?.id], () => {
  if (route.query.mode === 'edit' && liveDocument.value && canManage.value && !editVisible.value) openEditor()
})
</script>

<style scoped>
.ps-document-detail-head { grid-template-columns: 44px minmax(0, 1fr) auto; align-items: start; gap: 12px; padding: 16px; margin-bottom: 14px; }
.ps-material-edit-note { margin: 0 0 12px; color: var(--ps-muted); font-size: 13px; line-height: 1.6; }
.ps-material-inline-editor { padding: 16px; background: #fff; border: 1px solid var(--ps-line); border-radius: 12px; }
.ps-material-inline-editor :deep(.el-alert) { margin-bottom: 12px; }
.ps-material-inline-editor :deep(textarea) { font-size: 15px; line-height: 1.8; padding: 16px; }
.ps-document-heading-copy h1 { margin: 0; font-size: 20px; line-height: 1.5; overflow-wrap: anywhere; }
.ps-document-meta { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 6px; font-size: 13px; }
.ps-document-detail-head > .el-button { margin: 0; min-width: 44px; min-height: 44px; }
.ps-page-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.ps-page-actions :deep(.el-button) { margin-left: 0; }
.ps-document-detail-layout { height: max(360px, calc(100dvh - 220px)); min-height: 0; overflow: hidden; grid-template-columns: minmax(0, 1fr); background: #fff; }
.ps-document-detail-layout.is-info-open { grid-template-columns: minmax(0, 1fr) 280px; }
.ps-document-preview { min-width: 0; min-height: 0; overflow: auto; background: #fff; border-radius: 12px; }
.ps-preview-toolbar { position: sticky; top: 0; min-height: 52px; padding: 8px 16px; gap: 12px; flex-wrap: wrap; border-radius: 12px 12px 0 0; }
.ps-reader-context, .ps-reader-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.ps-reader-context { min-width: 0; }
.ps-reader-context > span { font-size: 13px; color: var(--ps-muted); }
.ps-reader-context :deep(.el-select) { width: 200px; }
.ps-reader-actions :deep(.el-button) { min-height: 36px; }
.ps-document-preview > article { box-sizing: border-box; width: 100%; max-width: 1040px; min-height: 0; margin: 0 auto; padding: 24px 32px 32px; box-shadow: none; font-family: inherit; overflow-wrap: anywhere; }
.ps-document-preview article h2 { margin: 0 0 16px; font-size: calc(21px * var(--ps-preview-zoom, 1)); }
.ps-document-preview article p { margin: 0 0 10px; font-size: calc(16px * var(--ps-preview-zoom, 1)); line-height: 1.75; white-space: pre-wrap; }
.ps-document-inspector { min-width: 0; min-height: 0; overflow: auto; border-radius: 0 12px 12px 0; }
.ps-material-info-title { margin: 0; padding: 16px; font-size: 14px; border-bottom: 1px solid var(--ps-line); }
@media (max-width: 760px) {
  .ps-document-detail-layout.is-info-open { grid-template-columns: minmax(0, 1fr); }
  .ps-document-inspector { grid-row: 1; max-height: 220px; border-left: 0; border-bottom: 1px solid var(--ps-line); }
  .ps-document-detail-layout.is-info-open { grid-template-rows: auto minmax(0, 1fr); }
  .ps-document-preview > article { padding: 18px; }
  .ps-document-detail-head { grid-template-columns: 44px minmax(0, 1fr); }
  .ps-document-detail-head .ps-page-actions { grid-column: 2; }
  .ps-document-heading-copy h1 { font-size: 18px; }
}
</style>
