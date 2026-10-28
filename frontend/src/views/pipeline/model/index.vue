<template>
 <div class="app-container pipeline-page pipeline-model-page">
  <div class="pipeline-page-head"><div><h1>模型与类别提示词</h1></div><el-button v-if="canModelAdd" type="primary" :icon="Plus" @click="openModelDialog">添加模型</el-button></div>
  <el-tabs v-model="activeTab" class="model-tabs">
      <el-tab-pane v-if="canModelQuery" label="模型配置" name="models"><div v-if="modelLoading" class="model-empty">正在读取 PostgreSQL 模型配置…</div><div v-else-if="modelError" class="model-empty model-error">{{ modelError }}<el-button class="ps-ui-action" @click="loadModels">重新加载</el-button></div><div v-else-if="!models.length" class="model-empty">当前没有模型配置，请先添加模型；不会展示演示用的虚拟模型。</div><div v-else class="model-grid ws-card-grid"><article v-for="model in models" :key="model.modelId"><header><span class="model-logo" :style="{ background: modelColor(model) }">{{ modelShort(model) }}</span><div><strong>{{ model.modelName || model.modelCode }}</strong><small>{{ model.provider }} · {{ modelCapabilities(model).join('、') || '未配置能力' }}</small></div><el-switch v-if="canModelEdit" :model-value="model.status === '0'" @change="toggleModel(model, $event)" /></header><dl><div><dt>模型编码</dt><dd>{{ model.modelCode }}</dd></div><div><dt>接口地址</dt><dd>{{ model.baseUrl || '未配置' }}</dd></div><div><dt>上下文上限</dt><dd>{{ model.maxTokens || '未配置' }}</dd></div><div><dt>温度参数</dt><dd>{{ model.temperature ?? '未配置' }}</dd></div></dl><footer><span :class="{ 'is-error': !model.baseUrl || !model.modelCode || model.status !== '0' }"><i></i>{{ model.status !== '0' ? '已停用' : model.baseUrl && model.modelCode ? '已配置' : '配置不完整' }}</span><div><el-button v-if="canModelEdit" plain type="primary" @click="editModel(model)">配置</el-button></div></footer></article></div></el-tab-pane>

   <el-tab-pane v-if="canCategoryList" label="类别提示词" name="categories">
    <div class="prompt-toolbar"><span>管理员维护类别、提示词和模型</span><el-button v-if="canCategorySave" type="primary" :icon="Plus" @click="openCategory()">新增类别</el-button></div>
    <el-alert v-if="categoryError" :title="categoryError" type="warning" :closable="false"><template #default><el-button plain @click="loadCategories">重新加载</el-button></template></el-alert>
    <el-table v-else v-loading="categoryLoading" :data="categories">
     <el-table-column prop="name" label="类别" min-width="140" /><el-table-column prop="prompt" label="分类提示词" min-width="240" show-overflow-tooltip />
     <el-table-column prop="appliesTo" label="适用内容" width="110"><template #default="{ row }">{{ ({ all: '全部', news: '新闻资讯', paper: '论文' })[row.appliesTo] || row.appliesTo || '—' }}</template></el-table-column>
     <el-table-column label="模型" min-width="140"><template #default="{ row }">{{ models.find(model => model.modelId === row.modelId)?.modelName || (row.modelId ? '已选择模型' : '未配置') }}</template></el-table-column>
     <el-table-column label="状态" width="100"><template #default="{ row }">{{ row.isEnabled ? '启用' : '停用' }}</template></el-table-column>
     <el-table-column label="操作" width="180"><template #default="{ row }"><el-button v-if="canCategorySave" plain type="primary" @click="openCategory(row)">编辑</el-button><el-button v-if="canCategoryDelete" plain type="danger" @click="removeCategory(row)">删除</el-button></template></el-table-column>
    </el-table>
   </el-tab-pane>
  </el-tabs>
    <el-dialog v-model="modelDialogVisible" :title="editingModel ? '配置模型' : '添加模型'" width="620px"><el-form label-position="top"><div class="model-form-grid"><el-form-item label="模型名称"><el-input v-model="modelForm.name" /></el-form-item><el-form-item label="服务商"><el-select v-model="modelForm.provider" filterable placeholder="请选择已支持的服务商" style="width:100%"><el-option v-for="provider in providers" :key="provider.value" :label="provider.label" :value="provider.value" /></el-select></el-form-item><el-form-item label="接口地址（其他服务商请选 compatible 并填写兼容端点）" class="is-full"><el-input v-model="modelForm.endpoint" /></el-form-item><el-form-item label="模型编码"><el-input v-model="modelForm.modelId" placeholder="例如 deepseek-chat" /></el-form-item><el-form-item label="能力" class="is-full"><el-checkbox-group v-model="modelForm.capabilities"><el-checkbox value="text_generate">文本生成</el-checkbox><el-checkbox value="image_generate">图片生成</el-checkbox><el-checkbox value="image_input">图片输入</el-checkbox><el-checkbox value="reasoning">推理</el-checkbox></el-checkbox-group></el-form-item><el-form-item label="最大输出 Token"><el-input-number v-model="modelForm.maxTokens" :min="1" :controls="false" style="width: 100%" /></el-form-item><el-form-item label="温度参数"><el-input-number v-model="modelForm.temperature" :min="0" :max="2" :step="0.1" :controls="false" style="width: 100%" /></el-form-item><el-form-item label="API 密钥" class="is-full"><el-input v-model="modelForm.apiKey" type="password" show-password placeholder="密钥仅加密保存，不会在页面回显；留空表示不修改" /></el-form-item></div></el-form><template #footer><el-button @click="modelDialogVisible = false">取消</el-button><el-button v-if="canModelSave" type="primary" @click="saveModel" :loading="modelSaving">保存配置</el-button></template></el-dialog>

  <el-dialog v-model="categoryDialogVisible" title="类别与分类提示词" width="min(680px, calc(100vw - 32px))" class="category-config-dialog" destroy-on-close>
   <el-form label-position="top" class="category-config-form">
    <div class="category-basic-grid">
      <el-form-item label="类别名称"><el-input v-model="categoryForm.name" placeholder="例如：管网安全" /></el-form-item>
      <el-form-item label="适用内容"><el-select v-model="categoryForm.appliesTo"><el-option label="全部" value="all" /><el-option label="新闻资讯" value="news" /><el-option label="论文" value="paper" /></el-select></el-form-item>
    </div>
    <el-form-item label="分类提示词"><el-input v-model="categoryForm.prompt" type="textarea" :autosize="{ minRows: 5, maxRows: 10 }" resize="vertical" placeholder="描述该类别关注的内容、判断条件及需要排除的内容" /></el-form-item>
    <el-form-item label="文本生成模型"><el-select v-model="categoryForm.modelId" clearable placeholder="请选择用于分类的文本模型"><el-option v-for="model in textModels" :key="model.modelId" :label="model.modelName || model.modelCode" :value="model.modelId" /></el-select></el-form-item>
    <el-alert v-if="modelError" :title="modelError" type="warning" :closable="false"><template #default><el-button plain @click="loadModels">重新加载模型</el-button></template></el-alert>
    <div class="category-options-row">
      <el-form-item label="排序"><el-input-number v-model="categoryForm.sortOrder" :min="0" controls-position="right" /></el-form-item>
      <el-form-item label="启用类别"><el-switch v-model="categoryForm.isEnabled" /></el-form-item>
    </div>
   </el-form>
   <template #footer><el-button @click="categoryDialogVisible = false">取消</el-button><el-button type="primary" :loading="categorySaving" @click="saveCategory">保存</el-button></template>
  </el-dialog>
 </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { addModel, listModelAll, updateModel } from '@/api/ai/model'
