<template>
  <div class="app-container pipeline-page pipeline-template-page ws-list-page">
    <section class="template-toolbar" aria-label="模板筛选与操作">
      <el-input v-model="keyword" :prefix-icon="Search" clearable aria-label="搜索模板" placeholder="搜索模板名称或说明" />
      <el-select v-model="status" aria-label="模板状态">
        <el-option label="全部状态" value="all" />
        <el-option label="已启用" value="enabled" />
        <el-option label="已停用" value="disabled" />
      </el-select>
      <el-button :icon="Refresh" :loading="loading" @click="loadTemplates">刷新</el-button>
      <el-button v-if="canSaveTemplate" type="primary" :icon="Plus" @click="createTemplate">新建模板</el-button>
    </section>
    <nav class="template-categories" aria-label="模板类别">
      <el-segmented v-model="activeCategory" :options="categories" :props="{ label: 'name', value: 'value' }">
        <template #default="{ item }"><span>{{ item.name }}</span><span class="template-category-count">{{ countCategory(item.value) }}</span></template>
      </el-segmented>
    </nav>
    <el-alert v-if="templateError" type="warning" show-icon :closable="false" class="template-load-error">
      <template #title>{{ templateError }}</template>
      <template #default><el-button plain @click="loadTemplates">重新加载</el-button></template>
    </el-alert>
    <section v-else v-loading="loading" class="template-results ws-list-scroll" aria-label="模板列表">
      <div class="template-grid">
        <article v-for="item in filteredTemplates" :key="item.id" class="template-card">
          <header class="template-card-head">
            <span class="template-document-icon"><el-icon><Document /></el-icon></span>
            <h3>{{ item.name }}</h3>
            <el-tag :type="statusTag(item.status)" effect="light">{{ statusLabel(item.status) }}</el-tag>
          </header>
          <p class="template-description">{{ item.description || '暂无模板说明' }}</p>
          <dl class="template-metadata">
            <div><dt>报告类型</dt><dd>{{ reportTypeLabel(item) }}</dd></div>
            <div><dt>文本模型</dt><dd>{{ modelLabel(item.modelId) }}</dd></div>
            <div><dt>章节结构</dt><dd>{{ item.sections?.length ? `${item.sections.length} 个章节` : '未配置' }}</dd></div>
            <div><dt>最近更新</dt><dd>{{ item.updatedAt || '—' }}</dd></div>
          </dl>
          <footer class="template-card-actions">
            <el-button v-if="canSaveTemplate" type="primary" plain :icon="Edit" @click="editTemplate(item)">编辑</el-button>
            <el-button :icon="View" @click="previewTemplate(item)">预览</el-button>
            <el-button v-if="canSaveTemplate" :disabled="saving" @click="toggleTemplate(item)">{{ item.isEnabled ? '停用' : '启用' }}</el-button>
          </footer>
        </article>
      </div>
      <el-empty v-if="!loading && !filteredTemplates.length" description="当前筛选下暂无模板" :image-size="72" />
    </section>
    <div class="template-result-count" aria-live="polite">共 {{ filteredTemplates.length }} 个模板<span v-if="unassignedCount"> · {{ unassignedCount }} 个未绑定报告类型</span></div>
    <el-drawer v-model="editorVisible" :title="editingTemplate?.id ? '编辑模板' : '新建模板'" size="640px"><el-form label-position="top" :model="form"><div class="template-form-grid"><el-form-item label="模板名称" required><el-input v-model="form.name" /></el-form-item><el-form-item label="报告类型" :required="form.purpose === 'research'"><el-select v-model="form.reportType" clearable placeholder="选择报告类型"><el-option v-for="category in categories.filter(item => item.value !== 'all')" :key="category.value" :label="category.name" :value="category.value" /></el-select></el-form-item><el-form-item label="模板说明" class="is-full"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item></div>
 <el-alert class="template-contract-note" type="warning" :closable="false" title="模板按报告类型展示，同一类型可配置多个模板；保存时保留各模板的独立内容。" /><el-form-item label="正文生成提示词" required><el-input v-model="form.prompt" type="textarea" :rows="6" /></el-form-item>
 <el-alert v-if="modelError" :title="modelError" type="warning" :closable="false"><template #default><el-button plain @click="loadModels">重新加载模型</el-button></template></el-alert>
 <el-form-item label="文本生成模型"><el-select v-model="form.modelId" clearable placeholder="可稍后由管理员配置"><el-option v-for="model in textModels" :key="model.modelId" :label="model.modelName || model.modelCode" :value="model.modelId" /></el-select></el-form-item>
 <el-form-item label="启用配图"><el-switch v-model="form.imageConfig.enabled" /></el-form-item>
 <el-form-item label="图片生成模型"><el-select v-model="form.imageModelId" clearable placeholder="仅显示具备图片生成能力的模型"><el-option v-for="model in imageModels" :key="model.modelId" :label="model.modelName || model.modelCode" :value="model.modelId" /></el-select></el-form-item>
 <el-form-item v-if="form.imageConfig.enabled" label="配图数量"><el-input-number v-model="form.imageConfig.count" :min="1" :max="10" /></el-form-item>
 <el-form-item v-if="form.imageConfig.enabled" label="图片生成提示词"><el-input v-model="form.imageConfig.prompt" type="textarea" :rows="3" placeholder="填写配图内容和风格要求；本页不执行图片生成" /></el-form-item>
 <el-form-item label="启用模板"><el-switch v-model="form.isEnabled" /></el-form-item>
 <h3>章节结构</h3><div v-for="(section, index) in form.sections" :key="section.id" class="template-section-row"><Rank /><span>{{ index + 1 }}</span><el-input v-model="section.title" :aria-label="'第' + (index + 1) + '章标题'" /><el-input-number :aria-label="'第' + (index + 1) + '章字数'" v-model="section.words" :min="100" :max="8000" :step="100" /><el-switch v-model="section.required" active-text="必填" /><el-button :icon="Delete" circle class="ps-ui-action" @click="form.sections.splice(index, 1)" aria-label="删除章节" /></div><el-button :icon="Plus" v-if="canSaveTemplate" class="template-add-section" @click="form.sections.push({ id: Date.now(), title: '新增章节', words: 1000, required: false })">新增章节</el-button></el-form><template #footer><el-button @click="editorVisible = false">取消</el-button><el-button @click="previewTemplate({ ...form, status: form.isEnabled ? 'enabled' : 'disabled' })">预览草稿</el-button><el-button v-if="canSaveTemplate" type="primary" :loading="saving" @click="saveTemplate">保存模板内容</el-button></template></el-drawer>
    <el-dialog v-model="previewVisible" :title="previewingTemplate?.name || '模板预览'" width="min(720px, calc(100vw - 32px))"><div v-if="previewingTemplate" class="template-preview-dialog"><div class="preview-meta"><el-tag :type="statusTag(previewingTemplate.status)" effect="plain">{{ statusLabel(previewingTemplate.status) }}</el-tag><span>{{ reportTypeLabel(previewingTemplate) }}</span></div><el-alert title="仅模板配置与提示词预览，不生成报告、不调用模型。" type="info" :closable="false" class="template-contract-note" /><el-form label-position="top"><el-form-item label="正文生成提示词（只读）"><el-input :model-value="previewingTemplate.prompt" type="textarea" :rows="8" readonly /></el-form-item></el-form><p class="preview-description">{{ previewingTemplate.description || '暂无模板说明' }}</p><div v-if="previewingTemplate.sections?.length" class="preview-sections"><div v-for="(section, index) in previewingTemplate.sections" :key="section.id || index" class="preview-section"><span>{{ index + 1 }}</span><div><strong>{{ section.title || '未命名章节' }}</strong><small>{{ section.required ? '必填' : '选填' }} · {{ section.words || '—' }} 字</small></div></div></div><el-empty v-else description="当前模板尚未配置章节结构" :image-size="72" /></div></el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete, Document, Files, Plus, Rank, Search, Refresh, Edit, View } from '@element-plus/icons-vue'
