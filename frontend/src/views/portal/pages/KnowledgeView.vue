<template>
  <div class="ps-page ps-knowledge-page ps-basket-page">
    <PortalPageHeader title="资料库">
      <template #actions>
        <el-button type="primary" :icon="UploadFilled" @click="openUpload">上传资料</el-button>
        <el-button type="primary" :loading="preparingReport" :disabled="!selection.selectedItems.value.length || preparingReport" @click="createFromSelection">新建报告</el-button>
      </template>
    </PortalPageHeader>

    <div v-if="documentsError || parsingRefreshError" class="ps-inline-state is-warning" role="status">
      <WarningFilled />
      <span>{{ documentsError || parsingRefreshError }}</span>
      <el-button class="ps-ui-action" :disabled="portalStore.dataLoading" @click="refreshDocuments">重新获取</el-button>
    </div>

    <div class="ps-toolbar ps-knowledge-toolbar">
      <el-input v-model.trim="keyword" :prefix-icon="Search" clearable aria-label="搜索资料库" placeholder="搜索资料标题、来源或摘要" />
      <el-select v-model="libraryKind" aria-label="资料类型">
        <el-option label="全部类型" value="all" /><el-option label="新闻资讯" value="news" />
        <el-option label="论文" value="paper" /><el-option label="上传资料" value="document" />
      </el-select>
      <el-select v-model="parseStatus" aria-label="按解析状态筛选">
        <el-option label="全部状态" value="all" />
        <el-option label="已解析" value="已解析" />
        <el-option label="解析中" value="解析中" />
        <el-option label="待解析" value="待解析" />
        <el-option label="解析失败" value="解析失败" />
        <el-option label="待安全扫描" value="待安全扫描" />
        <el-option label="已隔离" value="已隔离" />
        <el-option label="扫描失败" value="扫描失败" />
      </el-select>
      <el-button @click="clearFilters">重置筛选</el-button>
    </div>
    <div class="ps-library-selection-tools">
      <el-checkbox :model-value="selection.allVisible.value" :indeterminate="selection.indeterminate.value" :disabled="!selectablePage.length || preparingReport" @change="togglePage">全选当前页</el-checkbox>
      <span role="status">已选 {{ selection.selectedItems.value.length }} / 50 条</span>
      <el-button v-if="selection.selectedItems.value.length" :disabled="preparingReport" @click="selection.selectedIds.value = []">清空选择</el-button>
    </div>
    <section class="ps-material-list" :aria-busy="isInitialLoading" aria-label="资料列表">

      <template v-if="isInitialLoading">
        <div v-for="index in 4" :key="index" class="ps-knowledge-skeleton"><i></i><span></span><span></span><span></span></div>
      </template>

      <article v-for="doc in pagedDocuments" v-else :key="`${doc.kind}:${doc.id}`">
        <el-tooltip :content="libraryItemReason(doc) || '勾选用于生成报告'" placement="top"><el-checkbox :model-value="selection.selectedIds.value.includes(doc.id)" :disabled="Boolean(libraryItemReason(doc)) || preparingReport" :aria-label="`选择资料：${doc.name}`" @change="toggleSelection(doc, $event)" /></el-tooltip>
        <span class="ps-doc-type" :class="`is-${String(doc.format || '').toLowerCase()}`">{{ doc.format }}</span>
        <span class="ps-doc-main">
          <button type="button" @click="openDocument(doc)">{{ doc.name }}</button>
          <p>{{ doc.summary }}</p>
          <small>{{ doc.kind === 'document' ? '上传资料' : doc.kind === 'paper' ? '论文' : '新闻资讯' }}<template v-if="doc.source || doc.journal"> · {{ doc.source || doc.journal }}</template><template v-if="doc.updatedAt || doc.publishedDate || doc.time"> · {{ doc.updatedAt || doc.publishedDate || doc.time }}</template></small>
          <small v-if="doc.scanStatus && doc.scanStatus !== 'clean'" class="ps-doc-security-state">
            安全状态：{{ scanStatusLabel(doc.scanStatus) }}{{ doc.scanMessage ? ` · ${doc.scanMessage}` : '' }}
          </small>
        </span>
        <span data-label="解析状态">
          <b class="ps-parse-state" :class="statusClass(doc.status)"><i></i>{{ doc.status }}</b>
          <el-button v-if="doc.status === '解析失败' && doc.canManage !== false" plain type="primary" :loading="isReparsing(doc.id)" :aria-label="`重试解析：${doc.name}`" @click="reparse(doc)">重试</el-button>
        </span>
        <span class="ps-row-actions">
          <el-button plain type="primary" @click="openDocument(doc)">查看</el-button>
          <el-button v-if="doc.kind === 'document' && doc.canManage === true" @click="editDocument(doc)">编辑</el-button>
          <el-button v-if="doc.kind !== 'document' || doc.canManage === true" plain type="danger" :loading="deletingId === `${doc.kind}:${doc.id}`" :disabled="Boolean(deletingId) || preparingReport" @click="deleteLibraryItem(doc)">删除</el-button>
          <el-dropdown v-if="doc.kind === 'document'" trigger="click" :disabled="preparingReport || Boolean(deletingId)">
            <el-button class="ps-ui-action" :aria-label="`${doc.name}的更多操作`"><MoreFilled /></el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="doc.canManage !== false && doc.status !== '解析失败'" :disabled="isReparsing(doc.id)" @click="reparse(doc)">
                  {{ isReparsing(doc.id) ? '正在提交…' : '重新解析' }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </span>
      </article>

      <PortalEmptyState
        v-if="!isInitialLoading && !filteredDocuments.length && !documentsError"
        :title="hasFilters ? '没有匹配资料' : '还没有研究资料'"
        :description="hasFilters ? '请调整搜索词或筛选条件。' : '上传项目报告、标准或会议纪要，建立可检索的证据库。'"
        :action-label="hasFilters ? '清除筛选' : '上传第一份资料'"
        @action="hasFilters ? clearFilters() : openUpload()"
      />
      <PortalEmptyState v-else-if="!isInitialLoading && !filteredDocuments.length && documentsError" title="暂时无法确认资料列表" description="资料获取失败，请重新获取后再检查筛选结果。" action-label="重新获取" @action="refreshDocuments" />
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
import { Close, MoreFilled, Search, UploadFilled, WarningFilled } from '@element-plus/icons-vue'
import PortalPageHeader from '../components/PortalPageHeader.vue'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'
import {
  deletePipelineKnowledgeDocument,
  listPipelineKnowledgeDocuments,
  reparsePipelineKnowledgeDocument,
  uploadPipelineKnowledgeDocument,
  savePipelineWorkspaceItem
} from '@/api/pipeline/intelligence'
import { materialBasketReason, useListQuery, useListWorkspace, validPage } from '@/utils/portal/listQuery'
import { useBasketSelection } from '@/utils/portal/basketSelection'
import { buildLibraryItems, libraryItemPath, libraryItemReason, prepareLibrarySelection } from '@/utils/portal/libraryItems'

const MAX_FILE_SIZE = 16 * 1024 * 1024
const ALLOWED_EXTENSIONS = new Set(['pdf', 'docx', 'md', 'txt'])
const router = useRouter()
const route = useRoute()
const portalStore = usePortalStore()
const query = useListQuery({ q: '', status: 'all', kind: 'all', page: 1, size: 10 })
function applySavedSearch(filters) { if (!applySavedSearchQuery(query, filters, 'knowledge')) refreshDocuments() }
const { q: keyword, status: parseStatus, page: currentPage, size: pageSize } = toRefs(query)
const libraryKind = toRefs(query).kind
const preparingReport = ref(false)
const deletingId = ref('')
const { inBasket, busy, persist } = useListWorkspace(portalStore, { save: savePipelineWorkspaceItem })
const uploadVisible = ref(false)
const uploadFiles = ref([])
const uploading = ref(false)
const completedUploads = ref(0)
const reparsingIds = ref(new Set())

const documents = computed(() => portalStore.knowledgeDocuments || [])
const libraryItems = computed(() => buildLibraryItems(portalStore.basket, documents.value, portalStore.paperItems, portalStore.newsItems))
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
  reparsingIds.value = new Set(); parsingRefreshError.value = ''; deletingId.value = ''; preparingReport.value = false
  uploading.value = false; uploadFiles.value = []; completedUploads.value = 0; uploadVisible.value = false
  scheduleParsingRefresh()
})
onBeforeUnmount(() => { parsingStopped = true; parsingGeneration++; clearTimeout(parsingTimer) })
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
const documentsError = computed(() => portalStore.sectionErrors?.documents || portalStore.sectionErrors?.workspace || (!portalStore.sectionErrors ? portalStore.dataError : ''))
const isInitialLoading = computed(() => portalStore.dataLoading && !portalStore.dataLoaded)
const hasFilters = computed(() => Boolean(keyword.value || parseStatus.value !== 'all' || libraryKind.value !== 'all'))
const filteredDocuments = computed(() => {
  const query = keyword.value.toLocaleLowerCase('zh-CN')
  return libraryItems.value.filter(item => {
    const searchText = [item.name, item.summary, item.owner, item.source, item.journal, ...(safeTags(item))].filter(Boolean).join(' ').toLocaleLowerCase('zh-CN')
    return (libraryKind.value === 'all' || item.kind === libraryKind.value)
      && (parseStatus.value === 'all' || (item.status === '等待解析' ? '待解析' : item.status) === parseStatus.value)
      && (!query || searchText.includes(query))
  })
})
const pagedDocuments = computed(() => filteredDocuments.value.slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value))
const selectablePage = computed(() => pagedDocuments.value.filter(item => !libraryItemReason(item)))
const selection = useBasketSelection(() => libraryItems.value, () => selectablePage.value, () => portalStore.workspaceEpoch)
function toggleSelection(item, checked) {
  if (preparingReport.value || libraryItemReason(item)) return
  if (checked && !selection.selectedIds.value.includes(item.id) && selection.selectedItems.value.length >= 50) return ElMessage.warning('每次最多选择 50 条资料，已选资料不会被截断')
  selection.toggle(item.id, checked)
}
function togglePage(checked) {
  if (preparingReport.value) return
  const added = selectablePage.value.filter(item => !selection.selectedIds.value.includes(item.id)).length
  if (checked && selection.selectedItems.value.length + added > 50) return ElMessage.warning('全选当前页后将超过 50 条，请逐条选择；已选资料不会被截断')
  selection.toggleVisible(checked)
}
async function createFromSelection() {
  if (preparingReport.value) return
  const epoch = portalStore.workspaceEpoch
  preparingReport.value = true
  try {
    const ids = await prepareLibrarySelection([...selection.selectedItems.value], persist, () => !parsingStopped && epoch === portalStore.workspaceEpoch)
    if (!parsingStopped && epoch === portalStore.workspaceEpoch) await router.push({ path: '/portal/research/create', query: { selected: ids } })
  } catch (error) {
    if (!parsingStopped && epoch === portalStore.workspaceEpoch) ElMessage.error(error?.msg || error?.message || '资料准备失败，请重试')
  } finally { if (epoch === portalStore.workspaceEpoch) preparingReport.value = false }
}
watch([() => filteredDocuments.value.length, pageSize, () => portalStore.dataLoaded], () => {
  if (!isInitialLoading.value && portalStore.dataLoaded) currentPage.value = validPage(filteredDocuments.value.length, pageSize.value, currentPage.value)
}, { immediate: true })

