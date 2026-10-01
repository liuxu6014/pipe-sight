<template>
  <div class="ps-page ps-knowledge-detail-page" :aria-busy="loading">
    <nav class="ps-breadcrumb" aria-label="当前位置">
      <button type="button" @click="router.push('/portal/knowledge')">知识库</button>
      <ArrowRight />
      <b>资料详情</b>
    </nav>

    <div v-if="loadError && document" class="ps-inline-state is-warning" role="status">
      <WarningFilled /><span>{{ loadError }}</span><button type="button" @click="loadDocument">重新获取</button>
    </div>

    <section v-if="loading && !document" class="ps-detail-loading">
      <i></i><div><span></span><span></span><span></span></div>
    </section>

    <PortalEmptyState
      v-else-if="!document"
      title="资料不存在或无权访问"
      :description="loadError || '该资料可能已被删除，或不在当前账号的授权范围内。'"
      action-label="返回知识库"
      @action="router.push('/portal/knowledge')"
    />

    <template v-else>
      <section class="ps-document-detail-head">
        <span class="ps-doc-type" :class="`is-${String(document.format || '').toLowerCase()}`">{{ document.format }}</span>
        <div class="ps-document-heading-copy">
          <div class="ps-document-flags">
            <span>{{ document.type }}</span><span>{{ document.permission }}</span>
            <span class="ps-parse-state" :class="statusClass(document.status)"><i></i>{{ document.status }}</span>
          </div>
          <h1>{{ document.name }}</h1>
          <p>{{ document.summary || '该资料暂未填写摘要。' }}</p>
          <div class="ps-document-meta">
            <span>上传人：{{ document.uploader || document.owner }}</span>
            <span>所有者：{{ document.owner }}</span>
            <span>{{ document.pages ? `${document.pages} 页` : '页数待补充' }}</span>
            <span>更新于 {{ document.updatedAt }}</span>
          </div>
        </div>
        <div class="ps-page-actions">
          <el-button type="primary" @click="add"><Collection />加入资料篮</el-button>
          <el-dropdown v-if="canManage || document.allowDownload !== false" trigger="click">
            <el-button aria-label="更多资料操作"><MoreFilled /></el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="canManage" :disabled="reparsing" @click="reparse">{{ reparsing ? '正在提交…' : '重新解析' }}</el-dropdown-item>
                <el-dropdown-item v-if="document.allowDownload !== false" @click="downloadDocument">下载文件</el-dropdown-item>
                <el-dropdown-item v-if="canManage" divided class="ps-danger-menu-item" @click="removeDocument">删除资料</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </section>

      <section v-if="document.status !== '已解析'" class="ps-parse-overview" :class="statusClass(document.status)">
        <span class="ps-parse-overview-icon"><Loading v-if="document.status !== '解析失败'" /><WarningFilled v-else /></span>
        <div>
          <h2>{{ document.status === '解析失败' ? '资料解析未完成' : '资料正在进入可检索状态' }}</h2>
          <p>{{ parseStateDescription }}</p>
        </div>
        <el-button v-if="canManage" :loading="reparsing" @click="reparse">重新解析</el-button>
      </section>

      <div v-else class="ps-document-detail-layout">
        <aside class="ps-document-nav">
          <h3>文档目录</h3>
          <button v-for="(chapter, index) in chapters" :key="chapter.title" type="button" :class="{ 'is-active': activeChapter === index }" @click="activeChapter = index">
            <span>{{ String(index + 1).padStart(2, '0') }}</span>{{ chapter.title }}
          </button>
          <hr />
          <h3>文件版本</h3>
          <button v-for="version in versions" :key="version.id || version.label" class="ps-version-button">
            <Clock /><span><strong>{{ version.label }}</strong><small>{{ version.updatedAt }} · {{ version.owner }}</small></span>
          </button>
        </aside>

        <main class="ps-document-preview">
          <div class="ps-preview-toolbar">
            <span>{{ document.pages ? `共 ${document.pages} 页` : '页数待补充' }} · {{ chapters[activeChapter]?.title }}</span>
            <el-button-group>
              <el-button :icon="ZoomOut" aria-label="缩小预览" :disabled="zoom <= 80" @click="zoom -= 10" />
              <el-button disabled>{{ zoom }}%</el-button>
              <el-button :icon="ZoomIn" aria-label="放大预览" :disabled="zoom >= 130" @click="zoom += 10" />
            </el-button-group>
          </div>
          <article :style="{ '--ps-preview-zoom': zoom / 100 }">
            <span class="ps-preview-page-number">{{ activeChapter + 1 }} / {{ chapters.length }}</span>
            <h1>{{ chapters[activeChapter]?.title }}</h1>
            <p v-for="(paragraph, index) in activeParagraphs" :key="index">{{ paragraph }}</p>
            <div v-if="!activeParagraphs.length" class="ps-preview-empty">
              <Document /><strong>该章节暂无可展示文本</strong><span>解析结果生成后会自动显示在这里。</span>
            </div>
          </article>
        </main>

        <aside class="ps-document-inspector">
          <div class="ps-inspector-tabs">
            <button v-for="tab in detailTabs" :key="tab" type="button" :class="{ 'is-active': detailTab === tab }" @click="detailTab = tab">{{ tab }}</button>
          </div>
          <div class="ps-inspector-content">
            <div v-if="detailTab === '解析信息'" class="ps-inspector-facts">
              <div><span>解析状态</span><strong>{{ document.status }}</strong></div>
              <div><span>文本长度</span><strong>{{ parsedCharacterCount.toLocaleString('zh-CN') }} 字</strong></div>
              <div><span>切块数量</span><strong>{{ chunks.length }}</strong></div>
              <div><span>可见范围</span><strong>{{ document.permission }}</strong></div>
            </div>
            <template v-else-if="detailTab === '切块结果'">
              <button v-for="(chunk, index) in chunks" :key="chunk.id || index" class="ps-chunk-card">
                <span>Chunk {{ index + 1 }}</span><p>{{ chunk.text || chunk.content || chunk.summary }}</p><small>{{ chunk.tokens ? `约 ${chunk.tokens} tokens` : '长度待统计' }}</small>
              </button>
              <div v-if="!chunks.length" class="ps-inspector-empty">暂无可展示的切块结果</div>
            </template>
            <template v-else>
              <div v-for="(reference, index) in references" :key="reference.id || index" class="ps-reference-record">
                <Operation /><span><strong>{{ reference.title || reference.name }}</strong><small>{{ reference.location || reference.summary || '引用位置待补充' }}</small></span>
              </div>
              <div v-if="!references.length" class="ps-inspector-empty">该资料尚未被报告或简报引用</div>
            </template>
          </div>
        </aside>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowRight, Clock, Collection, Document, Loading, MoreFilled, Operation, WarningFilled, ZoomIn, ZoomOut } from '@element-plus/icons-vue'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'
