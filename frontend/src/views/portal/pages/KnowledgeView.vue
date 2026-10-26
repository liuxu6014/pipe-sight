<template>
  <div class="ps-page ps-knowledge-page">
    <PortalPageHeader title="研究资料">
      <template #actions>
        <el-button @click="router.push('/portal/research')">返回科研报告</el-button>
        <el-button type="primary" :icon="UploadFilled" @click="openUpload">上传资料</el-button>
      </template>
    </PortalPageHeader>

    <div v-if="documentsError || parsingRefreshError" class="ps-inline-state is-warning" role="status">
      <WarningFilled />
      <span>{{ documentsError || parsingRefreshError }}</span>
      <button type="button" :disabled="portalStore.dataLoading" @click="refreshDocuments">重新获取</button>
    </div>

    <div class="ps-toolbar ps-knowledge-toolbar">
      <div class="ps-search-inline">
        <Search />
        <input v-model.trim="keyword" aria-label="搜索研究资料文件" placeholder="搜索文件名、摘要、标签或上传人" />
        <button v-if="keyword" type="button" aria-label="清空搜索" @click="keyword = ''"><Close /></button>
      </div>
      <el-select v-model="permission" aria-label="按权限筛选">
        <el-option label="全部权限" value="all" />
        <el-option label="全员可见" value="public" />
        <el-option label="仅自己可见" value="private" />
      </el-select>
      <el-button @click="clearFilters">重置筛选</el-button>
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
    </div>

    <div class="ps-tabs-line ps-knowledge-tabs" role="group" aria-label="资料分类筛选">
      <button
        v-for="tab in tabs"
        :key="tab"
        type="button"
        :aria-pressed="activeTab === tab"
        :class="{ 'is-active': activeTab === tab }"
        @click="activeTab = tab"
      >
        {{ tab }}<span>{{ categoryCount(tab) }}</span>
      </button>
    </div>

    <div class="ps-knowledge-status-strip" aria-live="polite">
      <span>匹配 <b>{{ filteredDocuments.length }}</b> 份 · 当前页 {{ pagedDocuments.length }} 份</span>
      <span><i class="is-ready"></i>当前筛选已解析 {{ statusCount('已解析') }}</span>
      <span><i class="is-running"></i>当前筛选处理中 {{ processingCount }}</span>
      <button v-if="hasFilters" type="button" @click="clearFilters">清除筛选</button>
    </div>
    <div class="ps-list-summary" role="status">当前条件：{{ filterSummary }}</div>

    <section class="ps-knowledge-table" :aria-busy="isInitialLoading" role="region" aria-label="资料列表，小屏可横向滚动查看全部列" tabindex="0">
      <div class="ps-table-head" aria-hidden="true">
        <span>资料名称</span><span>所有者</span><span>权限</span><span>解析状态</span><span>更新时间</span><span></span>
      </div>

      <template v-if="isInitialLoading">
        <div v-for="index in 4" :key="index" class="ps-knowledge-skeleton"><i></i><span></span><span></span><span></span></div>
      </template>

      <article v-for="doc in pagedDocuments" v-else :key="doc.id">
        <span class="ps-doc-type" :class="`is-${String(doc.format || '').toLowerCase()}`">{{ doc.format }}</span>
        <span class="ps-doc-main">
          <button type="button" @click="openDocument(doc)">{{ doc.name }}</button>
          <p>{{ doc.summary }}</p>
          <small>
            {{ doc.type }} · {{ doc.pages ? `${doc.pages} 页` : '页数待补充' }}
            <b v-for="tag in safeTags(doc)" :key="tag">{{ tag }}</b>
          </small>
          <small v-if="doc.scanStatus && doc.scanStatus !== 'clean'" class="ps-doc-security-state">
            安全状态：{{ scanStatusLabel(doc.scanStatus) }}{{ doc.scanMessage ? ` · ${doc.scanMessage}` : '' }}
          </small>
        </span>
        <span data-label="所有者">{{ doc.owner }}</span>
        <span data-label="权限"><b class="ps-permission-pill">{{ doc.permission }}</b></span>
        <span data-label="解析状态">
          <b class="ps-parse-state" :class="statusClass(doc.status)"><i></i>{{ doc.status }}</b>
          <el-button v-if="doc.status === '解析失败' && doc.canManage !== false" text type="primary" :loading="isReparsing(doc.id)" :aria-label="`重试解析：${doc.name}`" @click="reparse(doc)">重试</el-button>
        </span>
        <span data-label="更新时间">{{ doc.updatedAt }}</span>
        <span class="ps-row-actions">
          <el-button text type="primary" @click="openDocument(doc)">查看</el-button>
          <el-dropdown trigger="click">
            <button type="button" :aria-label="`${doc.name}的更多操作`"><MoreFilled /></button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item :disabled="busy(doc) || inBasket(doc) || Boolean(materialBasketReason(doc))" @click="add(doc)">{{ materialBasketReason(doc) || (inBasket(doc) ? '已加入资料篮' : busy(doc) ? '正在保存…' : '加入资料篮') }}</el-dropdown-item>
                <el-dropdown-item v-if="doc.canManage !== false && doc.status !== '解析失败'" :disabled="isReparsing(doc.id)" @click="reparse(doc)">
                  {{ isReparsing(doc.id) ? '正在提交…' : '重新解析' }}
                </el-dropdown-item>
                <el-dropdown-item v-if="doc.canManage !== false" divided class="ps-danger-menu-item" @click="removeDocument(doc)">删除资料</el-dropdown-item>
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

    <el-dialog v-model="uploadVisible" title="上传研究资料" width="min(620px, calc(100vw - 24px))" destroy-on-close @closed="resetUpload">
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
      <div class="ps-form-grid">
        <label>资料分类<el-select v-model="uploadCategory"><el-option v-for="tab in tabs.slice(1)" :key="tab" :label="tab" :value="tab" /></el-select></label>
        <label>可见范围<el-select v-model="uploadPermission"><el-option label="仅自己可见" value="private" /><el-option label="全员可见" value="public" /></el-select></label>
      </div>
      <template #footer>
        <el-button :disabled="uploading" @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" :disabled="!uploadFiles.length" @click="finishUpload">开始上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
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

