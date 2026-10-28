<template>
  <div class="pipeline-page pipeline-knowledge-page ws-list-page">
    <section class="page-heading">
      <div>

        <h1>资料库管理</h1>

      </div>
      <div class="heading-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadDocuments">刷新</el-button>
        <el-button type="primary" :icon="UploadFilled" @click="openUpload">上传资料</el-button>
      </div>
    </section>

    <el-alert
      v-if="loadError"
      :title="loadError"
      type="error"
      show-icon
      :closable="false"
      class="knowledge-alert"
    >
      <template #default>
        <el-button plain type="primary" @click="loadDocuments">重新加载</el-button>
      </template>
    </el-alert>

    <div class="knowledge-workspace knowledge-status-only">
      <el-card shadow="never" class="panel-card knowledge-status-card">
        <template #header>资料状态</template>
        <dl>
          <div><dt>资料总数</dt><dd>{{ documents.length }}</dd></div>
          <div><dt>已解析</dt><dd>{{ statusCount('ready') }}</dd></div>
          <div><dt>处理中</dt><dd>{{ processingCount }}</dd></div>
          <div><dt>解析失败</dt><dd class="is-danger">{{ statusCount('failed') }}</dd></div>
        </dl>
        <p>以每份文件的安全检查与解析结果为准。可搜索 PDF、DOCX、MD、TXT 按现有解析流程处理；扫描材料及旧版 DOC 不视为已支持。</p>
      </el-card>
    </div>

    <el-card v-loading="loading" shadow="never" class="panel-card knowledge-table-card ws-list-panel">
      <template #header>
        <div class="card-header knowledge-table-head">
          <div>
            <strong>业务资料管理</strong>
            <small>列表仅展示当前账号有权访问的资料</small>
          </div>
          <div class="knowledge-filters">
            <el-input v-model="keyword" :prefix-icon="Search" clearable placeholder="搜索名称、摘要或标签" />
            <el-select v-model="statusFilter" aria-label="解析状态筛选">
              <el-option label="全部状态" value="all" />
              <el-option label="已解析" value="ready" />
              <el-option label="解析中" value="parsing" />
              <el-option label="等待解析" value="queued" />
              <el-option label="解析失败" value="failed" />
            </el-select>
          </div>
        </div>
      </template>

      <el-table
        height="100%"
        :data="pagedDocuments"
        row-key="id"
        border
      >
        <el-table-column label="文档名称" min-width="300">
          <template #default="{ row }">
            <div class="doc-name" :title="row.name">{{ row.name }}</div>
            <div class="doc-meta">
              <span>{{ row.format || 'FILE' }}</span>
              <span>{{ formatFileSize(row.fileSize) }}</span>
              <span>{{ row.version || 'V1.0' }}</span>
            </div>
            <div v-if="safeTags(row).length" class="doc-keywords">
              <el-tag v-for="tag in safeTags(row).slice(0, 4)" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="资料类型" width="130" />
        <el-table-column label="权限与所有者" min-width="180">
          <template #default="{ row }">
            <div class="permission-cell"><strong>{{ row.permission }}</strong><small>{{ row.owner }}</small></div>
          </template>
        </el-table-column>
        <el-table-column label="解析状态" width="130">
          <template #default="{ row }">
            <el-tooltip :content="row.parseMessage || statusText(row.parseStatus)" placement="top">
              <el-tag :type="statusTag(row.parseStatus)" effect="light">{{ statusText(row.parseStatus) }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="updatedAt" label="更新时间" width="170" />
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button plain type="primary" :disabled="row.allowDownload === false" :icon="Download" @click="downloadDocument(row)">下载</el-button>
            <el-button
              v-if="row.canManage !== false && row.parseStatus !== 'ready'"
              plain
              :loading="isReparsing(row.id)"
              @click="reparseDocument(row)"
            >重新解析</el-button>
            <el-button v-if="row.canManage !== false" plain type="danger" :icon="Delete" @click="removeDocument(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty :description="hasFilters ? '当前筛选条件下没有资料' : '知识库中还没有可访问资料'">
            <el-button v-if="hasFilters" @click="clearFilters">清除筛选</el-button>
          </el-empty>
        </template>
      </el-table>

      <div v-if="filteredDocuments.length" class="knowledge-pagination">
        <span>共 {{ filteredDocuments.length }} 份资料</span>
        <el-pagination
          v-model:current-page="pageNum"
          v-model:page-size="pageSize"
          background
          layout="sizes, prev, pager, next"
          :page-sizes="[10, 20, 50]"
          :total="filteredDocuments.length"
        />
      </div>
    </el-card>

    <el-dialog v-model="uploadVisible" title="上传知识库资料" width="min(620px, calc(100vw - 24px))" @closed="resetUpload">
      <el-form label-position="top">
        <el-form-item label="访问范围"><span>仅自己可见（私有资料）</span></el-form-item>
        <el-upload
          v-model:file-list="uploadFiles"
          drag
          multiple
          action="#"
          accept=".pdf,.docx,.md,.txt"
          :auto-upload="false"
          :limit="10"
          :disabled="uploading"
          :on-change="handleFileChange"
          :on-exceed="handleUploadExceed"
        >
          <el-icon class="upload-icon"><UploadFilled /></el-icon>
          <div class="el-upload__text">拖拽文件到此处，或<em>点击选择</em></div>
          <template #tip>
            <div class="el-upload__tip">支持可搜索 PDF、DOCX、MD、TXT；单个文件不超过 16MB，单次最多 10 份。扫描 PDF 与旧版 DOC 暂不支持解析。</div>
          </template>
        </el-upload>
        <el-progress
          v-if="uploading && uploadFiles.length"
          :percentage="Math.round(completedUploads / uploadFiles.length * 100)"
          :status="completedUploads === uploadFiles.length ? 'success' : undefined"
          class="upload-progress"
        />
      </el-form>
      <template #footer>
        <el-button :disabled="uploading" @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" :disabled="!uploadFiles.length" @click="finishUpload">
          {{ uploading ? `正在上传 ${completedUploads}/${uploadFiles.length}` : (uploadFiles.length ? `上传 ${uploadFiles.length} 份资料` : '选择资料后上传') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Download, Refresh, Search, UploadFilled } from '@element-plus/icons-vue'
import {
  deletePipelineKnowledgeDocument,
  downloadPipelineKnowledgeDocument,
  listPipelineKnowledgeDocuments,
  reparsePipelineKnowledgeDocument,
  uploadPipelineKnowledgeDocument
} from '@/api/pipeline/intelligence'

defineOptions({ name: 'PipelineKnowledge' })

const MAX_FILE_SIZE = 16 * 1024 * 1024
const ALLOWED_EXTENSIONS = new Set(['pdf', 'docx', 'md', 'txt'])
const loading = ref(false)
const loadError = ref('')
const documents = ref([])
const keyword = ref('')
const statusFilter = ref('all')
const pageNum = ref(1)
const pageSize = ref(10)
const uploadVisible = ref(false)
const uploadFiles = ref([])
const uploading = ref(false)
const completedUploads = ref(0)
const reparsingIds = ref(new Set())

const hasFilters = computed(() => Boolean(keyword.value || statusFilter.value !== 'all'))
const processingCount = computed(() => documents.value.filter(item => ['parsing', 'queued'].includes(item.parseStatus)).length)
const filteredDocuments = computed(() => {
  const query = keyword.value.trim().toLocaleLowerCase('zh-CN')
  return documents.value.filter(item => {
    const text = [item.name, item.summary, item.owner, ...safeTags(item)].filter(Boolean).join(' ').toLocaleLowerCase('zh-CN')
    return (statusFilter.value === 'all' || item.parseStatus === statusFilter.value) && (!query || text.includes(query))
  })
})
const pagedDocuments = computed(() => {
  const start = (pageNum.value - 1) * pageSize.value
  return filteredDocuments.value.slice(start, start + pageSize.value)
})

function safeTags(document) { return Array.isArray(document?.tags) ? document.tags : [] }
function statusCount(status) { return documents.value.filter(item => item.parseStatus === status).length }
function statusTag(status) { return ({ ready: 'success', parsing: 'warning', queued: 'info', failed: 'danger' })[status] || 'info' }
function statusText(status) { return ({ ready: '已解析', parsing: '解析中', queued: '等待解析', failed: '解析失败' })[status] || status || '状态未提供' }
function isReparsing(id) { return reparsingIds.value.has(id) }
function extensionOf(name = '') { return name.includes('.') ? name.split('.').pop().toLowerCase() : '' }
function formatFileSize(bytes) {
  const size = Number(bytes || 0)
  if (!size) return '大小未知'
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`
  return `${(size / 1024 / 1024).toFixed(size < 10 * 1024 * 1024 ? 1 : 0)} MB`
}
function validateUploadFile(file) {
  if (!ALLOWED_EXTENSIONS.has(extensionOf(file.name))) return '仅支持可搜索 PDF、DOCX、MD、TXT 文件'
  if (!file.size) return '文件内容为空'
  if (file.size > MAX_FILE_SIZE) return '单个文件不能超过 16MB'
  return ''
}

async function loadDocuments() {
  if (loading.value) return
  loading.value = true
  loadError.value = ''
  try {
    const res = await listPipelineKnowledgeDocuments()
    documents.value = Array.isArray(res.data?.rows) ? res.data.rows : []
    if ((pageNum.value - 1) * pageSize.value >= documents.value.length) pageNum.value = 1
  } catch (error) {
    loadError.value = '知识库资料加载失败，请检查后端服务、登录状态或当前账号权限。'
  } finally {
    loading.value = false
  }
}

function clearFilters() { keyword.value = ''; statusFilter.value = 'all' }
function openUpload() { uploadVisible.value = true }
function resetUpload() {
  if (uploading.value) return
  uploadFiles.value = []
  completedUploads.value = 0
}
function handleUploadExceed() { ElMessage.warning('单次最多上传 10 份资料') }
function handleFileChange(uploadFile, currentFiles) {
  const error = validateUploadFile(uploadFile.raw || uploadFile)
  if (error) {
    uploadFiles.value = currentFiles.filter(item => item.uid !== uploadFile.uid)
    ElMessage.warning(`${uploadFile.name}：${error}`)
    return
  }
  const duplicate = currentFiles.find(item => item.uid !== uploadFile.uid && item.name === uploadFile.name && item.size === uploadFile.size)
  if (duplicate) {
    uploadFiles.value = currentFiles.filter(item => item.uid !== uploadFile.uid)
    ElMessage.warning(`${uploadFile.name} 已在上传列表中`)
  }
}

async function finishUpload() {
  if (!uploadFiles.value.length || uploading.value) return
  const validFiles = uploadFiles.value.filter(item => !validateUploadFile(item.raw || item))
  if (validFiles.length !== uploadFiles.value.length) return ElMessage.warning('上传列表中存在无效文件，请移除后重试')
  uploading.value = true
  completedUploads.value = 0
  const failures = []
  for (const item of validFiles) {
    try {
      const data = new FormData()
      data.append('file', item.raw)
      data.append('permissionScope', 'private')
      await uploadPipelineKnowledgeDocument(data)
      completedUploads.value += 1
    } catch (error) {
      failures.push(item.name)
    }
  }
  try {
    if (completedUploads.value) await loadDocuments()
    if (!failures.length) {
      uploadVisible.value = false
      uploadFiles.value = []
      ElMessage.success('资料上传完成，解析状态已同步到列表')
    } else {
      uploadFiles.value = validFiles.filter(item => failures.includes(item.name))
      ElMessage.error(`${completedUploads.value} 份上传成功，${failures.length} 份失败，请重试失败文件`)
    }
  } finally {
    uploading.value = false
    completedUploads.value = 0
  }
}

async function reparseDocument(document) {
  if (isReparsing(document.id)) return
  reparsingIds.value = new Set([...reparsingIds.value, document.id])
  try {
    await reparsePipelineKnowledgeDocument(document.id)
    await loadDocuments()
    ElMessage.success('资料已重新提交解析')
  } catch (error) {
    ElMessage.error('重新解析失败，请确认资料所有权和解析服务状态')
  } finally {
    const next = new Set(reparsingIds.value)
    next.delete(document.id)
    reparsingIds.value = next
  }
}

async function removeDocument(document) {
  try {
    await ElMessageBox.confirm(`删除“${document.name}”后，该资料将无法继续用于检索和报告生成。`, '删除资料', {
      confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning'
    })
    await deletePipelineKnowledgeDocument(document.id)
    await loadDocuments()
    ElMessage.success('资料已删除')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error('删除失败，请确认资料所有权或稍后重试')
  }
}

function downloadDocument(document) {
  if (document.allowDownload === false) return ElMessage.warning('当前资料禁止下载')
  return downloadPipelineKnowledgeDocument(document.id, document.name).catch(() => {})
}

watch([keyword, statusFilter, pageSize], () => { pageNum.value = 1 })
onMounted(loadDocuments)
</script>

<style scoped>
.ws-list-page .knowledge-status-card :deep(.el-card__header) { padding: 8px 12px; }
.ws-list-page .knowledge-status-card :deep(.el-card__body) { padding: 10px 12px; }
.ws-list-page .knowledge-status-card dl { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.ws-list-page .knowledge-status-card dl div { padding: 8px 12px; }
.ws-list-page .knowledge-status-card dd { font-size: 20px; }
.ws-list-page .knowledge-status-card p { margin: 8px 0 0; font-size: 12px; }
@media (max-width: 760px) {
  .ws-list-page .knowledge-status-card dl { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.heading-actions,
.card-header,
.knowledge-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.knowledge-alert {
  margin-bottom: 16px;
}

.knowledge-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(280px, 0.7fr);
  gap: 16px;
  margin-bottom: 16px;
}

.knowledge-workspace.knowledge-status-only {
  grid-template-columns: minmax(0, 1fr);
}

.card-header > div,
.knowledge-table-head > div:first-child {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.card-header small {
  color: #718096;
  font-size: 13px;
}

.doc-name {
  color: #163c55;
  font-weight: 700;
}

.knowledge-status-card dl {
  margin: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  border: 1px solid #e2e8f0;
  background: #e2e8f0;
}

.knowledge-status-card dl div {
  padding: 14px;
  display: grid;
  gap: 4px;
  background: #fff;
}

.knowledge-status-card dt {
  color: #718096;
  font-size: 13px;
}

.knowledge-status-card dd {
  margin: 0;
  color: #163c55;
  font-size: 22px;
  font-weight: 750;
}

.knowledge-status-card dd.is-danger {
  color: #c24141;
}

.knowledge-status-card p {
  margin: 16px 0;
  color: #667085;
  font-size: 13px;
  line-height: 1.7;
}

.knowledge-filters {
  min-width: min(100%, 500px);
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 150px;
  gap: 10px;
}

.doc-name {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-meta,
.doc-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

.doc-meta span {
  color: #718096;
  font-size: 13px;
}

.permission-cell {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.permission-cell strong,
.permission-cell small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.permission-cell small {
  color: #718096;
}

.knowledge-pagination {
  margin-top: 16px;
  color: #718096;
  font-size: 13px;
}

.upload-config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.upload-icon {
  color: #005487;
  font-size: 42px;
}

.upload-progress {
  margin-top: 16px;
}

@media (max-width: 1100px) {
  .knowledge-workspace {
    grid-template-columns: 1fr;
  }

  .knowledge-status-card dl {
    grid-template-columns: repeat(4, 1fr);
  }
}

@media (max-width: 760px) {
  .heading-actions,
  .knowledge-table-head,
  .knowledge-pagination {
    align-items: stretch;
    flex-direction: column;
  }

  .heading-actions .el-button {
    width: 100%;
    margin: 0;
  }

  .knowledge-filters,
  .upload-config-grid {
    min-width: 0;
    grid-template-columns: 1fr;
  }

  .knowledge-status-card dl {
    grid-template-columns: 1fr 1fr;
  }

}
</style>
