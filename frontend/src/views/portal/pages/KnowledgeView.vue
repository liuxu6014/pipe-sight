<template>
  <div class="ps-page ps-knowledge-page ps-basket-page">
    <PortalPageHeader title="资料库">
      <template #actions>
        <el-button type="primary" :icon="UploadFilled" @click="openUpload">上传资料</el-button>
      </template>
    </PortalPageHeader>

    <div v-if="documentsError || parsingRefreshError" class="ps-inline-state is-warning" role="status">
      <WarningFilled />
      <span>{{ documentsError || parsingRefreshError }}</span>
      <el-button class="ps-ui-action" :disabled="portalStore.dataLoading" @click="refreshDocuments">重新获取</el-button>
    </div>

    <div class="ps-toolbar ps-knowledge-toolbar">
      <el-input v-model.trim="keyword" :prefix-icon="Search" clearable aria-label="搜索资料库" placeholder="搜索文件名称或摘要" />
      <el-select v-model="classification" clearable filterable placeholder="全部类别" aria-label="资料类别"><el-option v-for="name in libraryCategories" :key="name" :label="name" :value="name" /></el-select>
      <el-select v-model="parseStatus" aria-label="按解析状态筛选">
        <el-option label="全部状态" value="all" />
        <el-option label="已解析" value="已解析" />
        <el-option label="处理中" value="处理中" />
        <el-option label="异常" value="异常" />
      </el-select>
      <el-button v-if="hasFilters" @click="clearFilters">重置筛选</el-button>
    </div>
    <section ref="listRegion" class="ps-material-list" :aria-busy="isInitialLoading" aria-label="资料列表">
      <el-skeleton v-if="isInitialLoading" :rows="4" animated />
      <el-table v-else :data="pagedDocuments" row-key="id" :max-height="listHeight" class="ps-library-table" style="width: 100%">
        <el-table-column label="资料名称" min-width="360" header-align="center">
          <template #default="{ row: doc }">
            <div class="ps-library-identity">
              <span class="ps-doc-type" :class="`is-${String(doc.format || '').toLowerCase()}`">{{ doc.format }}</span>
              <div class="ps-doc-main">
                <el-link underline="hover" :href="$router.resolve(libraryItemPath(doc) || '/portal').href" class="ps-ui-title" @click.prevent="openDocument(doc)">{{ doc.name }}</el-link>
                <p v-if="doc.summary" :title="doc.summary">{{ doc.summary }}</p>
                <small v-if="doc.scanStatus && doc.scanStatus !== 'clean'" class="ps-doc-security-state">安全状态：{{ scanStatusLabel(doc.scanStatus) }}{{ doc.scanMessage ? ` · ${doc.scanMessage}` : '' }}</small>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类别" width="130" header-align="center" align="center">
          <template #default="{ row: doc }"><el-tag class="ps-library-category" effect="plain" :type="contentCategory(doc) ? 'primary' : 'info'">{{ contentCategory(doc) || '待分类' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="解析状态" width="130" header-align="center" align="center">
          <template #default="{ row: doc }"><b class="ps-parse-state" :class="statusClass(doc.status)"><i></i>{{ doc.status }}</b></template>
        </el-table-column>
        <el-table-column label="更新时间" width="180" header-align="center" align="center">
          <template #default="{ row: doc }"><time>{{ doc.updatedAt || doc.publishedDate || doc.time || '—' }}</time></template>
        </el-table-column>
        <el-table-column label="操作" width="320" header-align="center" align="right">
          <template #default="{ row: doc }"><div class="ps-row-actions">
          <el-button plain type="primary" @click="openDocument(doc)">查看</el-button>
          <el-button v-if="doc.canManage !== false" plain :loading="isReparsing(doc.id)" :disabled="Boolean(deletingId)" :aria-label="`${doc.status === '解析失败' ? '重试解析' : '重新解析'}：${doc.name}`" @click="reparse(doc)">{{ doc.status === '解析失败' ? '重试解析' : '重新解析' }}</el-button>
          <el-button v-if="doc.canManage === true" plain type="danger" :loading="deletingId === `${doc.kind}:${doc.id}`" :disabled="Boolean(deletingId)" @click="deleteLibraryItem(doc)">删除</el-button>

          </div></template>
        </el-table-column>
        <template #empty>
      <PortalEmptyState
        v-if="!isInitialLoading && !filteredDocuments.length && !documentsError"
        :title="hasFilters ? '没有匹配资料' : '还没有研究资料'"
        :description="hasFilters ? '请调整搜索词或筛选条件。' : '上传项目报告、标准或会议纪要，建立可检索的证据库。'"
        :action-label="hasFilters ? '清除筛选' : '上传第一份资料'"
        @action="hasFilters ? clearFilters() : openUpload()"
      />
      <PortalEmptyState v-else-if="!isInitialLoading && !filteredDocuments.length && documentsError" title="暂时无法确认资料列表" description="资料获取失败，请重新获取后再检查筛选结果。" action-label="重新获取" @action="refreshDocuments" />
        </template>
      </el-table>
    </section>
    <div v-if="filteredDocuments.length && !isInitialLoading" class="ps-pagination" aria-label="研究资料列表分页">
      <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[10, 20, 50]" :total="filteredDocuments.length" :pager-count="5" layout="total, sizes, ->, prev, pager, next, jumper" background />
    </div>

    <el-dialog v-model="uploadVisible" title="上传资料" width="min(620px, calc(100vw - 24px))" :close-on-click-modal="!uploading" :close-on-press-escape="!uploading" :show-close="!uploading" destroy-on-close @closed="resetUpload">
      <el-upload
        v-model:file-list="uploadFiles"
        drag
        action="#"
        :auto-upload="false"
        multiple
        accept=".pdf,.docx,.md,.txt"
        :limit="10"
        :on-change="handleFileChange"
        :on-exceed="handleUploadExceed"
        :disabled="uploading"
      >
        <UploadFilled />
        <div class="el-upload__text">拖拽文件到此处，或 <em>点击选择</em></div>
        <template #tip>
          <div class="el-upload__tip">支持可搜索 PDF、DOCX、MD、TXT；旧版 DOC 请先转换。单文件最大 16MB，单次最多 10 份。</div>
        </template>
      </el-upload>
      <div v-if="uploadFiles.length" class="ps-upload-summary" role="status">
        已选择 {{ uploadFiles.length }} 份资料<span v-if="uploading">，正在上传第 {{ completedUploads + 1 }} 份</span>
      </div>
      <p class="ps-upload-private-note">上传后保存到个人资料库，仅自己可见。</p>
      <el-alert title="分类方式：系统提示词" description="资料解析后将由统一提示词分类；当前自动分类接口待接入，暂显示为待分类，不会把文件类型或关键词当作类别。" type="info" show-icon :closable="false" />
      <template #footer>
        <el-button :disabled="uploading" @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" :disabled="!uploadFiles.length" @click="finishUpload">开始上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import SavedSearchBar from '../components/SavedSearchBar.vue'
