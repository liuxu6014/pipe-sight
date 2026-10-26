<template>
  <div class="ps-page">
    <nav v-if="mode !== 'basket'" class="ps-workspace-tabs" aria-label="个人中心栏目">
      <router-link v-for="tab in workspaceTabs" :key="tab.mode" :to="'/portal/me/' + tab.mode" :aria-current="mode === tab.mode ? 'page' : undefined">{{ tab.label }}</router-link>
    </nav>
    <div v-if="mode !== 'basket'" class="ps-workspace-filter">
      <el-input class="ps-search-input" v-model.trim="keyword" clearable aria-label="搜索个人事项" :placeholder="'搜索' + pageConfig.title" />
      <el-select v-if="mode === 'tasks'" v-model="statusFilter" aria-label="任务状态"><el-option label="全部状态" value="" /><el-option label="进行中" value="active" /><el-option label="生成完成" value="completed" /><el-option label="失败" value="failed" /><el-option label="已取消" value="cancelled" /></el-select>
      <el-button v-if="keyword || statusFilter" @click="keyword = ''; statusFilter = ''">清除筛选</el-button>
    </div>
    <div v-if="sectionError" class="ps-inline-state is-warning" role="alert"><span>{{ sectionError }}，请重试获取当前栏目。</span><el-button text :loading="portalStore.dataLoading" @click="portalStore.hydrate(true)">重试</el-button></div>
    <el-skeleton v-if="portalStore.dataLoading && !portalStore.dataLoaded" :rows="5" animated />
    <template v-else>
      <div v-if="mode === 'tasks'" class="ps-my-task-grid ws-card-grid">
        <article v-for="task in pagedItems" :key="task.id" class="ps-my-task-card">
          <div><span class="ps-task-status" :class="`is-${task.status}`"></span><span><strong>{{ task.title }}</strong><small>{{ task.type }} · {{ task.updatedAt }}</small></span><b>{{ task.statusLabel }}</b></div>
          <el-progress :percentage="Math.max(0, Math.min(100, Number(task.progress) || 0))" :stroke-width="7" :status="task.status === 'failed' ? 'exception' : undefined" />
          <footer><span>{{ taskHint(task) }}</span><el-button type="primary" text @click="openTask(task)">{{ taskActionLabel(task) }}</el-button></footer>
        </article>
      </div>
      <section v-else-if="mode === 'reports'" class="ps-report-table ps-my-report-table ps-panel" aria-label="我的成果列表">
        <div class="ps-table-head"><span>成果名称</span><span>业务状态</span><span>版本</span><span>字数</span><span>更新时间</span><span></span></div>
        <button v-for="report in pagedItems" :key="report.id" type="button" @click="router.push(getPortalReportPath(report))">
          <span><strong>{{ report.title }}</strong><small>{{ report.type }}</small></span><span><b class="ps-status-pill">{{ report.status }}</b></span><span>{{ report.version }}</span><span>{{ report.words ? report.words.toLocaleString() : '待统计' }}</span><span>{{ report.updatedAt }}</span><ArrowRight />
        </button>
      </section>
      <section v-else-if="mode === 'basket' && !sectionError" class="ps-panel ps-basket-panel">
        <div class="ps-basket-toolbar">
          <el-input class="ps-search-input" v-model.trim="keyword" clearable aria-label="搜索资料篮" placeholder="搜索资料标题或类型" />
          <el-button :icon="UploadFilled" @click="uploadVisible = true">上传资料</el-button>
          <el-button type="primary" :disabled="!basketSelection.selectedItems.value.length" @click="createFromSelection">新建报告</el-button>
        </div>
        <div v-if="portalStore.basketCount" class="ps-basket-selection-tools">
          <el-checkbox :model-value="basketSelection.allVisible.value" :indeterminate="basketSelection.indeterminate.value" :disabled="!visibleItems.length" @change="basketSelection.toggleVisible">全选当前结果</el-checkbox>
          <span role="status">已选 {{ basketSelection.selectedItems.value.length }} 条</span>
          <el-button v-if="basketSelection.selectedItems.value.length" text @click="basketSelection.selectedIds.value = []">清空选择</el-button>
        </div>
        <p v-if="basketParsing.error.value" class="ps-basket-status-error" role="status">{{ basketParsing.error.value }}</p>
        <div class="ps-basket-list"><div v-for="item in pagedItems" :key="item.id">
          <el-checkbox :model-value="basketSelection.selectedIds.value.includes(item.id)" :aria-label="`选择资料：${item.title}`" @change="basketSelection.toggle(item.id, $event)" />
          <span class="ps-file-icon" aria-hidden="true"><component :is="basketIcon(item)" /></span>
          <span class="ps-basket-item-copy"><router-link v-if="itemPath(item)" :to="itemPath(item)">{{ item.title }}</router-link><strong v-else>{{ item.title }}</strong><small>{{ basketItemLabel(item) }}<span v-if="basketParsing.label(item.id)" role="status"> · {{ basketParsing.label(item.id) }}</span><el-button v-if="basketParsing.label(item.id) === '解析失败'" text type="primary" :loading="basketParsing.retrying.value.includes(item.id)" :aria-label="`重试解析：${item.title}`" @click="basketParsing.retry(item.id)">重试</el-button></small></span><el-button text type="danger" @click="portalStore.removeFromBasket(item.id)">移除</el-button>
        </div></div>
        <div v-if="!visibleItems.length" class="ps-basket-empty" role="status">
          <p>{{ portalStore.basketCount ? '没有匹配资料' : '暂无资料' }}</p>
          <el-button v-if="portalStore.basketCount" @click="keyword = ''">清除筛选</el-button>
        </div>
        <div v-if="visibleItems.length" class="ps-pagination ps-basket-pagination" aria-label="资料列表分页"><el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[10, 20, 50]" :total="visibleItems.length" :pager-count="5" layout="total, sizes, ->, prev, pager, next, jumper" background /></div>
      </section>
      <PortalEmptyState v-if="mode !== 'basket' && !visibleItems.length && !sectionError" :title="keyword || statusFilter ? '没有匹配记录' : pageConfig.empty" :description="keyword || statusFilter ? '清除筛选或尝试其他关键词。' : pageConfig.description" :action-label="keyword || statusFilter ? '清除筛选' : mode === 'reports' ? '' : pageConfig.action" @action="emptyAction" />
      <div v-if="mode !== 'basket' && visibleItems.length && !sectionError" class="ps-pagination" aria-label="资料列表分页"><el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[10, 20, 50]" :total="visibleItems.length" :pager-count="5" layout="total, sizes, ->, prev, pager, next, jumper" background /></div>
    </template>
    <el-dialog v-if="mode === 'basket'" v-model="uploadVisible" title="上传资料" width="min(480px, calc(100vw - 32px))" append-to-body :close-on-click-modal="!uploading" :close-on-press-escape="!uploading" :show-close="!uploading" @open="uploadError = ''">
      <input ref="fileInput" class="ps-visually-hidden" type="file" accept=".pdf,.docx,.md,.txt" aria-label="选择上传资料" :disabled="uploading" @change="uploadMaterial" />
      <button type="button" class="ps-upload-drop ps-basket-upload" :disabled="uploading" @click="fileInput?.click()"><UploadFilled /><span>{{ uploading ? '正在上传…' : '选择文件上传' }}</span><small>支持可搜索 PDF、DOCX、MD、TXT，最大 16MB</small></button>
      <p class="ps-basket-upload-hint">上传后保存到资料库，并加入资料篮。</p>
      <p v-if="uploadError" role="alert">{{ uploadError }}</p>
      <template #footer><el-button :disabled="uploading" @click="uploadVisible = false">取消</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, UploadFilled, Document, Reading, Tickets } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'
