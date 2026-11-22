<template>
  <div class="app-container pipeline-page pipeline-template-page ws-list-page" :class="{ 'is-personal': personal }">
    <nav class="template-purposes" aria-label="模板用途">
      <el-segmented v-model="activePurpose" :options="templatePurposes" aria-label="模板用途" />
    </nav>
    <section class="template-toolbar" aria-label="模板筛选与操作">
      <el-input v-model="keyword" :prefix-icon="Search" clearable aria-label="搜索模板" placeholder="搜索模板名称或说明" />
      <el-select v-model="status" aria-label="模板状态">
        <el-option label="全部状态" value="all" />
        <el-option label="已启用" value="enabled" />
        <el-option label="已停用" value="disabled" />
        <el-option v-if="personal" label="已删除" value="deleted" />
      </el-select>
      <el-button v-if="canSaveTemplate" type="primary" :icon="Plus" :disabled="activePurpose === 'digest' && (loading || !!templateError)" @click="createTemplate">新建模板</el-button>
    </section>
    <nav v-if="activePurpose === 'research'" class="template-categories" aria-label="科研报告类型">
      <el-segmented v-model="activeCategory" :options="categories" :props="{ label: 'name', value: 'value' }">
        <template #default="{ item }"><el-icon class="template-category-icon"><component :is="item.icon" /></el-icon><span>{{ item.name }}</span></template>
      </el-segmented>
    </nav>
    <el-alert v-if="templateError" type="warning" show-icon :closable="false" class="template-load-error">
      <template #title>{{ templateError }}</template>
      <template #default><el-button plain @click="loadTemplates">重新加载</el-button></template>
    </el-alert>
    <section v-else v-loading="loading" class="template-results ws-list-scroll" aria-label="模板列表">
      <div class="template-grid">
        <article v-for="item in filteredTemplates" :key="item.id" class="template-card">
          <div class="template-card-main">
            <header class="template-card-head">
              <span class="template-document-icon"><el-icon><Document /></el-icon></span>
              <h3 :title="item.name">{{ item.name }}</h3>
              <el-tag :type="statusTag(item.status)" effect="light">{{ statusLabel(item.status) }}</el-tag>
            </header>
            <p class="template-description">{{ item.description || '暂无模板说明' }}</p>
            <dl class="template-metadata">
              <div><dt>{{ item.purpose === 'digest' ? '适用周期' : '报告类型' }}</dt><dd>{{ reportTypeLabel(item) }}</dd></div>
              <div><dt>文本模型</dt><dd>{{ modelLabel(item.modelId) }}</dd></div>
              <div v-if="item.purpose === 'research'"><dt>章节结构</dt><dd>{{ item.sections?.length ? `${item.sections.length} 个章节` : '未配置' }}</dd></div>
              <div><dt>最近更新</dt><dd>{{ item.updatedAt || '—' }}</dd></div>
            </dl>
          </div>
          <footer class="template-card-actions">
            <el-button v-if="canSaveTemplate && !item.isDeleted" type="primary" plain :icon="Edit" @click="editTemplate(item)">编辑</el-button>
            <el-button :icon="View" @click="previewTemplate(item)">预览</el-button>
            <el-button v-if="canSaveTemplate && !item.isDeleted" :disabled="saving" @click="toggleTemplate(item)">{{ item.isEnabled ? '停用' : '启用' }}</el-button>
            <el-button v-if="personal && !item.isDeleted" type="danger" plain :disabled="saving" @click="removeTemplate(item)">删除</el-button>
            <el-button v-if="personal && item.isDeleted" type="primary" plain :disabled="saving" @click="restoreTemplate(item)">恢复</el-button>
          </footer>
        </article>
      </div>
      <el-empty v-if="!loading && !filteredTemplates.length" description="当前筛选下暂无模板" :image-size="72" />
    </section>
    <div class="template-result-count"><el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :total="total" :page-sizes="[10, 20, 50]" layout="total, sizes, ->, prev, pager, next, jumper" background aria-label="模板列表分页" /></div>
    <el-dialog
      v-model="editorVisible"
      :title="`${editingTemplate?.id ? '编辑' : '新建'}${form.purpose === 'digest' ? '简报' : '科研报告'}模板`"
      width="min(960px, calc(100vw - 32px))"
      class="ps-centered-dialog template-dialog"
      append-to-body
      align-center
      :close-on-click-modal="false"
    >
      <el-form label-position="top" :model="form" class="template-editor-form" :class="{ 'is-digest': form.purpose === 'digest' }">
        <section class="template-editor-section" aria-label="模板内容">
          <h3>模板内容</h3>
          <div class="template-form-grid">
            <el-form-item label="模板名称" required>
              <el-input v-model="form.name" />
            </el-form-item>
            <el-form-item v-if="form.purpose === 'research'" label="报告类型" required>
              <el-select v-model="form.reportType" clearable placeholder="选择报告类型">
                <el-option v-for="category in categories.filter(item => item.value !== 'all')" :key="category.value" :label="category.name" :value="category.value" />
              </el-select>
            </el-form-item>
            <el-form-item v-else label="适用周期" required>
              <el-select v-model="form.digestCadence" aria-label="简报适用周期">
                <el-option v-for="(label, value) in digestCadences" :key="value" :label="label" :value="value" />
              </el-select>
            </el-form-item>
          </div>
          <el-form-item label="模板说明">
            <el-input v-model="form.description" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="正文生成提示词" required>
            <el-input v-model="form.prompt" type="textarea" :rows="form.purpose === 'digest' ? 3 : 7" />
          </el-form-item>
        </section>

        <section class="template-editor-section" aria-label="生成设置">
          <DigestScreeningRules v-if="form.purpose === 'digest'" v-model:categories="form.screeningCategories" v-model:prompt="form.screeningPrompt" :default-prompt="defaultScreeningPrompt" />
          <h3 v-else>生成设置</h3>
          <el-alert v-if="modelError" :title="modelError" type="warning" :closable="false" class="template-contract-note">
            <template #default><el-button plain @click="loadModels">重新加载模型</el-button></template>
          </el-alert>
          <el-form-item v-if="form.purpose === 'article'" label="文本生成模型">
            <el-select v-model="form.modelId" clearable placeholder="可稍后由管理员配置">
              <el-option v-for="model in textModels" :key="model.modelId" :label="model.modelName || model.modelCode" :value="model.modelId" />
            </el-select>
          </el-form-item>
          <p v-if="form.purpose === 'digest'" class="template-contract-note">筛选和写作使用管理员配置的简报生成模型。</p>
          <p v-else-if="personal" class="template-contract-note">正文与图片模型由管理员统一配置。</p>
          <p v-else class="template-contract-note">正文与图片模型在<router-link to="/pipeline/model">模型管理 → 用途配置</router-link>中统一选择。</p>
          <div class="template-form-grid">
            <el-form-item label="启用模板"><el-switch v-model="form.isEnabled" aria-label="启用模板" /></el-form-item>
            <el-form-item v-if="form.purpose === 'research'" label="启用配图"><el-switch v-model="form.imageConfig.enabled" aria-label="启用配图" /></el-form-item>
          </div>
          <el-form-item v-if="form.purpose === 'research' && form.imageConfig.enabled" label="配图数量">
            <el-input-number v-model="form.imageConfig.count" :min="1" :max="10" />
          </el-form-item>
          <el-form-item v-if="form.purpose === 'research' && form.imageConfig.enabled" label="图片生成提示词">
            <el-input v-model="form.imageConfig.prompt" type="textarea" :rows="3" placeholder="填写配图内容和风格要求" />
          </el-form-item>
        </section>

        <section v-if="form.purpose === 'research'" class="template-editor-section template-editor-sections" aria-label="章节结构">
          <h3>章节结构</h3>
          <div v-for="(section, index) in form.sections" :key="section.id" class="template-section-row">
            <span>{{ index + 1 }}</span>
            <el-input v-model="section.title" :aria-label="'第' + (index + 1) + '章标题'" />
            <el-input-number v-model="section.words" :aria-label="'第' + (index + 1) + '章字数'" :min="100" :max="8000" :step="100" />
            <el-switch v-model="section.required" active-text="必填" :aria-label="'第' + (index + 1) + '章必填'" />
            <el-button :icon="Delete" circle class="ps-ui-action" @click="form.sections.splice(index, 1)" :aria-label="'删除第' + (index + 1) + '章'" />
            <el-input v-model="section.description" type="textarea" :rows="2" class="template-section-prompt" :aria-label="'第' + (index + 1) + '章写作提示词'" placeholder="说明本章的写作重点、证据要求和论证边界" />
          </div>
          <el-button v-if="canSaveTemplate" :icon="Plus" class="template-add-section" @click="form.sections.push({ id: Date.now(), title: '新增章节', words: 1000, required: false })">新增章节</el-button>
        </section>
      </el-form>
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button @click="previewTemplate(form)">预览草稿</el-button>
        <el-button v-if="canSaveTemplate" type="primary" :loading="saving" @click="saveTemplate">保存模板内容</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="previewVisible" :title="previewingTemplate?.name || '模板预览'" width="min(720px, calc(100vw - 32px))" class="ps-centered-dialog template-dialog" append-to-body align-center>
      <div v-if="previewingTemplate" class="template-preview-dialog">
        <div class="preview-meta"><el-tag :type="statusTag(previewingTemplate.status)" effect="plain">{{ statusLabel(previewingTemplate.status) }}</el-tag><span>{{ reportTypeLabel(previewingTemplate) }}</span></div>
        <el-alert title="仅预览模板配置与提示词，不生成报告、不调用模型。" type="info" :closable="false" class="template-contract-note" />
        <el-form label-position="top">
          <el-form-item label="正文生成提示词（只读）"><el-input :model-value="previewingTemplate.prompt" type="textarea" :rows="8" readonly /></el-form-item>
          <DigestScreeningRules v-if="previewingTemplate.purpose === 'digest'" :categories="previewingTemplate.screeningCategories" :prompt="previewingTemplate.screeningPrompt" :default-prompt="defaultScreeningPrompt" readonly />
        </el-form>
        <p v-if="previewingTemplate.description" class="preview-description">{{ previewingTemplate.description }}</p>
        <template v-if="previewingTemplate.purpose === 'research'">
          <div v-if="previewingTemplate.sections?.length" class="preview-sections">
            <div v-for="(section, index) in previewingTemplate.sections" :key="section.id || index" class="preview-section"><span>{{ index + 1 }}</span><div><strong>{{ section.title || '未命名章节' }}</strong><small>{{ section.required ? '必填' : '选填' }} · {{ section.words || '—' }} 字</small></div></div>
          </div>
          <el-empty v-else description="当前模板尚未配置章节结构" :image-size="72" />
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Document, Files, Plus, Search, Edit, View } from '@element-plus/icons-vue'
import { createPipelineTemplate, deletePipelineTemplate, restorePipelineTemplate, getPipelineTemplate, listPipelineTemplates, retirePipelineTemplate, updatePipelineTemplate } from '@/api/pipeline/intelligence'
import { listModelAll } from '@/api/ai/model'
import { modelsFor } from '@/utils/pipeline/compactContract'
import { checkPermi } from '@/utils/permission'
import DigestScreeningRules from '@/views/portal/components/DigestScreeningRules.vue'
import { screeningRulesError } from '@/utils/portal/digestScreeningRules'
const { personal = false } = defineProps({ personal: Boolean })
const emit = defineEmits(['changed'])
const activeCategory = ref('all'), keyword = ref(''), status = ref('all')
const activePurpose = ref('research')
const templatePurposes = [{ label: '科研报告', value: 'research' }, { label: '情报简报', value: 'digest' }]
const digestCadences = { all: '周报和月报', weekly: '周报', monthly: '月报' }
const currentPage = ref(1), pageSize = ref(10), total = ref(0), categoryCounts = ref({})
let listRequest = 0, searchTimer
const editorVisible = ref(false), previewVisible = ref(false), previewingTemplate = ref(null), editingTemplate = ref(null)
const saving = ref(false), loading = ref(false), templateError = ref('')
const canSaveTemplate = computed(() => personal || checkPermi(['pipeline:template:save']))
// These are the portal report keys, not new values for the API's purpose enum.
const categories = [{ name: '全部模板', value: 'all', icon: Files }, { name: '科研需求报告', value: 'research-demand', icon: Document }, { name: '技术路线报告', value: 'technology-route', icon: Document }, { name: '科技项目需求表', value: 'project-demand', icon: Document }]
function reportTypeOf(item) { return ['research-demand', 'technology-route', 'project-demand'].find(key => key === item?.reportType || key === item?.purpose) || '' }
function reportTypeLabel(item) {
 if (item.purpose === 'digest') return digestCadences[item.digestCadence] || '周期待绑定'
 return ({ 'research-demand': '科研需求报告', 'technology-route': '技术路线报告', 'project-demand': '科技项目需求表' })[reportTypeOf(item)] || '报告类型待绑定'
}
const templates = ref([]), models = ref([]), modelError = ref('')
const defaultScreeningCategories = ref([]), defaultScreeningPrompt = ref('')
const unassignedCount = computed(() => categoryCounts.value.unassigned || 0)
const textModels = computed(() => modelsFor(models.value, 'text_generate'))
const imageModels = computed(() => modelsFor(models.value, 'image_generate'))
const form = reactive({ name: '', purpose: 'research', reportType: '', digestCadence: 'all', screeningPrompt: '', screeningCategories: [], prompt: '', description: '', modelId: null, imageModelId: null, sections: [], imageConfig: { enabled: false }, isEnabled: true })
const filteredTemplates = computed(() => templates.value)
function countCategory(value) { return categoryCounts.value[value] || 0 }
function modelLabel(id) {
 if (!id) return '未配置'
 const model = models.value.find(item => String(item.modelId) === String(id))
 return model?.modelName || model?.modelCode || '已配置模型'
}
function statusTag(value) { return value === 'enabled' ? 'success' : 'info' }
function templateStatus(item) { return item.isDeleted ? 'deleted' : item.isEnabled ? 'enabled' : 'disabled' }
function statusLabel(value) { return ({ enabled: '已启用', disabled: '已停用', deleted: '已删除' })[value] || '已停用' }
function resetForm(item = null) {
 Object.assign(form, {
  name: item?.name || '', purpose: item?.purpose || activePurpose.value,
  reportType: reportTypeOf(item) || (activeCategory.value === 'all' ? '' : activeCategory.value),
  digestCadence: item?.digestCadence || 'all', screeningPrompt: item ? item.screeningPrompt || '' : defaultScreeningPrompt.value,
  screeningCategories: (item ? item.screeningCategories || [] : defaultScreeningCategories.value).map(row => ({ ...row })),
  prompt: item?.prompt || '', description: item?.description || '', modelId: item?.modelId ?? null, imageModelId: item?.imageModelId ?? null,
  sections: (item?.sections || []).map(section => ({ ...section })), imageConfig: item ? JSON.parse(JSON.stringify(item.imageConfig || {})) : {}, isEnabled: item?.isEnabled ?? true
 })
 form.imageConfig.enabled ??= false
 form.imageConfig.count ??= 1
 form.imageConfig.prompt ??= ''
}
function createTemplate() { if (!canSaveTemplate.value) return; editingTemplate.value = null; resetForm(); editorVisible.value = true }
async function editTemplate(item) { if (!canSaveTemplate.value) return; try { const { data } = await getPipelineTemplate(item.id); editingTemplate.value = data; resetForm(data); editorVisible.value = true } catch (error) { ElMessage.error(error?.msg || error?.message || '模板详情加载失败') } }
async function previewTemplate(item) {
 try {
  const detail = item.id ? (await getPipelineTemplate(item.id)).data : item
  previewingTemplate.value = { ...JSON.parse(JSON.stringify(detail)), status: templateStatus(detail) }
  previewVisible.value = true
 } catch (error) { ElMessage.error(error?.msg || error?.message || '模板详情加载失败') }
}
async function loadTemplates() {
 const request = ++listRequest
 loading.value = true; templateError.value = ''
 try {
  const res = await listPipelineTemplates({
   page: currentPage.value, pageSize: pageSize.value, keyword: keyword.value.trim(), category: activePurpose.value,
   reportType: activePurpose.value === 'research' && activeCategory.value !== 'all' ? activeCategory.value : undefined, status: status.value
  })
  if (request !== listRequest) return
  if (activePurpose.value === 'digest') {
    defaultScreeningCategories.value = res.data?.defaultScreeningCategories || []
    defaultScreeningPrompt.value = res.data?.defaultScreeningPrompt || ''
  }
  total.value = res.data?.total || 0; categoryCounts.value = res.data?.counts || {}
  const lastPage = Math.max(1, Math.ceil(total.value / pageSize.value))
  if (currentPage.value > lastPage) { currentPage.value = lastPage; return loadTemplates() }
  const rows = res.data?.rows || []
  templates.value = rows.filter(item => item.purpose === activePurpose.value)
   .map(item => ({ ...item, status: templateStatus(item) }))
 }
 catch (error) { if (request === listRequest) templateError.value = error?.msg || error?.message || '模板加载失败，请重试' }
 finally { if (request === listRequest) loading.value = false }
}
async function loadModels() {
 if (!checkPermi(['ai:model:query'])) return
 modelError.value = ''
 try { const res = await listModelAll(); models.value = res.data?.rows || res.data || [] }
 catch (error) { models.value = []; modelError.value = error?.msg || error?.message || '模型列表加载失败；可稍后配置模型' }
}
function templatePayload(item = form) {
 const base = { name: item.name.trim(), purpose: item.purpose, prompt: item.prompt.trim(), description: item.description, isEnabled: item.isEnabled }
 if (item.purpose === 'digest') return { ...base, digestCadence: item.digestCadence, screeningPrompt: item.screeningPrompt, screeningCategories: item.screeningCategories }
 return { ...base, reportType: item.reportType || null, modelId: item.modelId || null, imageModelId: item.imageModelId || null, sections: item.sections, imageConfig: item.imageConfig }
}
async function saveTemplate() {
 if (!canSaveTemplate.value || saving.value) return
 if (!form.name.trim() || !form.prompt.trim()) return ElMessage.warning('请填写模板名称和正文生成提示词')
 if (form.purpose === 'research' && !form.reportType) return ElMessage.warning('请选择模板所属的报告类型')
 if (form.purpose === 'digest') {
   const invalid = screeningRulesError(form.screeningCategories)
   if (invalid) return ElMessage.warning(invalid)
 }
 saving.value = true
 try {
  if (editingTemplate.value) await updatePipelineTemplate(editingTemplate.value.id, templatePayload())
  else await createPipelineTemplate(templatePayload())
  editorVisible.value = false; ElMessage.success('模板已保存'); await loadTemplates(); emit('changed')
 } catch (error) { ElMessage.error(error?.msg || error?.message || '模板保存失败') }
 finally { saving.value = false }
}
async function toggleTemplate(item) {
 if (!canSaveTemplate.value || saving.value) return
 saving.value = true
 try {
  if (item.isEnabled) await retirePipelineTemplate(item.id)
  else { const { data } = await getPipelineTemplate(item.id); await updatePipelineTemplate(item.id, templatePayload({ ...data, isEnabled: true })) }
  ElMessage.success(item.isEnabled ? '模板已停用' : '模板已启用'); await loadTemplates(); emit('changed')
 }
 catch (error) { ElMessage.error(error?.msg || error?.message || '模板状态保存失败') }
 finally { saving.value = false }
}
async function removeTemplate(item) {
 if (!personal || saving.value) return
 try { await ElMessageBox.confirm(`删除“${item.name}”？已生成的报告不受影响，可在“已删除”中恢复。`, '删除模板', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }) }
 catch { return }
 saving.value = true
 try { await deletePipelineTemplate(item.id); await loadTemplates(); emit('changed'); ElMessage.success('模板已删除，可在“已删除”中恢复') }
 catch (error) { ElMessage.error(error?.msg || error?.message || '删除失败') }
 finally { saving.value = false }
}
async function restoreTemplate(item) {
 if (!personal || saving.value) return
 saving.value = true
 try { await restorePipelineTemplate(item.id); await loadTemplates(); emit('changed'); ElMessage.success('模板已恢复，启用后可用于生成') }
 catch (error) { ElMessage.error(error?.msg || error?.message || '恢复失败') }
 finally { saving.value = false }
}
watch([activePurpose, activeCategory, status, pageSize], () => { currentPage.value = 1; loadTemplates() })
watch(currentPage, loadTemplates)
watch(keyword, () => { clearTimeout(searchTimer); listRequest++; searchTimer = setTimeout(() => { currentPage.value = 1; loadTemplates() }, 250) })
onBeforeUnmount(() => { clearTimeout(searchTimer); listRequest++ })
onMounted(() => { loadTemplates(); loadModels() })
</script>
<style scoped>
:global(.el-dialog.ps-centered-dialog.is-align-center.template-dialog > .el-dialog__header) {
 padding-inline: 48px;
 text-align: center;
}
.template-contract-note { margin-bottom: 14px; }
.template-purposes { flex-shrink: 0; padding: 10px 0 0; }
.is-personal > .template-purposes { padding-inline: 20px; }
.template-toolbar {
 display: flex; align-items: center; gap: 10px; padding: 12px 16px;
 background: var(--el-bg-color); border: 1px solid var(--el-border-color-light); border-radius: 8px;
}
.template-toolbar .el-input { flex: 1; min-width: 180px; }
.template-toolbar .el-select { width: 140px; flex-shrink: 0; }
.template-toolbar .el-button { margin: 0 0 0 auto; }
.template-categories { overflow-x: auto; padding: 0 0 2px; }
.template-categories :deep(.el-segmented) { --el-segmented-item-selected-bg-color: #1f64a6; }
.template-categories :deep(.el-segmented__item-label) { display: flex; align-items: center; gap: 6px; }
.template-category-icon { color: var(--el-text-color-secondary); font-size: 15px; }
.template-categories :deep(.el-segmented__item.is-selected) .template-category-icon { color: #fff; }
.template-results { min-width: 0; }
.template-card-main { display: contents; }
.template-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.template-card {
 min-width: 0; display: flex; flex-direction: column; padding: 20px;
 border: 1px solid var(--el-border-color-light); border-radius: 8px; background: var(--el-bg-color);
}
.template-card-head { display: flex; align-items: center; gap: 10px; }
.template-document-icon { display: flex; padding: 9px; border-radius: 6px; background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-size: 20px; }
.template-card h3 { flex: 1; min-width: 0; margin: 0; color: var(--el-text-color-primary); font-size: 16px; line-height: 1.5; overflow-wrap: anywhere; }
.template-card :deep(.el-tag--success) { --el-tag-text-color: #196b3c; --el-tag-bg-color: #edf7ef; --el-tag-border-color: #c5e1cd; }
.template-card :deep(.el-tag--info) { --el-tag-text-color: #526277; }
.template-description { margin: 14px 0; color: var(--el-text-color-regular); font-size: 14px; line-height: 1.7; overflow-wrap: anywhere; }
.template-metadata { display: grid; gap: 10px; margin: auto 0 16px; font-size: 13px; }
.template-metadata > div { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 12px; }
.template-metadata dt { color: var(--ps-muted, #526277); }
.template-metadata dd { margin: 0; color: var(--el-text-color-regular); overflow-wrap: anywhere; }
.template-card-actions { display: flex; flex-wrap: wrap; gap: 8px; padding-top: 14px; border-top: 1px solid var(--el-border-color-lighter); }
.template-section-prompt { grid-column: 2 / -1; }
.template-card-actions .el-button { margin: 0; }
.template-result-count { color: var(--ps-muted, #526277); font-size: 13px; padding: 10px 16px; background: var(--el-bg-color); border: 1px solid var(--el-border-color-light); border-radius: 8px; }
.is-personal {
 display: flex; flex-direction: column; overflow: hidden;
 border: 1px solid var(--ps-line); border-radius: 10px; background: var(--ps-paper);
}
.is-personal > .template-toolbar { flex-shrink: 0; padding: 16px 20px 12px; border: 0; border-radius: 0; background: transparent; }
.is-personal > .template-toolbar :deep(.el-input__wrapper),
.is-personal > .template-toolbar :deep(.el-select__wrapper) { border-radius: 6px; }
.is-personal > .template-toolbar :deep(.el-input__wrapper:focus-within),
.is-personal > .template-toolbar :deep(.el-select__wrapper:focus-within),
.is-personal > .template-toolbar :deep(.el-select__wrapper.is-focused) {
 outline: none;
 box-shadow: 0 0 0 1px var(--el-color-primary) inset;
}
.is-personal > .template-categories { flex-shrink: 0; padding: 0 20px 12px; border-bottom: 1px solid var(--ps-line); }
.is-personal > .template-results { flex: 1 1 0; min-height: 0; overflow: auto; overscroll-behavior: contain; padding: 0 20px; }
.is-personal .template-grid { display: block; }
.is-personal .template-card {
 display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 16px 24px;
 padding: 20px 0; border: 0; border-bottom: 1px solid var(--ps-line); border-radius: 0; background: transparent;
}
.is-personal .template-card-main { display: block; min-width: 0; }
.is-personal .template-card-head { align-items: flex-start; }
.is-personal .template-document-icon { flex: 0 0 32px; height: 32px; align-items: center; justify-content: center; padding: 0; font-size: 18px; }
.is-personal .template-card h3 { flex: 0 1 auto; padding-block: 3px; }
.is-personal .template-card-head > .el-tag { flex-shrink: 0; margin-top: 4px; }
.is-personal .template-description { margin: 8px 0 12px 42px; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; }
.is-personal .template-metadata { display: flex; flex-wrap: wrap; gap: 8px 20px; margin: 0 0 0 42px; font-size: 13px; line-height: 1.6; }
.is-personal .template-metadata > div { display: flex; gap: 8px; min-width: 0; }
.is-personal .template-metadata dt { flex-shrink: 0; }
.is-personal .template-card-actions { justify-content: flex-end; padding: 0; border: 0; }
@container workspace (min-width: 761px) {
 .is-personal .template-card-actions { display: grid; grid-template-columns: repeat(2, auto); }
}
.is-personal > .template-result-count { flex-shrink: 0; border: 0; border-top: 1px solid var(--ps-line); border-radius: 0; padding: 12px 20px; }
.is-personal .template-load-error { margin: 16px 20px; }
@container workspace (max-width: 760px) {
 .is-personal > .template-toolbar { flex-wrap: wrap; }
 .is-personal > .template-toolbar .el-input { flex-basis: 100%; min-width: 0; }
 .is-personal > .template-toolbar .el-select { flex: 1 1 100px; width: auto; }
 .is-personal .template-card { grid-template-columns: minmax(0, 1fr); gap: 14px; }
 .is-personal .template-card-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); padding-left: 42px; }
 .is-personal .template-card-actions .el-button { min-height: 44px; }
 .is-personal > .template-toolbar .el-button { min-height: 44px; }
 .is-personal > .template-toolbar :deep(.el-input__wrapper),
 .is-personal > .template-toolbar :deep(.el-select__wrapper) { min-height: 44px; }
}
@container workspace (max-width: 480px) {
 .is-personal > .template-toolbar { padding: 12px; gap: 8px; }
 .is-personal > .template-categories { padding-inline: 12px; }
 .is-personal > .template-results { padding-inline: 12px; }
 .is-personal .template-description, .is-personal .template-metadata { margin-left: 0; }
 .is-personal .template-card-actions { padding-left: 0; }
 .is-personal > .template-result-count { padding-inline: 12px; }
}
.template-editor-form { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); align-items: start; gap: 20px; }
.template-editor-form.is-digest { grid-template-columns: minmax(0, 1fr); gap: 12px; }
.template-editor-section {
 min-width: 0;
 padding: 16px;
 border: 1px solid var(--el-border-color-lighter);
 border-radius: 8px;
}
.template-editor-section h3 { margin: 0 0 14px; color: var(--el-text-color-primary); font-size: 15px; line-height: 1.4; }
.template-editor-section > .el-form-item:last-child,
.template-editor-section > .template-form-grid:last-child > .el-form-item { margin-bottom: 0; }
.template-editor-section :deep(.el-select) { width: 100%; }
.template-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 14px; }
.template-editor-sections { grid-column: 1 / -1; }
.template-section-row {
 min-height: 48px;
 display: grid;
 grid-template-columns: 24px minmax(0, 1fr) 120px 68px 32px;
 align-items: center;
 gap: 8px 12px;
 border-bottom: 1px solid var(--el-border-color-lighter);
}
.template-section-row > span:first-child { text-align: center; color: var(--el-text-color-secondary); font-variant-numeric: tabular-nums; }
.template-section-row > button { justify-self: end; }
.template-add-section { margin-top: 12px; }
.template-section-row > .el-input-number { width: 100%; }
@media (max-width: 540px) {
 .template-editor-section { padding: 12px; }
 .template-editor-section:first-child .template-form-grid { grid-template-columns: minmax(0, 1fr); }
 .template-section-row { grid-template-columns: 18px minmax(0, 1fr) auto 32px; gap: 8px; padding: 8px 0; }
 .template-section-row > .el-input { grid-column: 2 / 4; }
 .template-section-row > .el-input-number { grid-column: 2; grid-row: 2; max-width: 120px; }
 .template-section-row > .el-switch { grid-column: 3 / 5; grid-row: 2; }
 .template-section-row > button { grid-column: 4; grid-row: 1; }
}
.preview-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; color: #64748b; font-size: 13px; }.preview-description { margin: 18px 0; color: #475569; line-height: 1.7; }.preview-sections { border-top: 1px solid #e2e8f0; }.preview-section { min-height: 58px; padding: 10px 0; border-bottom: 1px solid #edf1f6; display: flex; align-items: center; gap: 12px; }.preview-section > span { width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; background: #edf3ff; color: #409eff; font-size: 13px; font-weight: 700; }.preview-section div { display: flex; flex-direction: column; gap: 4px; }.preview-section small { color: #64748b; font-size: 13px; }
@media (max-width: 1200px) { .template-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) {
 .template-grid, .template-editor-form { grid-template-columns: minmax(0, 1fr); }
 .template-toolbar { flex-wrap: wrap; padding: 12px; }
 .template-toolbar .el-input { flex: 1 1 100%; min-width: 0; }
 .template-toolbar .el-select { flex: 1; min-width: 100px; }
 .template-card { padding: 16px; }
}
</style>