import { applySavedSearchQuery } from '@/utils/portal/savedSearches'
import { computed, onBeforeUnmount, onMounted, ref, toRefs, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Close, Search, UploadFilled, WarningFilled } from '@element-plus/icons-vue'
import PortalPageHeader from '../components/PortalPageHeader.vue'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'
import {
  deletePipelineKnowledgeDocument,
  listPipelineKnowledgeDocuments,
  reparsePipelineKnowledgeDocument,
  uploadPipelineKnowledgeDocument
} from '@/api/pipeline/intelligence'
import { useListQuery, validPage } from '@/utils/portal/listQuery'
import { buildLibraryItems, libraryItemPath } from '@/utils/portal/libraryItems'
import { contentCategory } from '@/utils/portal/contentPresentation'

const MAX_FILE_SIZE = 16 * 1024 * 1024
const ALLOWED_EXTENSIONS = new Set(['pdf', 'docx', 'md', 'txt'])
const router = useRouter()
const route = useRoute()
const portalStore = usePortalStore()
const query = useListQuery({ q: '', status: 'all', classification: '', page: 1, size: 10 })
function applySavedSearch(filters) { if (!applySavedSearchQuery(query, filters, 'knowledge')) refreshDocuments() }
const { q: keyword, classification, page: currentPage, size: pageSize } = toRefs(query)
const parseStatus = computed({
  get: () => parseStatusGroup(query.status) || 'all',
  set: value => { query.status = value }
})
const listRegion = ref(null)
const listHeight = ref()
let listResizeObserver
watch(listRegion, element => {
  listResizeObserver?.disconnect()
  if (!element || typeof ResizeObserver === 'undefined') return
  listResizeObserver = new ResizeObserver(([entry]) => {
    listHeight.value = Math.max(1, Math.floor(entry.contentRect.height))
  })
  listResizeObserver.observe(element)
}, { flush: 'post' })
const deletingId = ref('')
const uploadVisible = ref(false)
const uploadFiles = ref([])
const uploading = ref(false)
const completedUploads = ref(0)
const reparsingIds = ref(new Set())