import { getPortalReportPath, getPortalTaskPath } from '../utils/routing'
import { ownedReports } from '../utils/workspace'
import useUserStore from '@/store/modules/user'
import { useBasketSelection } from '@/utils/portal/basketSelection'
import { basketItemLabel, basketItemPath, uploadBasketFile, validateBasketUpload } from '@/utils/portal/basketItems'
import { useBasketParsing } from '@/utils/portal/basketParsing'
import { uploadPipelineKnowledgeDocument, savePipelineWorkspaceItem, listPipelineKnowledgeDocuments, reparsePipelineKnowledgeDocument } from '@/api/pipeline/intelligence'

const props = defineProps({ mode: { type: String, default: 'tasks' } })
const router = useRouter()
const portalStore = usePortalStore()
const userStore = useUserStore()
const keyword = ref('')
const statusFilter = ref('')
const uploadVisible = ref(false)
const uploading = ref(false)
const uploadError = ref('')
const fileInput = ref(null)
const basketParsing = useBasketParsing(portalStore, () => props.mode === 'basket', { list: listPipelineKnowledgeDocuments, retry: reparsePipelineKnowledgeDocument })
function itemPath(item) {
  if (item.type === 'report') return getPortalReportPath(allReports.value.find(report => report.id === item.id) || item)
  return basketItemPath(item)
}
function basketIcon(item) {
  const label = basketItemLabel(item)
  return label === '论文' ? Reading : label === '新闻资讯' ? Tickets : Document
}
async function uploadMaterial(event) {
  const file = event.target.files?.[0]
  if (!file || uploading.value) return
  const validation = validateBasketUpload(file)
  if (validation) { ElMessage.warning(validation); event.target.value = ''; return }
  uploading.value = true
  uploadError.value = ''
  try {
    const result = await uploadBasketFile(file, { upload: uploadPipelineKnowledgeDocument, save: savePipelineWorkspaceItem, refresh: () => portalStore.hydrate(true) })
    keyword.value = ''
    uploadVisible.value = false
    if (result.basketError) ElMessage.warning('已保存到资料库，但加入资料篮失败，请到资料库重新加入')
    else ElMessage.success('已保存到资料库，并加入资料篮')
  } catch (error) {
    uploadError.value = error?.msg || error?.message || '上传失败，请稍后重试'
  } finally { uploading.value = false; event.target.value = '' }
}
const workspaceTabs = [{ mode: 'reports', label: '我的报告' }]
const pageConfig = computed(() => ({
  tasks: { title: '我的任务', description: '跟踪本人科研报告与情报简报生成任务；完成、失败和取消分别显示。', empty: '当前没有任务', action: '新建科研报告', path: '/portal/research/create' },
  reports: { title: '我的成果', description: '查看本人科研报告和情报简报，生成完成不等于审核或正式发布。', empty: '当前没有成果', action: '新建科研报告', path: '/portal/research/create' },
  basket: { title: '资料篮', description: '整理本次编制使用的资料。移除不删除原文件，生成时重新核验授权。', empty: '资料篮还是空的', action: '浏览资料库', path: '/portal/knowledge' }
})[props.mode] || { title: '个人事项', description: '', empty: '暂无内容', action: '返回首页', path: '/portal' })
const sectionError = computed(() => props.mode === 'tasks' ? portalStore.sectionErrors.tasks
  : props.mode === 'reports' ? portalStore.sectionErrors.reports || portalStore.sectionErrors.digests
  : portalStore.sectionErrors.workspace)