import {
  deletePipelineKnowledgeDocument,
  downloadPipelineKnowledgeDocument,
  getPipelineKnowledgeDocument,
  reparsePipelineKnowledgeDocument
} from '@/api/pipeline/intelligence'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const liveDocument = ref(null)
const loading = ref(false)
const loadError = ref('')
const activeChapter = ref(0)
const detailTab = ref('解析信息')
const zoom = ref(100)
const reparsing = ref(false)
const detailTabs = ['解析信息', '切块结果', '引用记录']

const storeDocument = computed(() => portalStore.knowledgeDocuments.find(item => String(item.id) === String(route.params.id)) || null)
const document = computed(() => liveDocument.value || storeDocument.value)
const parsedText = computed(() => String(document.value?.parsedText || document.value?.extractedText || document.value?.content || '').trim())
const chunks = computed(() => Array.isArray(document.value?.chunks) ? document.value.chunks : [])
const references = computed(() => Array.isArray(document.value?.references) ? document.value.references : [])
const canManage = computed(() => document.value?.canManage !== false)
const parsedCharacterCount = computed(() => parsedText.value.length)
const chapters = computed(() => {
  const sections = document.value?.sections
  if (Array.isArray(sections) && sections.length) {
    return sections.map((item, index) => typeof item === 'string' ? { title: `第 ${index + 1} 节`, paragraphs: [item] } : {
      title: item.title || `第 ${index + 1} 节`,
      paragraphs: normalizeParagraphs(item.content || item.text || item.summary)
    })
  }
  return [{ title: '资料摘要', paragraphs: normalizeParagraphs(parsedText.value || document.value?.summary) }]
})
const activeParagraphs = computed(() => chapters.value[activeChapter.value]?.paragraphs || [])
const versions = computed(() => {
  if (Array.isArray(document.value?.versions) && document.value.versions.length) return document.value.versions
  return [{ id: 'current', label: '当前版本', updatedAt: document.value?.updatedAt || '最近更新', owner: document.value?.owner || '平台知识库' }]
})
const parseStateDescription = computed(() => document.value?.status === '解析失败'
  ? (document.value?.parseError || '请检查文件是否损坏、加密或格式不受支持，然后重新提交解析。')
  : '解析完成后可用于科研报告、情报简报和资料引用。TXT、MD、DOCX 和可搜索 PDF 可直接提取文字；扫描版 PDF 需先完成 OCR，旧版 DOC 请转换为 DOCX。')