import { listPipelineCategories, createPipelineCategory, updatePipelineCategory, deletePipelineCategory } from '@/api/pipeline/categories'
import { categoryPayload, modelCapabilities, modelsFor } from '@/utils/pipeline/compactContract'
import { checkPermi, checkRole } from '@/utils/permission'
const providers = [{ value: 'openai', label: 'OpenAI' }, { value: 'openai-compatible', label: 'OpenAI 兼容' }, { value: 'compatible', label: '其他服务商的兼容端点' }, { value: 'deepseek', label: 'DeepSeek' }]
const activeTab = ref('models')
const models = ref([]), modelLoading = ref(false), modelError = ref(''), modelSaving = ref(false)
const modelDialogVisible = ref(false), editingModel = ref(null)
const canModelQuery = computed(() => checkPermi(['ai:model:query']))
const canModelAdd = computed(() => checkPermi(['ai:model:add']))
const canModelEdit = computed(() => checkPermi(['ai:model:edit']))
const canModelSave = computed(() => editingModel.value ? canModelEdit.value : canModelAdd.value)
const canCategoryList = computed(() => checkRole(['admin']))
const canCategorySave = computed(() => checkRole(['admin']))
const canCategoryDelete = computed(() => checkRole(['admin']))
const modelForm = reactive({ modelId: '', name: '', provider: '', endpoint: '', capabilities: [], maxTokens: null, temperature: 0.2, apiKey: '' })
function openModelDialog() { if (!canModelAdd.value) return; editingModel.value = null; Object.assign(modelForm, { modelId: '', name: '', provider: '', endpoint: '', capabilities: [], maxTokens: null, temperature: 0.2, apiKey: '' }); modelDialogVisible.value = true }
function editModel(model) { if (!canModelEdit.value) return; editingModel.value = model; Object.assign(modelForm, { modelId: model.modelCode, name: model.modelName || '', provider: model.provider || '', endpoint: model.baseUrl || '', capabilities: [...modelCapabilities(model)], maxTokens: model.maxTokens, temperature: model.temperature ?? 0.2, apiKey: '' }); modelDialogVisible.value = true }
function modelShort(model) { return (model.modelCode || 'AI').slice(0, 3).toUpperCase() }
function modelColor(model) { return ['#2764e7', '#0b8f87', '#7357c8', '#c26a2e'][(String(model.modelId || '0').charCodeAt(String(model.modelId || '0').length - 1) % 4)] }
async function loadModels() { if (!canModelQuery.value) return; modelLoading.value = true; modelError.value = ''; try { const res = await listModelAll(); models.value = res.data?.rows || res.data || [] } catch (error) { models.value = []; modelError.value = error?.msg || error?.message || '模型配置暂时无法加载，请检查服务后重试'; ElMessage.warning(modelError.value) } finally { modelLoading.value = false } }
async function saveModel() { if (!canModelSave.value) return; if (!modelForm.name || !modelForm.modelId || !modelForm.provider || !modelForm.endpoint || !modelForm.capabilities.length) { ElMessage.warning('请填写名称、编码、服务商、地址并选择能力'); return } modelSaving.value = true; try { const payload = { modelId: editingModel.value?.modelId, modelCode: modelForm.modelId, modelName: modelForm.name, provider: modelForm.provider, baseUrl: modelForm.endpoint, capabilities: [...modelForm.capabilities], parameters: { ...(editingModel.value?.parameters || {}), ...(modelForm.maxTokens ? { max_tokens: modelForm.maxTokens } : {}), temperature: modelForm.temperature }, maxTokens: modelForm.maxTokens, temperature: modelForm.temperature, status: editingModel.value?.status || '0', ...(modelForm.apiKey ? { apiKey: modelForm.apiKey } : {}) }; if (editingModel.value) await updateModel(payload); else await addModel(payload); modelDialogVisible.value = false; ElMessage.success('模型配置已保存'); await loadModels() } catch (error) { ElMessage.error(error?.msg || error?.message || '模型配置保存失败') } finally { modelSaving.value = false } }
async function toggleModel(model, enabled) { if (!canModelEdit.value) return; const previous = model.status; model.status = enabled ? '0' : '1'; try { await updateModel({ modelId: model.modelId, status: model.status }); ElMessage.success(`模型已${enabled ? '启用' : '停用'}`) } catch (error) { model.status = previous; ElMessage.error(error?.msg || error?.message || '模型状态更新失败') } }