const visibleItems = computed(() => {
  const source = props.mode === 'tasks' ? portalStore.tasks : props.mode === 'reports' ? allReports.value : props.mode === 'basket' ? portalStore.basket : []
  return source.filter(item => {
    const matchesText = !keyword.value || [item.title, item.type, item.summary, props.mode === 'basket' ? basketItemLabel(item) : ''].filter(Boolean).join(' ').toLocaleLowerCase().includes(keyword.value.toLocaleLowerCase())
    const matchesStatus = props.mode !== 'tasks' || !statusFilter.value || (statusFilter.value === 'active'
      ? !['completed', 'cancelled', 'failed'].includes(item.status) : item.status === statusFilter.value)
    return matchesText && matchesStatus
  })
})
const basketSelection = useBasketSelection(() => portalStore.basket, () => props.mode === 'basket' ? visibleItems.value : [], () => portalStore.workspaceEpoch)
const currentPage = ref(1)
const pageSize = ref(10)
const pagedItems = computed(() => visibleItems.value.slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value))
watch([keyword, statusFilter, pageSize, () => props.mode], () => { currentPage.value = 1 })
watch(() => visibleItems.value.length, count => { currentPage.value = Math.min(currentPage.value, Math.max(1, Math.ceil(count / pageSize.value))) })
function createFromSelection() {
  const ids = basketSelection.selectedItems.value.map(item => item.id)
  if (ids.length) router.push({ path: '/portal/research/create', query: { selected: ids } })
}
function emptyAction() {
  if (keyword.value || statusFilter.value) { keyword.value = ''; statusFilter.value = ''; return }
  router.push(pageConfig.value.path)
}
const allReports = computed(() => ownedReports([...portalStore.researchReports, ...portalStore.digestReports], portalStore.tasks, userStore.id))
function openTask(task) { router.push(getPortalTaskPath(task)) }
function taskActionLabel(task) { return task.status === 'completed' && task.reportId ? (task.requiresReview ? '查看草稿' : '查看结果') : ['failed', 'cancelled'].includes(task.status) ? '查看详情' : '查看进度' }
function taskHint(task) {
  if (task.status === 'completed') return task.reportId ? (task.requiresReview ? '已生成待复核草稿，暂不作为正式成果' : '任务已完成，可查看结果') : '任务已完成'
  if (task.status === 'failed') return '生成失败，可查看原因并重新生成'
  if (task.status === 'cancelled') return '任务已取消，可按原配置重新生成'
  return `当前进度 ${task.progress}%`
}
</script>