function normalizeParagraphs(value) {
  if (Array.isArray(value)) return value.map(String).filter(Boolean)
  return String(value || '').split(/\n{2,}|\r?\n/).map(item => item.trim()).filter(Boolean)
}
function normalizeDocument(item = {}) {
  return {
    ...item,
    id: item.id || item.materialId,
    name: item.name || item.title || '未命名资料',
    type: item.type || item.category || '内部文献',
    format: item.format || item.fileType || item.name?.split('.').pop()?.toUpperCase() || 'FILE',
    pages: Number(item.pages || 0),
    owner: item.owner || item.department || '平台知识库',
    uploader: item.uploader || item.uploadedBy,
    permission: item.permission || item.permissionLabel || '仅自己可见',
    allowDownload: item.allowDownload !== false,
    status: ({ indexed: '已解析', parsing: '解析中', queued: '待解析', planned: '待解析', failed: '解析失败' })[item.status] || item.status || '待解析',
    updatedAt: item.updated_at || item.updatedAt || '最近更新',
    summary: item.summary || item.scenario || ''
  }
}
function statusClass(status) { return { 'is-processing': ['解析中', '待解析'].includes(status), 'is-failed': status === '解析失败' } }
function add() { ElMessage.success(portalStore.addToBasket({ ...document.value, title: document.value.name }) ? '已加入资料篮' : '资料已在资料篮中') }
function downloadDocument() {
  if (!document.value?.allowDownload) return ElMessage.warning('当前资料禁止下载')
  downloadPipelineKnowledgeDocument(document.value.id, document.value.name).catch(() => {})
}
async function loadDocument() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await getPipelineKnowledgeDocument(route.params.id)
    const payload = res.data?.data || res.data
    if (payload?.id || payload?.materialId) liveDocument.value = normalizeDocument(payload)
    else if (!storeDocument.value) loadError.value = '接口未返回该资料的详情信息。'
  } catch (error) {
    liveDocument.value = null
    loadError.value = storeDocument.value
      ? '详情服务暂不可用，当前显示知识库列表中已同步的信息。'
      : '无法读取该资料，请检查网络、访问权限或资料是否已删除。'
  } finally {
    loading.value = false
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
    router.replace('/portal/knowledge')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error('删除失败，请确认权限或稍后重试')
  }
}

watch(() => route.params.id, () => {
  liveDocument.value = null
  activeChapter.value = 0
  detailTab.value = '解析信息'
  loadDocument()
}, { immediate: true })
</script>