const MAX_FILE_SIZE = 16 * 1024 * 1024
const ALLOWED_EXTENSIONS = new Set(['pdf', 'docx', 'md', 'txt'])
const router = useRouter()
const route = useRoute()
const portalStore = usePortalStore()
const query = useListQuery({ q: '', permission: 'all', status: 'all', category: '全部', page: 1, size: 10 })
const { q: keyword, permission, status: parseStatus, category: activeTab, page: currentPage, size: pageSize } = toRefs(query)
const { inBasket, busy, persist } = useListWorkspace(portalStore, { save: savePipelineWorkspaceItem })
const uploadVisible = ref(false)
const uploadFiles = ref([])
const uploading = ref(false)
const completedUploads = ref(0)
const uploadCategory = ref('内部文献')
const uploadPermission = ref('private')
const reparsingIds = ref(new Set())
const tabs = ['全部', '内部文献', '英文报告', '论文', '历史项目', '模板', '其他']

const documents = computed(() => portalStore.knowledgeDocuments || [])
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
  reparsingIds.value = new Set(); parsingRefreshError.value = ''
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
const documentsError = computed(() => portalStore.sectionErrors?.documents || (!portalStore.sectionErrors ? portalStore.dataError : ''))
const isInitialLoading = computed(() => portalStore.dataLoading && !portalStore.dataLoaded)
const hasFilters = computed(() => Boolean(keyword.value || permission.value !== 'all' || parseStatus.value !== 'all' || activeTab.value !== '全部'))
const processingCount = computed(() => filteredDocuments.value.filter(item => ['解析中', '待解析', '等待解析', '待安全扫描'].includes(item.status)).length)
const filteredDocuments = computed(() => {
  const query = keyword.value.toLocaleLowerCase('zh-CN')
  return documents.value.filter(item => {
    const searchText = [item.name, item.summary, item.owner, ...(safeTags(item))].filter(Boolean).join(' ').toLocaleLowerCase('zh-CN')
    return (activeTab.value === '全部' || item.type === activeTab.value)
      && (permission.value === 'all' || item.permissionScope === permission.value)
      && (parseStatus.value === 'all' || item.status === parseStatus.value)
      && (!query || searchText.includes(query))
  })
})
const pagedDocuments = computed(() => filteredDocuments.value.slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value))
watch([() => filteredDocuments.value.length, pageSize, () => portalStore.dataLoaded], () => {
  if (!isInitialLoading.value && portalStore.dataLoaded) currentPage.value = validPage(filteredDocuments.value.length, pageSize.value, currentPage.value)
}, { immediate: true })
const filterSummary = computed(() => [keyword.value && `关键词“${keyword.value}”`, activeTab.value !== '全部' && activeTab.value, permission.value !== 'all' && (permission.value === 'public' ? '全员可见' : '仅自己可见'), parseStatus.value !== 'all' && parseStatus.value].filter(Boolean).join(' / ') || '全部资料')

