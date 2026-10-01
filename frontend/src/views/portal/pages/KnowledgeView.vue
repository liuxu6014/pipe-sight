<template>
  <div class="ps-page ps-knowledge-page">
    <PortalPageHeader title="知识库">
      <template #actions>
        <el-button type="primary" :icon="UploadFilled" @click="openUpload">上传资料</el-button>
      </template>
    </PortalPageHeader>

    <div v-if="portalStore.dataError" class="ps-inline-state is-warning" role="status">
      <WarningFilled />
      <span>{{ portalStore.dataError }}</span>
      <button type="button" :disabled="portalStore.dataLoading" @click="refreshDocuments">重新获取</button>
    </div>

    <div class="ps-toolbar ps-knowledge-toolbar">
      <div class="ps-search-inline">
        <Search />
        <input v-model.trim="keyword" aria-label="搜索知识库资料" placeholder="搜索文件名、摘要、标签或上传人" />
        <button v-if="keyword" type="button" aria-label="清空搜索" @click="keyword = ''"><Close /></button>
      </div>
      <el-select v-model="permission" aria-label="按权限筛选">
        <el-option label="全部权限" value="all" />
        <el-option label="全员可见" value="全员可见" />
        <el-option label="仅自己可见" value="仅自己可见" />
        <el-option label="全员可见" value="全员可见" />
        <el-option label="项目组可见" value="项目组可见" />
        <el-option label="受限" value="受限" />
      </el-select>
      <el-select v-model="parseStatus" aria-label="按解析状态筛选">
        <el-option label="全部状态" value="all" />
        <el-option label="已解析" value="已解析" />
        <el-option label="解析中" value="解析中" />
        <el-option label="待解析" value="待解析" />
        <el-option label="解析失败" value="解析失败" />
      </el-select>
    </div>

    <div class="ps-tabs-line ps-knowledge-tabs" role="tablist" aria-label="资料分类">
      <button
        v-for="tab in tabs"
        :key="tab"
        type="button"
        role="tab"
        :aria-selected="activeTab === tab"
        :class="{ 'is-active': activeTab === tab }"
        @click="activeTab = tab"
      >
        {{ tab }}<span>{{ categoryCount(tab) }}</span>
      </button>
    </div>

    <div class="ps-knowledge-status-strip" aria-live="polite">
      <span>当前显示 <b>{{ filteredDocuments.length }}</b> 份</span>
      <span><i class="is-ready"></i>已解析 {{ statusCount('已解析') }}</span>
      <span><i class="is-running"></i>处理中 {{ processingCount }}</span>
      <button v-if="hasFilters" type="button" @click="clearFilters">清除筛选</button>
    </div>

    <section class="ps-knowledge-table" :aria-busy="isInitialLoading">
      <div class="ps-table-head" aria-hidden="true">
        <span>资料名称</span><span>所有者</span><span>权限</span><span>解析状态</span><span>更新时间</span><span></span>
      </div>

      <template v-if="isInitialLoading">
        <div v-for="index in 4" :key="index" class="ps-knowledge-skeleton"><i></i><span></span><span></span><span></span></div>
      </template>

      <article v-for="doc in filteredDocuments" v-else :key="doc.id">
        <span class="ps-doc-type" :class="`is-${String(doc.format || '').toLowerCase()}`">{{ doc.format }}</span>
        <span class="ps-doc-main">
          <button type="button" @click="openDocument(doc)">{{ doc.name }}</button>
          <p>{{ doc.summary }}</p>
          <small>
            {{ doc.type }} · {{ doc.pages ? `${doc.pages} 页` : '页数待补充' }}
            <b v-for="tag in safeTags(doc)" :key="tag">{{ tag }}</b>
          </small>
        </span>
        <span data-label="所有者">{{ doc.owner }}</span>
        <span data-label="权限"><b class="ps-permission-pill">{{ doc.permission }}</b></span>
        <span data-label="解析状态">
          <b class="ps-parse-state" :class="statusClass(doc.status)"><i></i>{{ doc.status }}</b>
        </span>
        <span data-label="更新时间">{{ doc.updatedAt }}</span>
        <span class="ps-row-actions">
          <el-button text type="primary" @click="openDocument(doc)">查看</el-button>
          <el-dropdown trigger="click">
            <button type="button" :aria-label="`${doc.name}的更多操作`"><MoreFilled /></button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="add(doc)">加入资料篮</el-dropdown-item>
                <el-dropdown-item v-if="doc.canManage !== false" :disabled="isReparsing(doc.id)" @click="reparse(doc)">
                  {{ isReparsing(doc.id) ? '正在提交…' : '重新解析' }}
                </el-dropdown-item>
                <el-dropdown-item v-if="doc.canManage !== false" divided class="ps-danger-menu-item" @click="removeDocument(doc)">删除资料</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </span>
      </article>

      <PortalEmptyState
        v-if="!isInitialLoading && !filteredDocuments.length"
        :title="hasFilters ? '没有匹配资料' : '知识库还没有资料'"
        :description="hasFilters ? '请调整搜索词或筛选条件。' : '上传项目报告、标准或会议纪要，建立可检索的证据库。'"
        :action-label="hasFilters ? '清除筛选' : '上传第一份资料'"
        @action="hasFilters ? clearFilters() : openUpload()"
      />
    </section>

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
          <div class="el-upload__tip">支持可搜索 PDF、DOCX、MD、TXT；旧版 DOC 请先转换。单文件最大 100MB，单次最多 10 份。</div>
        </template>
      </el-upload>
      <div v-if="uploadFiles.length" class="ps-upload-summary" role="status">
        已选择 {{ uploadFiles.length }} 份资料<span v-if="uploading">，正在上传第 {{ completedUploads + 1 }} 份</span>
      </div>
      <div class="ps-form-grid">
        <label>资料分类<el-select v-model="uploadCategory"><el-option v-for="tab in tabs.slice(1)" :key="tab" :label="tab" :value="tab" /></el-select></label>
        <label>可见范围<el-select v-model="uploadPermission"><el-option label="仅自己可见" value="private" /><el-option label="全员可见" value="organization" /></el-select></label>
      </div>
      <template #footer>
        <el-button :disabled="uploading" @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" :disabled="!uploadFiles.length" @click="finishUpload">开始上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Close, MoreFilled, Search, UploadFilled, WarningFilled } from '@element-plus/icons-vue'