const documents = computed(() => portalStore.knowledgeDocuments || [])
const libraryItems = computed(() => buildLibraryItems([], documents.value))
const libraryCategories = computed(() => [...new Set(libraryItems.value.map(contentCategory).filter(Boolean))])
const parsingRefreshError = ref('')
const hasParsingDocuments = computed(() => documents.value.some(doc => ['queued', 'planned', 'parsing', '解析中', '待解析', '等待解析', '待安全扫描'].includes(doc.parseStatus || doc.status)))
let parsingTimer
let parsingStopped = false
let parsingRunning = false
let parsingGeneration = 0
function scheduleParsingRefresh() {
  if (!parsingStopped && !parsingTimer && hasParsingDocuments.value) parsingTimer = setTimeout(() => {
    parsingTimer = undefined
    void refreshParsingDocuments()
  }, 3000)
}
watch(hasParsingDocuments, pending => {
  if (pending) scheduleParsingRefresh()
  else { clearTimeout(parsingTimer); parsingTimer = undefined; parsingRefreshError.value = '' }
}, { immediate: true })
watch(() => portalStore.workspaceEpoch, () => {
  parsingGeneration++
  clearTimeout(parsingTimer); parsingTimer = undefined
  reparsingIds.value = new Set(); parsingRefreshError.value = ''; deletingId.value = ''
  uploading.value = false; uploadFiles.value = []; completedUploads.value = 0; uploadVisible.value = false
  scheduleParsingRefresh()
})
onBeforeUnmount(() => { listResizeObserver?.disconnect(); parsingStopped = true; parsingGeneration++; clearTimeout(parsingTimer) })
async function refreshParsingDocuments() {
  if (parsingStopped || parsingRunning) return
  if (uploading.value || reparsingIds.value.size || portalStore.dataLoading) { scheduleParsingRefresh(); return }
  parsingRunning = true
  const generation = ++parsingGeneration
  const epoch = portalStore.workspaceEpoch
  try {
    const response = await listPipelineKnowledgeDocuments()
    if (parsingStopped || generation !== parsingGeneration || epoch !== portalStore.workspaceEpoch) return
    if (!Array.isArray(response?.data?.rows)) throw new Error('资料状态响应无效')
    portalStore.liveDocuments = response.data.rows
    if (portalStore.sectionErrors) portalStore.sectionErrors = { ...portalStore.sectionErrors, documents: '' }
    parsingRefreshError.value = ''
  } catch {
    if (!parsingStopped && generation === parsingGeneration && epoch === portalStore.workspaceEpoch) parsingRefreshError.value = '状态更新暂时失败，正在自动重试'
  } finally { parsingRunning = false; scheduleParsingRefresh() }
}
const documentsError = computed(() => portalStore.sectionErrors?.documents || (!portalStore.sectionErrors ? portalStore.dataError : ''))
const isInitialLoading = computed(() => portalStore.dataLoading && !portalStore.dataLoaded)
const hasFilters = computed(() => Boolean(keyword.value || parseStatus.value !== 'all' || classification.value))
const filteredDocuments = computed(() => {
  const query = keyword.value.toLocaleLowerCase('zh-CN')
  return libraryItems.value.filter(item => {
    const searchText = [item.name, item.summary, item.owner, item.source, item.journal, ...(safeTags(item))].filter(Boolean).join(' ').toLocaleLowerCase('zh-CN')
    return (!classification.value || contentCategory(item) === classification.value)
      && (parseStatus.value === 'all' || parseStatusGroup(item.status) === parseStatus.value)
      && (!query || searchText.includes(query))
  })
})
const pagedDocuments = computed(() => filteredDocuments.value.slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value))
watch([() => filteredDocuments.value.length, pageSize, () => portalStore.dataLoaded], () => {
  if (!isInitialLoading.value && portalStore.dataLoaded) currentPage.value = validPage(filteredDocuments.value.length, pageSize.value, currentPage.value)
}, { immediate: true })