function safeTags(doc) { return Array.isArray(doc?.tags) ? doc.tags : [] }
function scanStatusLabel(status) {
  return { pending: '等待安全扫描', quarantined: '已隔离', failed: '扫描失败' }[status] || '未通过安全检查'
}
function statusClass(status) { return { 'is-processing': ['解析中', '待解析', '等待解析', '待安全扫描'].includes(status), 'is-failed': ['解析失败', '已隔离', '扫描失败'].includes(status) } }
function openDocument(doc) { const path = libraryItemPath(doc); if (path) router.push(path) }
function editDocument(doc) { router.push({ path: `/portal/knowledge/${doc.id}`, query: { mode: 'edit' } }) }
function openUpload() { uploadVisible.value = true }
async function add(doc) {
  const reason = materialBasketReason(doc)
  if (reason) return ElMessage.warning(reason)
  try { if (await persist(doc, 'material') === 'saved') ElMessage.success('已加入资料库') }
  catch (error) { ElMessage.error(error?.msg || '加入资料库失败，请重试') }
}
function clearFilters() { keyword.value = ''; parseStatus.value = 'all'; libraryKind.value = 'all'; currentPage.value = 1 }
async function deleteLibraryItem(item) {
  if (deletingId.value || preparingReport.value || parsingStopped) return
  const epoch = portalStore.workspaceEpoch
  const key = `${item.kind}:${item.id}`
  deletingId.value = key
  try {
    if (item.kind === 'document') {
      await removeDocument(item)
    } else {
      await ElMessageBox.confirm(`是否确认从资料库删除“${item.name}”？此操作不删除新闻或论文的原始数据。`, '确认删除', {
        confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning', customClass: 'ps-library-delete-confirm', closeOnClickModal: false, autofocus: false
      })
      if (parsingStopped || epoch !== portalStore.workspaceEpoch) return
      if (await portalStore.removeFromBasket(item.id)) ElMessage.success('已从资料库删除')
    }
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
.ps-material-list { border: 1px solid var(--ps-line); border-radius: 12px; padding: 0 16px; background: #fff; }
.ps-material-list > article { display: grid; grid-template-columns: 24px 42px minmax(0, 1fr) auto auto; align-items: center; gap: 12px; padding: 16px 0; border-bottom: 1px solid var(--ps-line); }
.ps-material-list > article:last-of-type { border-bottom: 0; }
.ps-doc-main { min-width: 0; }
.ps-doc-main > button { border: 0; padding: 0; background: none; font: inherit; font-weight: 600; text-align: left; color: var(--ps-ink); overflow-wrap: anywhere; cursor: pointer; }
.ps-doc-main > button:hover { color: var(--ps-blue); }
.ps-doc-main p { margin: 6px 0; color: var(--ps-muted); font-size: 13px; line-height: 1.65; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.ps-doc-main small, .ps-upload-private-note { font-size: 12px; line-height: 1.6; color: var(--ps-muted); }
.ps-doc-main small { display: block; }
.ps-doc-type { width: 42px; height: 46px; display: grid; place-items: center; font-size: 11px; border-radius: 6px; background: #edf4f8; color: var(--ps-blue); }
.ps-row-actions { display: flex; gap: 8px; align-items: center; }
.ps-row-actions button { cursor: pointer; }
.ps-knowledge-page.ps-basket-page { gap: 12px; }
.ps-knowledge-page > .ps-page-header { flex-shrink: 0; margin: 0; }
.ps-knowledge-toolbar { flex-shrink: 0; margin: 0; }
.ps-library-selection-tools { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 16px; flex-shrink: 0; color: var(--ps-muted); font-size: 13px; }
.ps-material-list { flex: 1 1 0; min-width: 0; min-height: 0; overflow: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
.ps-knowledge-page > .ps-inline-state { flex-shrink: 0; }
.ps-material-list > article > .el-checkbox { margin: 0; }
.ps-knowledge-page > .ps-pagination { margin: 0; padding: 12px 16px; flex-shrink: 0; background: #fff; border: 1px solid var(--ps-line); border-radius: 10px; }
:global(.el-message-box.ps-library-delete-confirm) { width: 480px; max-width: calc(100vw - 32px); box-sizing: border-box; }
:global(.ps-library-delete-confirm .el-message-box__message) { overflow-wrap: anywhere; }
@media (max-width: 760px) {
  .ps-knowledge-page > .ps-page-header { gap: 8px; }
  .ps-knowledge-page > .ps-page-header :deep(> div:first-child) { flex: 0 0 auto; }
  .ps-knowledge-toolbar { flex-direction: row; }
  .ps-knowledge-toolbar > .el-input { flex-basis: 100%; }
  .ps-knowledge-toolbar > .el-select { flex: 1 1 140px; width: auto; }
  .ps-material-list > article { grid-template-columns: 24px 36px minmax(0, 1fr); gap: 10px; }
  .ps-material-list > article > span[data-label], .ps-row-actions { grid-column: 3; flex-wrap: wrap; }
  .ps-row-actions { gap: 8px; }
  .ps-row-actions :deep(.el-button + .el-button) { margin-left: 0; }
  .ps-knowledge-page > .ps-pagination { padding: 8px; }
}
</style>