function safeTags(doc) { return Array.isArray(doc?.tags) ? doc.tags : [] }
function scanStatusLabel(status) {
  return { pending: '等待安全扫描', quarantined: '已隔离', failed: '扫描失败' }[status] || '未通过安全检查'
}
function categoryCount(tab) { return tab === '全部' ? documents.value.length : documents.value.filter(item => item.type === tab).length }
function statusCount(status) { return filteredDocuments.value.filter(item => item.status === status).length }
function statusClass(status) { return { 'is-processing': ['解析中', '待解析', '等待解析', '待安全扫描'].includes(status), 'is-failed': ['解析失败', '已隔离', '扫描失败'].includes(status) } }
function openDocument(doc) { router.push(`/portal/knowledge/${doc.id}`) }
function openUpload() { uploadVisible.value = true }
async function add(doc) {
  const reason = materialBasketReason(doc)
  if (reason) return ElMessage.warning(reason)
  try { if (await persist(doc, 'material') === 'saved') ElMessage.success('已加入资料篮') }
  catch (error) { ElMessage.error(error?.msg || '加入资料篮失败，请重试') }
}
function clearFilters() { keyword.value = ''; permission.value = 'all'; parseStatus.value = 'all'; activeTab.value = '全部'; currentPage.value = 1 }
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
  try {
    await ElMessageBox.confirm(`删除“${doc.name}”后将无法用于检索和报告生成。`, '删除资料', {
      confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning'
    })
    await deletePipelineKnowledgeDocument(doc.id)
    await portalStore.hydrate(true)
    ElMessage.success('资料已删除')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error('删除失败，请确认权限或稍后重试')
  }
}
async function finishUpload() {
  if (!uploadFiles.value.length || uploading.value) return
  const validFiles = uploadFiles.value.filter(item => !validateUploadFile(item.raw || item))
  if (validFiles.length !== uploadFiles.value.length) {
    ElMessage.warning('上传列表中存在不符合要求的文件，请移除后重试')
    return
  }
  uploading.value = true
  completedUploads.value = 0
  const failures = []
  for (const item of validFiles) {
    try {
      const data = new FormData()
      data.append('file', item.raw)
      data.append('category', uploadCategory.value)
      data.append('permissionScope', uploadPermission.value)
      await uploadPipelineKnowledgeDocument(data)
      completedUploads.value += 1
    } catch (error) {
      failures.push(item.name)
    }
  }
  try {
    if (completedUploads.value) await portalStore.hydrate(true)
    if (!failures.length) {
      uploadFiles.value = []
      uploadVisible.value = false
      ElMessage.success('已保存到资料库')
    } else {
      uploadFiles.value = validFiles.filter(item => failures.includes(item.name))
      ElMessage.error(`${completedUploads.value} 份上传成功，${failures.length} 份失败，请重试失败文件`)
    }
  } finally {
    uploading.value = false
    completedUploads.value = 0
  }
}

onMounted(() => {
  portalStore.hydrate()
  if (route.query.upload === '1') openUpload()
})
</script>