function safeTags(doc) { return Array.isArray(doc?.tags) ? doc.tags : [] }
function scanStatusLabel(status) {
  return { pending: '等待安全扫描', quarantined: '已隔离', failed: '扫描失败' }[status] || '未通过安全检查'
}
function parseStatusGroup(status) {
  if (['处理中', '解析中', '待解析', '等待解析', '待安全扫描'].includes(status)) return '处理中'
  if (['异常', '解析失败', '已隔离', '扫描失败'].includes(status)) return '异常'
  return status === '已解析' ? status : ''
}
function statusClass(status) {
  const group = parseStatusGroup(status)
  return { 'is-processing': group === '处理中', 'is-failed': group === '异常' }
}
function openDocument(doc) { const path = libraryItemPath(doc); if (path) router.push(path) }
function openUpload() { uploadVisible.value = true }
function clearFilters() { keyword.value = ''; parseStatus.value = 'all'; classification.value = ''; currentPage.value = 1 }
async function deleteLibraryItem(item) {
  if (deletingId.value || parsingStopped) return
  const epoch = portalStore.workspaceEpoch
  const key = `${item.kind}:${item.id}`
  deletingId.value = key
  try {
    await removeDocument(item)
  } catch (error) {
    if (!['cancel', 'close'].includes(error) && !parsingStopped && epoch === portalStore.workspaceEpoch) ElMessage.error('删除失败，请稍后重试')
  } finally { if (epoch === portalStore.workspaceEpoch) deletingId.value = '' }
}
function isReparsing(id) { return reparsingIds.value.has(id) }
function resetUpload() { if (!uploading.value) { uploadFiles.value = []; completedUploads.value = 0 } }
function extensionOf(fileName = '') { return fileName.includes('.') ? fileName.split('.').pop().toLowerCase() : '' }
function validateUploadFile(file) {
  if (!ALLOWED_EXTENSIONS.has(extensionOf(file.name))) return '仅支持可搜索 PDF、DOCX、MD、TXT；旧版 DOC 请先转换为 DOCX'
  if (Number(file.size || 0) > MAX_FILE_SIZE) return '单个文件不能超过 16MB'
  if (!file.size) return '文件内容为空，请重新选择'
  return ''
}
function handleFileChange(uploadFile, currentFiles) {
  const validationError = validateUploadFile(uploadFile.raw || uploadFile)
  if (validationError) {
    uploadFiles.value = currentFiles.filter(item => item.uid !== uploadFile.uid)
    ElMessage.warning(`${uploadFile.name}：${validationError}`)
    return
  }
  const duplicate = currentFiles.find(item => item.uid !== uploadFile.uid && item.name === uploadFile.name && item.size === uploadFile.size)
  if (duplicate) {
    uploadFiles.value = currentFiles.filter(item => item.uid !== uploadFile.uid)
    ElMessage.warning(`${uploadFile.name} 已在上传列表中`)
  }
}
function handleUploadExceed() { ElMessage.warning('单次最多上传 10 份资料') }
async function refreshDocuments() { await portalStore.hydrate(true) }
async function reparse(doc) {
  if (parsingStopped) return
  if (doc.canManage === false) return ElMessage.warning('仅资料所有者可以重新解析')
  if (isReparsing(doc.id)) return
  parsingGeneration++
  const epoch = portalStore.workspaceEpoch
  reparsingIds.value = new Set([...reparsingIds.value, doc.id])
  try {
    const response = await reparsePipelineKnowledgeDocument(doc.id)
    if (parsingStopped || epoch !== portalStore.workspaceEpoch) return
    if (!response?.data || String(response.data.id) !== String(doc.id)) throw new Error('重试状态获取失败，请稍后刷新')
    portalStore.liveDocuments = portalStore.liveDocuments.map(row => String(row.id) === String(doc.id) ? { ...row, ...response.data } : row)
    ElMessage.success('已提交重新解析')
  } catch (error) {
    if (!parsingStopped && epoch === portalStore.workspaceEpoch) ElMessage.error(error?.msg || error?.message || '重试失败，请稍后再试')
  } finally {
    if (!parsingStopped && epoch === portalStore.workspaceEpoch) {
      const next = new Set(reparsingIds.value)
      next.delete(doc.id)
      reparsingIds.value = next
    }
    scheduleParsingRefresh()
  }
}
async function removeDocument(doc) {
  if (doc.canManage === false) return ElMessage.warning('仅资料所有者可以删除')
  const epoch = portalStore.workspaceEpoch
  try {
    const ids = doc.duplicateIds?.length ? doc.duplicateIds : [doc.id]
    const copies = ids.length > 1 ? `包含 ${ids.length} 份内容相同的重复上传记录。` : ''
    await ElMessageBox.confirm(`是否确认删除上传资料“${doc.name}”？${copies}原始文件及资料库记录将被删除，后续无法用于检索和新报告生成。`, '删除资料', {
      confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning', customClass: 'ps-library-delete-confirm', closeOnClickModal: false, autofocus: false
    })
    if (parsingStopped || epoch !== portalStore.workspaceEpoch) return
    for (const id of ids) {
      if (parsingStopped || epoch !== portalStore.workspaceEpoch) return
      await deletePipelineKnowledgeDocument(id)
      if (parsingStopped || epoch !== portalStore.workspaceEpoch) return
      portalStore.liveDocuments = portalStore.liveDocuments.filter(item => String(item.id) !== String(id))
      portalStore.basket = portalStore.basket.filter(item => String(item.id) !== String(id))
    }
    await portalStore.hydrate(true)
    if (!parsingStopped && epoch === portalStore.workspaceEpoch) ElMessage.success('资料已删除')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    if (!parsingStopped && epoch === portalStore.workspaceEpoch) ElMessage.error('删除失败，请确认权限或稍后重试')
  }
}
async function finishUpload() {
  if (!uploadFiles.value.length || uploading.value) return
  const epoch = portalStore.workspaceEpoch
  const validFiles = uploadFiles.value.filter(item => !validateUploadFile(item.raw || item))
  if (validFiles.length !== uploadFiles.value.length) {
    ElMessage.warning('上传列表中存在不符合要求的文件，请移除后重试')
    return
  }
  uploading.value = true
  completedUploads.value = 0
  const failures = []
  let duplicateUploads = 0
  for (const item of validFiles) {
    if (parsingStopped || epoch !== portalStore.workspaceEpoch) return
    try {
      const data = new FormData()
      data.append('file', item.raw)
      data.append('permissionScope', 'private')
      const response = await uploadPipelineKnowledgeDocument(data)
      if (parsingStopped || epoch !== portalStore.workspaceEpoch) return
      if (response?.data?.duplicate) duplicateUploads += 1
      completedUploads.value += 1
    } catch (error) {
      failures.push(item.name)
    }
  }
  if (parsingStopped || epoch !== portalStore.workspaceEpoch) return
  try {
    if (completedUploads.value) await portalStore.hydrate(true)
    if (parsingStopped || epoch !== portalStore.workspaceEpoch) return
    if (!failures.length) {
      uploadFiles.value = []
      uploadVisible.value = false
      ElMessage.success(duplicateUploads ? `已完成，${duplicateUploads} 份内容相同的文件已复用已有资料，未重复保存` : '已保存到资料库')
    } else {
      uploadFiles.value = validFiles.filter(item => failures.includes(item.name))
      ElMessage.error(`${completedUploads.value} 份上传成功，${failures.length} 份失败，请重试失败文件`)
    }
  } finally {
    if (epoch === portalStore.workspaceEpoch) { uploading.value = false; completedUploads.value = 0 }
  }
}