const categories = ref([]), categoryLoading = ref(false), categoryError = ref('')
const categoryDialogVisible = ref(false), categorySaving = ref(false), editingCategory = ref(null)
const categoryForm = reactive({ name: '', prompt: '', modelId: null, appliesTo: 'all', sortOrder: 0, isEnabled: false })
const textModels = computed(() => modelsFor(models.value, 'text_generate'))
function openCategory(item = null) {
 if (!canCategorySave.value) return
 editingCategory.value = item
 Object.assign(categoryForm, { name: item?.name || '', prompt: item?.prompt || '', modelId: item?.modelId ?? null, appliesTo: item?.appliesTo || 'all', sortOrder: item?.sortOrder ?? 0, isEnabled: item?.isEnabled ?? false })
 categoryDialogVisible.value = true
}
async function loadCategories() {
 if (!canCategoryList.value) return
 categoryLoading.value = true; categoryError.value = ''
 try { const res = await listPipelineCategories(); categories.value = res.data?.rows || [] }
 catch (error) { categoryError.value = error?.msg || error?.message || '类别列表加载失败，请重试' }
 finally { categoryLoading.value = false }
}
async function saveCategory() {
 if (!canCategorySave.value || categorySaving.value) return
 categorySaving.value = true
 try {
  const data = categoryPayload(categoryForm)
  if (editingCategory.value) await updatePipelineCategory(editingCategory.value.id, data)
  else await createPipelineCategory(data)
  categoryDialogVisible.value = false; ElMessage.success('类别已保存'); await loadCategories()
 } catch (error) { ElMessage.error(error?.msg || error?.message || '类别保存失败') }
 finally { categorySaving.value = false }
}
async function removeCategory(item) {
 if (!canCategoryDelete.value) return
 try {
  await ElMessageBox.confirm('删除类别？已被内容引用的类别不能删除，可编辑为停用。', '删除类别')
  await deletePipelineCategory(item.id); ElMessage.success('类别已删除'); await loadCategories()
 } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.msg || error?.message || '类别删除失败') }
}
onMounted(() => { if (!canModelQuery.value && canCategoryList.value) activeTab.value = 'categories'; if (canModelQuery.value) loadModels(); if (canCategoryList.value) loadCategories() })
</script>
<style scoped>
.category-config-form :deep(.el-form-item) { margin-bottom: 16px; }
.category-config-form :deep(.el-select) { width: 100%; }
.category-basic-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; }
.category-options-row { display: flex; align-items: flex-start; gap: 32px; padding-top: 14px; border-top: 1px solid #e2e8f0; }
.category-options-row :deep(.el-form-item) { margin-bottom: 0; }
.category-config-form :deep(.el-textarea__inner) { line-height: 1.65; }
.category-config-form :deep(.el-input__inner:focus-visible),
.category-config-form :deep(.el-textarea__inner:focus-visible) { outline: none; }
.category-config-form :deep(.el-input__wrapper.is-focus),
.category-config-form :deep(.el-select__wrapper.is-focused) { box-shadow: 0 0 0 1px #7da6c0 inset, 0 0 0 2px #00548710; }
.category-config-form :deep(.el-textarea__inner:focus) { box-shadow: 0 0 0 1px #7da6c0 inset, 0 0 0 2px #00548710; }
@media (max-width: 520px) { .category-basic-grid { grid-template-columns: minmax(0, 1fr); gap: 0; } .category-options-row { gap: 24px; flex-wrap: wrap; } }
/* Number inputs use the rounded wrapper as their single focus indicator. */
.model-form-grid :deep(.el-input-number .el-input__inner:focus),
.model-form-grid :deep(.el-input-number .el-input__inner:focus-visible) { outline: none; box-shadow: none; }
.model-form-grid :deep(.el-input-number .el-input__wrapper.is-focus) { box-shadow: 0 0 0 1px #7da6c0 inset, 0 0 0 2px #00548710; }
.model-overview { margin-bottom: 18px; display: grid; grid-template-columns: repeat(4,1fr); gap: 14px; }.model-overview article { padding: 20px; border: 1px solid #e2e8f0; border-radius: 10px; display: flex; flex-direction: column; background: #fff; }.model-overview span,.model-overview small { color: #64748b; font-size: 13px; }.model-overview strong { margin: 8px 0 4px; color: #0f172a; font-size: 27px; }.model-overview small.is-success { color: #14845d; }
.model-empty { padding: 48px 20px; color: #64748b; text-align: center; }.model-error { color: #b45309; }.model-empty button,.retry-link { margin-left: 10px; padding: 0; border: 0; background: transparent; color: #2764e7; cursor: pointer; }.retry-link { margin-left: 0; text-decoration: underline; }
.route-readiness-alert { margin-top: 12px; }.route-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 14px; }.route-grid article { padding: 18px; border: 1px solid #e2e8f0; border-radius: 9px; }.route-grid header,.route-grid footer { display: flex; align-items: center; justify-content: space-between; gap: 10px; }.route-grid header div { display: flex; flex-direction: column; }.route-grid header small { margin-top: 4px; color: #64748b; font-size: 13px; }.route-form { margin-top: 16px; }.route-number-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 10px; }.route-grid footer { padding-top: 4px; border-top: 1px solid #edf1f6; }.route-grid footer small { color: #64748b; font-size: 13px; }
.prompt-connect-note { margin-bottom: 12px; }.test-state { display: block; margin-top: 4px; color: #64748b; font-size: 13px; }.test-state.is-passed { color: #14845d; }.test-state.is-failed { color: #c2410c; }
.audit-toolbar { margin: 16px 0 12px; display: flex; flex-wrap: wrap; gap: 10px; }.audit-model { display: flex; flex-direction: column; gap: 3px; }.audit-model small { color: #64748b; font-size: 13px; }.audit-pagination { padding-top: 14px; display: flex; justify-content: space-between; align-items: center; color: #64748b; font-size: 13px; }
.model-tabs { padding: 0 20px 20px; border: 1px solid #e2e8f0; border-radius: 10px; background: #fff; }.model-grid { display: grid; grid-template-columns: repeat(2,1fr); gap: 14px; }.model-grid article { padding: 20px; border: 1px solid #e2e8f0; border-radius: 9px; }.model-grid header { display: grid; grid-template-columns: 42px 1fr auto; gap: 11px; align-items: center; }.model-logo { width: 42px; height: 42px; border-radius: 10px; display: grid; place-items: center; color: #fff; font-size: 13px; font-weight: 800; }.model-grid header > div { display: flex; flex-direction: column; }.model-grid header small { margin-top: 3px; color: #64748b; font-size: 13px; }.model-grid dl { margin: 16px 0; }.model-grid dl div { padding: 6px 0; border-bottom: 1px solid #edf1f6; display: flex; justify-content: space-between; font-size: 13px; }.model-grid dt { color: #64748b; }.model-grid dd { margin: 0; color: #334155; }.model-grid footer { display: flex; align-items: center; justify-content: space-between; }.model-grid footer > span { display: flex; align-items: center; gap: 6px; color: #14845d; font-size: 13px; }.model-grid footer > span.is-error { color: #c26a2e; }.model-grid footer i { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }.prompt-layout { display: grid; grid-template-columns: 220px minmax(0,1fr); gap: 16px; }.prompt-layout > aside { padding: 8px; border: 1px solid #e2e8f0; border-radius: 9px; align-self: start; }.prompt-layout > aside button { width: 100%; min-height: 58px; padding: 8px; border: 0; border-radius: 7px; display: grid; grid-template-columns: 20px 1fr auto; gap: 8px; align-items: center; background: transparent; color: #475569; cursor: pointer; text-align: left; }.prompt-layout > aside button.is-active { background: #edf3ff; color: #2764e7; }.prompt-layout > aside svg { width: 16px; }.prompt-layout > aside span { display: flex; flex-direction: column; }.prompt-layout > aside strong { font-size: 13px; }.prompt-layout > aside small { margin-top: 3px; color: #64748b; font-size: 13px; }.prompt-layout > aside b { font-size: 13px; }.prompt-toolbar { margin-bottom: 12px; display: grid; grid-template-columns: 1fr auto; gap: 10px; }.prompt-name { display: flex; flex-direction: column; }.prompt-name small { margin-top: 4px; color: #64748b; font-size: 13px; }.model-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; }.model-form-grid .is-full { grid-column: 1/-1; }
@media(max-width:1100px){.route-grid{grid-template-columns:1fr 1fr}}@media(max-width:960px){.model-overview{grid-template-columns:repeat(2,1fr)}.model-grid,.route-grid{grid-template-columns:1fr}.prompt-layout{grid-template-columns:1fr}}@media(max-width:600px){.model-overview,.model-form-grid{grid-template-columns:1fr}.prompt-toolbar{grid-template-columns:1fr}}
</style>