import PortalPageHeader from '../components/PortalPageHeader.vue'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'
import {
  deletePipelineKnowledgeDocument,
  reparsePipelineKnowledgeDocument,
  uploadPipelineKnowledgeDocument
} from '@/api/pipeline/intelligence'

const MAX_FILE_SIZE = 100 * 1024 * 1024
const ALLOWED_EXTENSIONS = new Set(['pdf', 'docx', 'md', 'txt'])
const router = useRouter()
const portalStore = usePortalStore()
const keyword = ref('')
const permission = ref('all')
const parseStatus = ref('all')
const activeTab = ref('全部')
const uploadVisible = ref(false)
const uploadFiles = ref([])
const uploading = ref(false)
const completedUploads = ref(0)
const uploadCategory = ref('内部文献')
const uploadPermission = ref('private')
const reparsingIds = ref(new Set())
const tabs = ['全部', '内部文献', '英文报告', '论文', '历史项目', '模板', '其他']

const documents = computed(() => portalStore.knowledgeDocuments || [])
const isInitialLoading = computed(() => portalStore.dataLoading && !portalStore.dataLoaded)
const hasFilters = computed(() => Boolean(keyword.value || permission.value !== 'all' || parseStatus.value !== 'all' || activeTab.value !== '全部'))
const processingCount = computed(() => documents.value.filter(item => ['解析中', '待解析'].includes(item.status)).length)
const filteredDocuments = computed(() => {
  const query = keyword.value.toLocaleLowerCase('zh-CN')
  return documents.value.filter(item => {
    const searchText = [item.name, item.summary, item.owner, ...(safeTags(item))].filter(Boolean).join(' ').toLocaleLowerCase('zh-CN')
    return (activeTab.value === '全部' || item.type === activeTab.value)
      && (permission.value === 'all' || item.permission === permission.value)
      && (parseStatus.value === 'all' || item.status === parseStatus.value)
      && (!query || searchText.includes(query))
  })
})

function safeTags(doc) { return Array.isArray(doc?.tags) ? doc.tags : [] }
function categoryCount(tab) { return tab === '全部' ? documents.value.length : documents.value.filter(item => item.type === tab).length }
function statusCount(status) { return documents.value.filter(item => item.status === status).length }
function statusClass(status) { return { 'is-processing': ['解析中', '待解析'].includes(status), 'is-failed': status === '解析失败' } }
function openDocument(doc) { router.push(`/portal/knowledge/${doc.id}`) }
function openUpload() { uploadVisible.value = true }
function add(doc) { ElMessage.success(portalStore.addToBasket({ ...doc, title: doc.name }) ? '已加入资料篮' : '资料已在资料篮中') }
function clearFilters() { keyword.value = ''; permission.value = 'all'; parseStatus.value = 'all'; activeTab.value = '全部' }
function isReparsing(id) { return reparsingIds.value.has(id) }
function resetUpload() { if (!uploading.value) { uploadFiles.value = []; completedUploads.value = 0 } }
function extensionOf(fileName = '') { return fileName.includes('.') ? fileName.split('.').pop().toLowerCase() : '' }
function validateUploadFile(file) {
  if (!ALLOWED_EXTENSIONS.has(extensionOf(file.name))) return '仅支持可搜索 PDF、DOCX、MD、TXT；旧版 DOC 请先转换为 DOCX'
  if (Number(file.size || 0) > MAX_FILE_SIZE) return '单个文件不能超过 100MB'
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
  if (doc.canManage === false) return ElMessage.warning('仅资料所有者可以重新解析')
  if (isReparsing(doc.id)) return
  reparsingIds.value = new Set([...reparsingIds.value, doc.id])
  try {
    await reparsePipelineKnowledgeDocument(doc.id)
    await portalStore.hydrate(true)
    ElMessage.success('已提交重新解析，状态会在处理完成后更新')
  } catch (error) {
    ElMessage.error('重新解析提交失败，当前服务可能尚未启用该能力')
  } finally {
    const next = new Set(reparsingIds.value)
    next.delete(doc.id)
    reparsingIds.value = next
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
      ElMessage.success('资料已上传，解析状态可在列表中查看')
    } else {
      uploadFiles.value = validFiles.filter(item => failures.includes(item.name))
      ElMessage.error(`${completedUploads.value} 份上传成功，${failures.length} 份失败，请重试失败文件`)
    }
  } finally {
    uploading.value = false
    completedUploads.value = 0
  }
}

onMounted(() => portalStore.hydrate())
</script>
