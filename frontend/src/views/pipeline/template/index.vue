<template>
  <div class="app-container pipeline-page pipeline-template-page ws-list-page">
    <div class="pipeline-page-head"><div><h1>模板管理</h1></div><div class="pipeline-head-actions"><el-button v-if="canSaveTemplate" type="primary" :icon="Plus" @click="createTemplate">新建模板</el-button></div></div>
    <el-alert v-if="templateError" type="warning" show-icon :closable="false" class="template-load-error">
      <template #title>{{ templateError }}</template>
      <template #default><el-button class="ps-ui-action template-retry" @click="loadTemplates">重新加载</el-button></template>
    </el-alert>
    <div v-else class="template-layout ws-split-layout">
      <aside class="template-categories"><button v-for="category in categories" :key="category.name" type="button" :class="{ 'is-active': activeCategory === category.value }" @click="activeCategory = category.value"><component :is="category.icon" /><span>{{ category.name }}</span><b>{{ countCategory(category.value) }}</b></button></aside>
      <main v-loading="loading"><div class="template-toolbar"><el-input v-model="keyword" :prefix-icon="Search" clearable placeholder="搜索模板名称或用途" /><el-select v-model="status"><el-option label="全部状态" value="all" /><el-option label="已启用" value="enabled" /><el-option label="已停用" value="disabled" /></el-select></div><div class="template-grid ws-card-grid"><article v-for="item in filteredTemplates" :key="item.id"><div class="template-preview" :style="{ '--template-color': item.color }"><span>{{ item.purpose }}</span><div><i></i><i></i><i></i><i></i></div><b>{{ purposeLabel(item.purpose) }}</b></div><div class="template-body"><div><el-tag :type="statusTag(item.status)" size="small" effect="plain">{{ statusLabel(item.status) }}</el-tag><small>{{ item.modelId ? '已选择模型' : '模型未配置' }}</small></div><h3>{{ item.name }}</h3><p>{{ item.description }}</p><dl><div><dt>最近更新</dt><dd>{{ item.updatedAt }}</dd></div><div><dt>使用次数</dt><dd>{{ item.usage ?? '—' }}</dd></div></dl><footer><el-button v-if="canSaveTemplate" plain type="primary" @click="editTemplate(item)">编辑</el-button><el-button plain @click="previewTemplate(item)">预览</el-button><el-button v-if="canSaveTemplate" plain @click="toggleTemplate(item)">{{ item.isEnabled ? '停用' : '启用' }}</el-button></footer></div></article></div></main>
    </div>
    <el-drawer v-model="editorVisible" :title="editingTemplate?.id ? '编辑模板' : '新建模板'" size="640px"><el-form label-position="top" :model="form"><div class="template-form-grid"><el-form-item label="模板名称"><el-input v-model="form.name" /></el-form-item><el-form-item label="模板类型"><el-select v-model="form.purpose"><el-option label="科研报告" value="research" /><el-option label="日报周月报" value="digest" /><el-option label="文章" value="article" /></el-select></el-form-item><el-form-item label="模板说明" class="is-full"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item></div>
 <el-form-item label="正文生成提示词" required><el-input v-model="form.prompt" type="textarea" :rows="6" /></el-form-item>
 <el-alert v-if="modelError" :title="modelError" type="warning" :closable="false"><template #default><el-button plain @click="loadModels">重新加载模型</el-button></template></el-alert>
 <el-form-item label="文本生成模型"><el-select v-model="form.modelId" clearable placeholder="可稍后由管理员配置"><el-option v-for="model in textModels" :key="model.modelId" :label="model.modelName || model.modelCode" :value="model.modelId" /></el-select></el-form-item>
 <el-form-item label="启用配图"><el-switch v-model="form.imageConfig.enabled" /></el-form-item>
 <el-form-item label="图片生成模型"><el-select v-model="form.imageModelId" clearable placeholder="仅显示具备图片生成能力的模型"><el-option v-for="model in imageModels" :key="model.modelId" :label="model.modelName || model.modelCode" :value="model.modelId" /></el-select></el-form-item>
 <el-form-item v-if="form.imageConfig.enabled" label="配图数量"><el-input-number v-model="form.imageConfig.count" :min="1" :max="10" /></el-form-item>
 <el-form-item v-if="form.imageConfig.enabled" label="图片生成提示词"><el-input v-model="form.imageConfig.prompt" type="textarea" :rows="3" placeholder="留空时由后台使用报告标题" /></el-form-item>
 <el-form-item label="启用模板"><el-switch v-model="form.isEnabled" /></el-form-item>
 <h3>章节结构</h3><div v-for="(section, index) in form.sections" :key="section.id" class="template-section-row"><Rank /><span>{{ index + 1 }}</span><el-input v-model="section.title" /><el-input-number v-model="section.words" :min="100" :max="8000" :step="100" /><el-switch v-model="section.required" active-text="必填" /><el-button class="ps-ui-action" @click="form.sections.splice(index, 1)" aria-label="删除章节"><Delete /></el-button></div><el-button v-if="canSaveTemplate" class="template-add-section" @click="form.sections.push({ id: Date.now(), title: '新增章节', words: 1000, required: false })"><Plus />新增章节</el-button></el-form><template #footer><el-button @click="editorVisible = false">取消</el-button><el-button v-if="canSaveTemplate" type="primary" :loading="saving" @click="saveTemplate">保存模板</el-button></template></el-drawer>
    <el-dialog v-model="previewVisible" :title="previewingTemplate?.name || '模板预览'" width="720px"><div v-if="previewingTemplate" class="template-preview-dialog"><div class="preview-meta"><el-tag :type="statusTag(previewingTemplate.status)" effect="plain">{{ statusLabel(previewingTemplate.status) }}</el-tag><span>{{ purposeLabel(previewingTemplate.purpose) }}</span></div><p class="preview-description">{{ previewingTemplate.description || '暂无模板说明' }}</p><div v-if="previewingTemplate.sections?.length" class="preview-sections"><div v-for="(section, index) in previewingTemplate.sections" :key="section.id || index" class="preview-section"><span>{{ index + 1 }}</span><div><strong>{{ section.title || '未命名章节' }}</strong><small>{{ section.required ? '必填' : '选填' }} · {{ section.words || '—' }} 字</small></div></div></div><el-empty v-else description="当前模板尚未配置章节结构" :image-size="72" /></div></el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Calendar, Collection, Delete, Document, Files, Plus, Rank, Search } from '@element-plus/icons-vue'