onMounted(() => {
  portalStore.hydrate()
  if (route.query.upload === '1') openUpload()
})
</script>

<style scoped>
.ps-knowledge-toolbar { min-height: 0; padding: 10px 12px; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }
.ps-knowledge-toolbar > .el-input { flex: 1 1 280px; min-width: 180px; }
.ps-knowledge-toolbar > .el-select { flex: 0 0 170px; width: 170px; }
.ps-material-list { border: 0; border-radius: 0; padding: 0; background: transparent; }
.ps-library-table { border: 1px solid var(--ps-line); border-radius: 10px; }
.ps-library-table :deep(.el-table__cell) { padding-block: 14px; }
.ps-library-table :deep(th.el-table__cell) { padding-block: 10px; color: var(--ps-muted); font-size: 12px; font-weight: 500; }
.ps-library-table :deep(.cell) { padding-inline: 12px; }
.ps-library-table :deep(.el-table__inner-wrapper::before) { display: none; }
.ps-library-table time { color: var(--ps-muted); font-size: 13px; white-space: nowrap; font-variant-numeric: tabular-nums; }
.ps-library-identity { display: flex; align-items: flex-start; gap: 12px; min-width: 0; }
.ps-library-category { max-width: 100%; height: auto; white-space: normal; overflow-wrap: anywhere; }
.ps-library-category :deep(.el-tag__content) { white-space: normal; }
.ps-doc-main { flex: 1; min-width: 0; }
.ps-doc-main > .ps-ui-title { border: 0; padding: 0; background: none; font: inherit; font-size: 15px; font-weight: 600; line-height: 1.6; white-space: normal; text-align: left; color: var(--ps-ink); overflow-wrap: anywhere; cursor: pointer; }
.ps-doc-main > .ps-ui-title:hover { color: var(--ps-blue); }
.ps-doc-main p { margin: 6px 0; color: var(--ps-muted); font-size: 13px; line-height: 1.65; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.ps-doc-main small, .ps-upload-private-note { font-size: 12px; line-height: 1.6; color: var(--ps-muted); }
.ps-doc-main small { display: block; }
.ps-doc-type { flex: 0 0 42px; width: 42px; height: 46px; display: grid; place-items: center; font-size: 11px; border-radius: 6px; background: #edf4f8; color: var(--ps-blue); }
.ps-row-actions { display: flex; flex-wrap: nowrap; justify-content: flex-end; gap: 8px; align-items: center; }
.ps-row-actions > .el-button { margin: 0; }
.ps-row-actions button { cursor: pointer; }
.ps-knowledge-page.ps-basket-page { gap: 12px; }
.ps-knowledge-page > .ps-page-header { flex-shrink: 0; margin: 0; }
.ps-knowledge-toolbar { flex-shrink: 0; margin: 0; }
.ps-material-list { flex: 1 1 0; min-width: 0; min-height: 0; overflow: hidden; overscroll-behavior: contain; scrollbar-gutter: stable; }
.ps-knowledge-page > .ps-inline-state { flex-shrink: 0; }
.ps-knowledge-page > .ps-pagination { margin: 0; padding: 12px 16px; flex-shrink: 0; background: #fff; border: 1px solid var(--ps-line); border-radius: 10px; }
:global(.el-message-box.ps-library-delete-confirm) { width: 480px; max-width: calc(100vw - 32px); box-sizing: border-box; }
:global(.ps-library-delete-confirm .el-message-box__message) { overflow-wrap: anywhere; }
@media (max-width: 760px) {
  .ps-knowledge-page > .ps-page-header { gap: 8px; }
  .ps-knowledge-page > .ps-page-header :deep(> div:first-child) { flex: 0 0 auto; }
  .ps-knowledge-toolbar { flex-direction: row; }
  .ps-knowledge-toolbar > .el-input { flex-basis: 100%; }
  .ps-knowledge-toolbar > .el-select { flex: 1 1 140px; width: auto; }
  .ps-doc-type { width: 36px; height: 40px; }
  .ps-row-actions { gap: 8px; }
  .ps-row-actions :deep(.el-button + .el-button) { margin-left: 0; }
  .ps-knowledge-page > .ps-pagination { padding: 8px; }
}
</style>