import { createPipelineTemplate, listPipelineTemplates, retirePipelineTemplate, updatePipelineTemplate } from '@/api/pipeline/intelligence'
import { listModelAll } from '@/api/ai/model'
import { modelsFor } from '@/utils/pipeline/compactContract'
import { checkPermi } from '@/utils/permission'
const activeCategory = ref('all'), keyword = ref(''), status = ref('all')
const editorVisible = ref(false), previewVisible = ref(false), previewingTemplate = ref(null), editingTemplate = ref(null)
const saving = ref(false), loading = ref(false), templateError = ref('')
const canSaveTemplate = computed(() => checkPermi(['pipeline:template:save']))
// These are the portal report keys, not new values for the API's purpose enum.
const categories = [{ name: '全部模板', value: 'all', icon: Files }, { name: '科研需求报告', value: 'research-demand', icon: Document }, { name: '技术路线报告', value: 'technology-route', icon: Document }, { name: '科技项目需求表', value: 'project-demand', icon: Document }]
function reportTypeOf(item) { return ['research-demand', 'technology-route', 'project-demand'].find(key => key === item?.reportType || key === item?.purpose) || '' }
function reportTypeLabel(item) { return ({ 'research-demand': '科研需求报告', 'technology-route': '技术路线报告', 'project-demand': '科技项目需求表' })[reportTypeOf(item)] || '报告类型待绑定' }
const templates = ref([]), models = ref([]), modelError = ref('')
const unassignedCount = computed(() => templates.value.filter(item => !reportTypeOf(item)).length)
const textModels = computed(() => modelsFor(models.value, 'text_generate'))
const imageModels = computed(() => modelsFor(models.value, 'image_generate'))
const form = reactive({ name: '', purpose: 'research', reportType: '', prompt: '', description: '', modelId: null, imageModelId: null, sections: [], imageConfig: { enabled: false }, isEnabled: true })
const filteredTemplates = computed(() => templates.value.filter(item => (activeCategory.value === 'all' || reportTypeOf(item) === activeCategory.value) && (status.value === 'all' || item.status === status.value) && (!keyword.value.trim() || `${item.name} ${item.description || ''}`.includes(keyword.value.trim()))))
function countCategory(value) { return value === 'all' ? templates.value.length : templates.value.filter(item => reportTypeOf(item) === value).length }
function modelLabel(id) {
 if (!id) return '未配置'
 const model = models.value.find(item => String(item.modelId) === String(id))
 return model?.modelName || model?.modelCode || '已配置模型'
}
function statusTag(value) { return value === 'enabled' ? 'success' : 'info' }
function statusLabel(value) { return value === 'enabled' ? '已启用' : '已停用' }
function resetForm(item = null) {
 Object.assign(form, { name: item?.name || '', purpose: item?.purpose || 'research', reportType: reportTypeOf(item) || (activeCategory.value === 'all' ? '' : activeCategory.value), prompt: item?.prompt || '', description: item?.description || '', modelId: item?.modelId ?? null, imageModelId: item?.imageModelId ?? null, sections: (item?.sections || []).map(section => ({ ...section })), imageConfig: item ? JSON.parse(JSON.stringify(item.imageConfig || {})) : {}, isEnabled: item?.isEnabled ?? true })
 form.imageConfig.enabled ??= false
 form.imageConfig.count ??= 1
 form.imageConfig.prompt ??= ''
}
function createTemplate() { if (!canSaveTemplate.value) return; editingTemplate.value = null; resetForm(); editorVisible.value = true }
function editTemplate(item) { if (!canSaveTemplate.value) return; editingTemplate.value = item; resetForm(item); editorVisible.value = true }
function previewTemplate(item) { previewingTemplate.value = JSON.parse(JSON.stringify(item)); previewVisible.value = true }
async function loadTemplates() {
 loading.value = true; templateError.value = ''
 try {
  const res = await listPipelineTemplates()
  const rows = res.data?.rows || []
  const reportRows = rows.filter(item => item.purpose === 'research' || reportTypeOf(item))
  templates.value = reportRows.map(item => ({ ...item, status: item.isEnabled ? 'enabled' : 'disabled' }))
 }
 catch (error) { templateError.value = error?.msg || error?.message || '模板加载失败，请重试' }
 finally { loading.value = false }
}
async function loadModels() {
 if (!checkPermi(['ai:model:query'])) return
 modelError.value = ''
 try { const res = await listModelAll(); models.value = res.data?.rows || res.data || [] }
 catch (error) { models.value = []; modelError.value = error?.msg || error?.message || '模型列表加载失败；可稍后配置模型' }
}
function templatePayload(item = form) {
 return { name: item.name.trim(), purpose: item.purpose, reportType: item.purpose === 'research' ? item.reportType || null : null, prompt: item.prompt.trim(), description: item.description, modelId: item.modelId || null, imageModelId: item.imageModelId || null, sections: item.sections, imageConfig: item.imageConfig, isEnabled: item.isEnabled }
}
async function saveTemplate() {
 if (!canSaveTemplate.value || saving.value) return
 if (!form.name.trim() || !form.prompt.trim()) return ElMessage.warning('请填写模板名称和正文生成提示词')
 if (form.purpose === 'research' && !form.reportType) return ElMessage.warning('请选择模板所属的报告类型')
 saving.value = true
 try {
  if (editingTemplate.value) await updatePipelineTemplate(editingTemplate.value.id, templatePayload())
  else await createPipelineTemplate(templatePayload())
  editorVisible.value = false; ElMessage.success('模板内容及报告类型已保存'); await loadTemplates()
 } catch (error) { ElMessage.error(error?.msg || error?.message || '模板保存失败') }
 finally { saving.value = false }
}
async function toggleTemplate(item) {
 if (!canSaveTemplate.value || saving.value) return
 saving.value = true
 try {
  if (item.isEnabled) await retirePipelineTemplate(item.id)
  else await updatePipelineTemplate(item.id, templatePayload({ ...item, isEnabled: true }))
  ElMessage.success(item.isEnabled ? '模板已停用' : '模板已启用'); await loadTemplates()
 }
 catch (error) { ElMessage.error(error?.msg || error?.message || '模板状态保存失败') }
 finally { saving.value = false }
}
onMounted(() => { loadTemplates(); loadModels() })
</script>
<style scoped>
.template-contract-note { margin-bottom: 14px; }
.template-form-grid :deep(.el-select) { width: 100%; }
.template-toolbar {
 display: flex; align-items: center; gap: 10px; padding: 12px 16px;
 background: var(--el-bg-color); border: 1px solid var(--el-border-color-light); border-radius: 8px;
}
.template-toolbar .el-input { flex: 1; min-width: 180px; }
.template-toolbar .el-select { width: 140px; flex-shrink: 0; }
.template-toolbar .el-button { margin: 0; }
.template-categories { overflow-x: auto; padding: 0 0 2px; }
.template-categories :deep(.el-segmented__item-label) { display: flex; align-items: center; gap: 8px; }
.template-category-count { font-size: 12px; opacity: .8; font-variant-numeric: tabular-nums; }
.template-results { min-width: 0; }
.template-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.template-card {
 min-width: 0; display: flex; flex-direction: column; padding: 20px;
 border: 1px solid var(--el-border-color-light); border-radius: 8px; background: var(--el-bg-color);
}
.template-card-head { display: flex; align-items: center; gap: 10px; }
.template-document-icon { display: flex; padding: 9px; border-radius: 6px; background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-size: 20px; }
.template-card h3 { flex: 1; min-width: 0; margin: 0; color: var(--el-text-color-primary); font-size: 16px; line-height: 1.5; overflow-wrap: anywhere; }
.template-description { margin: 14px 0; color: var(--el-text-color-regular); font-size: 14px; line-height: 1.7; overflow-wrap: anywhere; }
.template-metadata { display: grid; gap: 10px; margin: auto 0 16px; font-size: 13px; }
.template-metadata > div { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 12px; }
.template-metadata dt { color: var(--el-text-color-secondary); }
.template-metadata dd { margin: 0; color: var(--el-text-color-regular); overflow-wrap: anywhere; }
.template-card-actions { display: flex; flex-wrap: wrap; gap: 8px; padding-top: 14px; border-top: 1px solid var(--el-border-color-lighter); }
.template-card-actions .el-button { margin: 0; }
.template-result-count { color: var(--el-text-color-secondary); font-size: 13px; padding: 10px 16px; background: var(--el-bg-color); border: 1px solid var(--el-border-color-light); border-radius: 8px; }
.template-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; }.template-form-grid .is-full { grid-column: 1/-1; }.template-section-row { min-height: 52px; display: grid; grid-template-columns: 18px 24px minmax(0, 1fr) 120px 76px 28px; gap: 8px; align-items: center; }.template-section-row > svg { width: 14px; color: #94a3b8; }.template-section-row > button { border: 0; background: transparent; color: #94a3b8; cursor: pointer; }.template-section-row > button svg { width: 15px; }.template-add-section { width: 100%; margin-top: 10px; }
.template-section-row > .el-input-number { width: 100%; }
:deep(.el-drawer) { max-width: 100vw; }
@media (max-width: 540px) {
 .template-section-row { grid-template-columns: 18px 24px minmax(0, 1fr) 28px; padding: 8px 0; }
 .template-section-row > .el-input-number { grid-column: 3; grid-row: 2; max-width: 140px; }
 .template-section-row > .el-switch { grid-column: 3; grid-row: 3; }
 .template-section-row > button { grid-column: 4; grid-row: 1; }
}
.preview-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; color: #64748b; font-size: 13px; }.preview-description { margin: 18px 0; color: #475569; line-height: 1.7; }.preview-sections { border-top: 1px solid #e2e8f0; }.preview-section { min-height: 58px; padding: 10px 0; border-bottom: 1px solid #edf1f6; display: flex; align-items: center; gap: 12px; }.preview-section > span { width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; background: #edf3ff; color: #409eff; font-size: 13px; font-weight: 700; }.preview-section div { display: flex; flex-direction: column; gap: 4px; }.preview-section small { color: #64748b; font-size: 13px; }
@media (max-width: 1200px) { .template-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) {
 .template-grid, .template-form-grid { grid-template-columns: minmax(0, 1fr); }
 .template-toolbar { flex-wrap: wrap; padding: 12px; }
 .template-toolbar .el-input { flex: 1 1 100%; min-width: 0; }
 .template-toolbar .el-select { flex: 1; min-width: 100px; }
 .template-card { padding: 16px; }
}
</style>