import { createPipelineTemplate, listPipelineTemplates, retirePipelineTemplate, updatePipelineTemplate } from '@/api/pipeline/intelligence'
import { listModelAll } from '@/api/ai/model'
import { modelsFor } from '@/utils/pipeline/compactContract'
import { checkPermi } from '@/utils/permission'
const activeCategory = ref('all'), keyword = ref(''), status = ref('all')
const editorVisible = ref(false), previewVisible = ref(false), previewingTemplate = ref(null), editingTemplate = ref(null)
const saving = ref(false), loading = ref(false), templateError = ref('')
const canSaveTemplate = computed(() => checkPermi(['pipeline:template:save']))
const categories = [{ name: '全部模板', value: 'all', icon: Files }, { name: '科研报告', value: 'research', icon: Document }, { name: '日报周月报', value: 'digest', icon: Calendar }, { name: '文章', value: 'article', icon: Collection }]
const templates = ref([]), models = ref([]), modelError = ref('')
const textModels = computed(() => modelsFor(models.value, 'text_generate'))
const imageModels = computed(() => modelsFor(models.value, 'image_generate'))
const form = reactive({ name: '', purpose: 'research', prompt: '', description: '', modelId: null, imageModelId: null, sections: [], imageConfig: { enabled: false }, isEnabled: true })
const filteredTemplates = computed(() => templates.value.filter(item => (activeCategory.value === 'all' || item.purpose === activeCategory.value) && (status.value === 'all' || item.status === status.value) && (!keyword.value || `${item.name}${item.description}`.includes(keyword.value))))
function countCategory(value) { return value === 'all' ? templates.value.length : templates.value.filter(item => item.purpose === value).length }
function statusTag(value) { return value === 'enabled' ? 'success' : 'info' }
function statusLabel(value) { return value === 'enabled' ? '已启用' : '已停用' }
function purposeLabel(value) { return ({ article: '文章', research: '科研报告', digest: '简报' })[value] || value }
function resetForm(item = null) {
 Object.assign(form, { name: item?.name || '', purpose: item?.purpose || 'research', prompt: item?.prompt || '', description: item?.description || '', modelId: item?.modelId ?? null, imageModelId: item?.imageModelId ?? null, sections: (item?.sections || []).map(section => ({ ...section })), imageConfig: item ? JSON.parse(JSON.stringify(item.imageConfig || {})) : {}, isEnabled: item?.isEnabled ?? true })
 form.imageConfig.enabled ??= false
 form.imageConfig.count ??= 1
 form.imageConfig.prompt ??= ''
}
function createTemplate() { if (!canSaveTemplate.value) return; editingTemplate.value = null; resetForm(); editorVisible.value = true }
function editTemplate(item) { if (!canSaveTemplate.value) return; editingTemplate.value = item; resetForm(item); editorVisible.value = true }
function previewTemplate(item) { previewingTemplate.value = item; previewVisible.value = true }
async function loadTemplates() {
 loading.value = true; templateError.value = ''
 try { const res = await listPipelineTemplates(); templates.value = (res.data?.rows || []).map(item => ({ ...item, status: item.isEnabled ? 'enabled' : 'disabled' })) }
 catch (error) { templateError.value = error?.msg || error?.message || '模板加载失败，请重试' }
 finally { loading.value = false }
}
async function loadModels() {
 modelError.value = ''
 try { const res = await listModelAll(); models.value = res.data?.rows || res.data || [] }
 catch (error) { models.value = []; modelError.value = error?.msg || error?.message || '模型列表加载失败；可稍后配置模型' }
}
function templatePayload(item = form) {
 return { name: item.name.trim(), purpose: item.purpose, prompt: item.prompt.trim(), description: item.description, modelId: item.modelId || null, imageModelId: item.imageModelId || null, sections: item.sections, imageConfig: item.imageConfig, isEnabled: item.isEnabled }
}
async function saveTemplate() {
 if (!canSaveTemplate.value || saving.value) return
 if (!form.name.trim() || !form.prompt.trim()) return ElMessage.warning('请填写模板名称和正文生成提示词')
 saving.value = true
 try {
  if (editingTemplate.value) await updatePipelineTemplate(editingTemplate.value.id, templatePayload())
  else await createPipelineTemplate(templatePayload())
  editorVisible.value = false; ElMessage.success('模板已保存'); await loadTemplates()
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
.template-layout { display: grid; grid-template-columns: 210px minmax(0,1fr); gap: 18px; }.template-categories { padding: 10px; border: 1px solid #e2e8f0; border-radius: 10px; align-self: start; background: #fff; }.template-categories button { width: 100%; min-height: 44px; padding: 0 11px; border: 0; border-radius: 7px; display: grid; grid-template-columns: 18px 1fr auto; gap: 9px; align-items: center; background: transparent; color: #475569; cursor: pointer; text-align: left; }.template-categories button.is-active { background: #edf3ff; color: #2764e7; }.template-categories svg { width: 16px; }.template-categories b { font-size: 13px; }
.template-load-error { margin-bottom: 18px; }.template-retry { padding: 0; border: 0; background: transparent; color: #2764e7; cursor: pointer; font-size: 13px; }
.template-toolbar { margin-bottom: 14px; display: grid; grid-template-columns: minmax(260px,1fr) 140px; gap: 10px; }.template-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 15px; }.template-grid article { border: 1px solid #e2e8f0; border-radius: 11px; overflow: hidden; background: #fff; }.template-preview { height: 145px; padding: 18px; position: relative; background: linear-gradient(145deg, color-mix(in srgb,var(--template-color),#fff 88%),#f8fafc); }.template-preview > span { color: var(--template-color); font-size: 13px; font-weight: 800; }.template-preview > div { width: 110px; margin: 18px auto 0; padding: 16px; border-top: 4px solid var(--template-color); background: #fff; box-shadow: 0 5px 15px rgba(15,23,42,.1); }.template-preview i { height: 3px; margin-bottom: 7px; display: block; background: #dbe3ed; }.template-preview i:nth-child(2){width:78%}.template-preview i:nth-child(3){width:90%}.template-preview i:nth-child(4){width:60%}.template-preview > b { position: absolute; right: 14px; bottom: 12px; color: #64748b; font-size: 13px; }.template-body { padding: 17px; }.template-body > div { display: flex; justify-content: space-between; }.template-body small { color: #64748b; }.template-body h3 { margin: 13px 0 7px; font-size: 15px; }.template-body p { height: 38px; margin: 0; overflow: hidden; color: #64748b; font-size: 13px; line-height: 1.7; }.template-body dl { margin: 14px 0; }.template-body dl div { padding: 4px 0; display: flex; justify-content: space-between; color: #64748b; font-size: 13px; }.template-body dd { margin: 0; color: #334155; }.template-body footer { padding-top: 10px; border-top: 1px solid #edf1f6; display: flex; align-items: center; }
.template-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; }.template-form-grid .is-full { grid-column: 1/-1; }.template-section-row { min-height: 52px; display: grid; grid-template-columns: 18px 24px minmax(0, 1fr) 120px 76px 28px; gap: 8px; align-items: center; }.template-section-row > svg { width: 14px; color: #94a3b8; }.template-section-row > button { border: 0; background: transparent; color: #94a3b8; cursor: pointer; }.template-section-row > button svg { width: 15px; }.template-add-section { width: 100%; margin-top: 10px; }
.template-section-row > .el-input-number { width: 100%; }
:deep(.el-drawer) { max-width: 100vw; }
@media (max-width: 540px) {
 .template-section-row { grid-template-columns: 18px 24px minmax(0, 1fr) 28px; padding: 8px 0; }
 .template-section-row > .el-input-number { grid-column: 3; grid-row: 2; max-width: 140px; }
 .template-section-row > .el-switch { grid-column: 3; grid-row: 3; }
 .template-section-row > button { grid-column: 4; grid-row: 1; }
}
.preview-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; color: #64748b; font-size: 13px; }.preview-description { margin: 18px 0; color: #475569; line-height: 1.7; }.preview-sections { border-top: 1px solid #e2e8f0; }.preview-section { min-height: 58px; padding: 10px 0; border-bottom: 1px solid #edf1f6; display: flex; align-items: center; gap: 12px; }.preview-section > span { width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; background: #edf3ff; color: #2764e7; font-size: 13px; font-weight: 700; }.preview-section div { display: flex; flex-direction: column; gap: 4px; }.preview-section small { color: #64748b; font-size: 13px; }
@media (max-width: 1100px){.template-grid{grid-template-columns:repeat(2,1fr)}}@media (max-width:760px){.template-layout{grid-template-columns:1fr}.template-categories{display:grid;grid-template-columns:repeat(2,1fr)}.template-grid{grid-template-columns:1fr}.template-toolbar,.template-form-grid{grid-template-columns:1fr}}
</style>