<style scoped>
.ps-basket-panel { padding: 20px 24px; }
.ps-basket-toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.ps-basket-toolbar > .el-input { flex: 1; min-width: 0; }
.ps-basket-toolbar :deep(.el-button) { flex-shrink: 0; margin-left: 0; min-height: 44px; }
.ps-basket-toolbar :deep(.el-input__wrapper) { min-height: 44px; }
.ps-basket-empty { display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 12px; min-height: 180px; }
.ps-basket-empty p { margin: 0; color: var(--ps-muted); font-size: 15px; }
.ps-basket-empty :deep(.el-button) { min-height: 44px; }
.ps-basket-selection-tools { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 16px; padding-bottom: 12px; color: var(--ps-muted); font-size: 13px; }
.ps-basket-list > div > .el-checkbox { flex: 0 0 auto; margin: 0; }
.ps-basket-list > div { grid-template-columns: 24px 34px minmax(0, 1fr) 48px; }
.ps-basket-list > div > .ps-file-icon { display: grid; }
.ps-basket-item-copy { display: flex; flex-direction: column; min-width: 0; }
.ps-basket-item-copy small { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.ps-basket-item-copy small :deep(.el-button) { min-height: 28px; padding: 4px 8px; }
.ps-basket-status-error { color: var(--ps-muted); font-size: 13px; }
.ps-basket-item-copy a { color: var(--ps-ink); font-weight: 600; line-height: 1.6; overflow-wrap: anywhere; }
.ps-basket-item-copy a:hover { color: var(--ps-blue); text-decoration: underline; }
.ps-basket-item-copy a:focus-visible { outline: 2px solid var(--ps-blue); outline-offset: 3px; border-radius: 3px; }
.ps-basket-panel .ps-basket-pagination { margin: 8px -24px -20px; padding: 14px 24px; border-top: 1px solid var(--ps-line); }
.ps-basket-upload { width: 100%; margin: 0; }
.ps-basket-upload-hint { color: var(--ps-muted); margin-bottom: 0; }
.ps-basket-list .ps-basket-item-copy strong { white-space: normal; overflow-wrap: anywhere; }
@media (max-width: 600px) {
  .ps-basket-panel { padding: 16px; }
  .ps-basket-toolbar { gap: 8px; }
  .ps-basket-toolbar { flex-wrap: wrap; }
  .ps-basket-toolbar > .el-input { flex-basis: 100%; }
  .ps-basket-panel .ps-basket-pagination { margin: 8px -16px -16px; padding: 12px 16px; overflow-x: auto; }
  .ps-basket-toolbar :deep(.el-input__inner) { font-size: 16px; }
  .ps-basket-selection-tools { gap: 8px 12px; }
}
</style>
