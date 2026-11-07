<template>
 <div class="app-container pipeline-page pipeline-model-page ws-list-page">

  <template v-if="showModelSection">
   <el-tabs v-model="activeTab" class="model-type-tabs" aria-label="模型分类">
    <el-tab-pane v-for="group in modelGroups" :key="group.value" :name="group.value" :label="group.label">
     <template #label><span class="model-tab-label">{{ group.label }}<span v-if="!modelLoading && !modelError" class="model-tab-count">{{ modelCounts[group.value] }}</span></span></template>
     <template v-if="activeTab === group.value">
   <div class="model-management-toolbar">
    <el-input v-model="modelKeyword" :prefix-icon="Search" clearable aria-label="搜索模型" placeholder="搜索模型名称、编码或服务商" />
    <el-dropdown v-if="canModelAdd" trigger="click" @command="openModelDialog">
     <el-button type="primary" :icon="Plus">添加模型<el-icon class="model-add-arrow"><ArrowDown /></el-icon></el-button>
     <template #dropdown><el-dropdown-menu><el-dropdown-item command="text" :icon="Cpu">文本模型</el-dropdown-item><el-dropdown-item command="image" :icon="Picture">图像模型</el-dropdown-item></el-dropdown-menu></template>
    </el-dropdown>
   </div>
   <section class="ws-list-scroll" tabindex="0" :aria-label="activeModelGroup.label + '列表'" :aria-busy="modelLoading">
     <div v-if="modelLoading" class="model-empty">正在加载模型配置…</div>
     <el-alert v-else-if="modelError" :title="modelError" type="error" :closable="false" show-icon><template #default><el-button @click="loadModels">重新加载</el-button></template></el-alert>
     <el-empty v-else-if="!visibleModels.length" :description="modelKeyword.trim() ? '没有匹配的模型' : activeTab === 'all' ? '尚未配置模型' : `尚未配置${activeModelGroup.label}`" :image-size="72" />
     <div v-else class="model-list">
      <article v-for="model in visibleModels" :key="model.modelId">
       <header>
        <span class="model-logo"><el-icon><Picture v-if="modelCapabilities(model).includes('image_generate')" /><Cpu v-else /></el-icon></span>
        <div class="model-identity"><strong>{{ model.modelName || model.modelCode }}</strong><small>{{ model.provider }}</small></div>
        <div class="model-capabilities"><el-tag v-for="capability in modelCapabilities(model)" :key="capability" type="info" effect="plain">{{ capabilityLabel(capability) }}</el-tag></div>
       </header>
       <dl>
        <div><dt>模型编码</dt><dd>{{ model.modelCode }}</dd></div>
        <div><dt>接口地址</dt><dd>{{ model.baseUrl || '未配置' }}</dd></div>
        <template v-if="modelCapabilities(model).includes('image_generate')">
         <div><dt>图片尺寸</dt><dd>{{ model.parameters?.size || '模型默认' }}</dd></div>
         <div><dt>图片质量</dt><dd>{{ model.parameters?.quality || '模型默认' }}</dd></div>
         <div v-if="model.parameters?.style"><dt>图片风格</dt><dd>{{ model.parameters.style }}</dd></div>
        </template>
        <template v-if="modelCapabilities(model).includes('text_generate')">
         <div><dt>输出上限</dt><dd>{{ model.maxTokens ? `${model.maxTokens} Token` : '模型默认' }}</dd></div>
         <div><dt>温度参数</dt><dd>{{ model.temperature ?? '模型默认' }}</dd></div>
        </template>
       </dl>
       <footer>
        <div class="model-status"><span>{{ model.status === '0' ? '已启用' : '已停用' }}</span><el-switch v-if="canModelEdit" :aria-label="(model.modelName || model.modelCode) + '启用状态'" :model-value="model.status === '0'" :loading="modelToggling === model.modelId" :disabled="modelToggling !== null" @change="toggleModel(model, $event)" /></div>
        <el-button v-if="canModelEdit" plain type="primary" :icon="Edit" @click="editModel(model)">配置</el-button>
       </footer>
      </article>
     </div>
   </section>
     </template>
    </el-tab-pane>
   </el-tabs>
  </template>
  <section v-if="showCategorySection" class="category-panel ws-list-scroll" aria-label="类别提示词">
    <div class="category-toolbar">
     <el-input v-model="categoryKeyword" :prefix-icon="Search" clearable placeholder="搜索类别名称或分类要求" aria-label="搜索类别" />
     <el-select v-model="categoryStatus" aria-label="类别状态"><el-option label="全部状态" value="all" /><el-option label="已启用" value="enabled" /><el-option label="已停用" value="disabled" /></el-select>
     <div class="category-toolbar-actions"><el-button @click="previewVisible = true">综合提示词预览</el-button><el-button v-if="canCategorySave" type="primary" :icon="Plus" :disabled="categoryBusy" @click="openCategory()">新增类别</el-button></div>
    </div>
    <el-alert v-if="categoryError" :title="categoryError" type="warning" :closable="false"><template #default><el-button plain @click="loadCategories">重新加载</el-button></template></el-alert>
    <el-table v-else v-loading="categoryLoading" :data="filteredCategories" class="category-table" :empty-text="categoryKeyword || categoryStatus !== 'all' ? '没有匹配的类别' : '暂无类别，请新增类别'">
     <el-table-column prop="name" label="类别名称" width="180"><template #default="{ row }"><strong class="category-name">{{ row.name }}</strong></template></el-table-column>
     <el-table-column label="分类要求" min-width="360"><template #default="{ row }"><el-tooltip placement="top" :show-after="500" popper-class="category-prompt-tooltip"><template #content><div class="category-prompt-tooltip-content">{{ categoryPromptText(row.prompt || '') }}</div></template><p class="category-prompt-summary" tabindex="0">{{ categoryPromptText(row.prompt || '') || '尚未填写分类要求' }}</p></el-tooltip></template></el-table-column>
     <el-table-column prop="appliesTo" label="适用内容" width="110"><template #default="{ row }">{{ ({ all: '全部', news: '新闻资讯', paper: '论文' })[row.appliesTo] || row.appliesTo || '—' }}</template></el-table-column>
     <el-table-column label="分类模型" width="180" show-overflow-tooltip><template #default="{ row }">{{ models.find(model => model.modelId === row.modelId)?.modelName || (row.modelId ? '已选择模型' : '未配置') }}</template></el-table-column>
     <el-table-column label="状态" width="100" align="center"><template #default="{ row }"><el-tag :type="row.isEnabled ? 'success' : 'info'" effect="light">{{ row.isEnabled ? '已启用' : '已停用' }}</el-tag></template></el-table-column>
     <el-table-column label="操作" width="250" align="center"><template #default="{ row }"><el-button v-if="canCategorySave" plain type="primary" :disabled="categoryBusy" @click="openCategory(row)">编辑</el-button><el-button v-if="canCategorySave" plain :disabled="!row.isEnabled || categoryBusy" :loading="categoryDisabling === row.id" @click="disableCategory(row)">停用</el-button><el-button v-if="canCategorySave" plain type="danger" :disabled="categoryBusy" :loading="categoryDeleting === row.id" @click="deleteCategory(row)">删除</el-button></template></el-table-column>
    </el-table>

  </section>
  <el-dialog
   v-if="showCategorySection"
   v-model="previewVisible"
   title="综合提示词预览"
   width="min(860px, calc(100vw - 32px))"
   class="ps-centered-dialog"
   align-center
   append-to-body
   destroy-on-close
  >
    <section class="processing-preview" aria-labelledby="processing-preview-title">
     <header class="preview-header">
      <div><h2 id="processing-preview-title">预览范围</h2><p>查看当前启用类别如何组合成提示词。仅本地预览，不调用模型。</p></div>
      <el-select v-model="previewKind" aria-label="预览适用来源" class="preview-source"><el-option label="全部启用类别" value="all" /><el-option label="普通新闻" value="news" /><el-option label="论文" value="paper" /><el-option label="已确认官网" value="website" /></el-select>
     </header>
     <el-alert v-if="categoryLoading || categoryError" :title="categoryLoading ? '类别读取中，暂不能预览综合提示词' : '类别读取失败，请先重新加载；不使用旧数据预览'" type="warning" :closable="false" />
     <template v-else>
      <div class="preview-rule-head"><strong>分类要求</strong><el-tag type="info" effect="plain" aria-live="polite">{{ processingPreview.categories.length }} 个启用类别</el-tag></div>
      <div v-if="processingPreview.categories.length" class="preview-rules">
       <article v-for="category in processingPreview.categories" :key="category.id || category.name" class="preview-rule">
        <h3>{{ category.name }}</h3><p>{{ categoryPromptText(category.prompt) }}</p>
       </article>
      </div>
      <p v-else class="preview-empty">当前范围暂无启用的分类要求，请先配置并启用类别。</p>
      <el-collapse class="preview-details">
       <el-collapse-item title="完整提示词" name="prompt">
        <p class="preview-help">只读内容包含过滤、分类、摘要及实体抽取等规则。此处展示拼接文本，不代表后端已采用该处理流程。</p>
        <p v-for="warning in processingPreview.warnings" :key="warning" class="preview-warning">{{ warning }}</p>
        <el-input :model-value="processingPreview.systemPrompt" aria-label="完整系统提示词，只读" type="textarea" :rows="12" readonly resize="vertical" class="preview-prompt" />
       </el-collapse-item>
       <el-collapse-item title="样本文本（可选）" name="sample">
        <p class="preview-help">粘贴原文可查看提交消息的结构，不会生成分类、摘要或解读结果。</p>
        <el-input v-model="previewContent" aria-label="样本文本" type="textarea" :rows="4" maxlength="20000" show-word-limit placeholder="在这里粘贴需要处理的文章内容" />
        <template v-if="previewContent"><p class="preview-help preview-message-label">用户消息（只读）</p><el-input :model-value="processingPreview.userPrompt" aria-label="用户消息，只读" type="textarea" :rows="5" readonly class="preview-prompt" /></template>
       </el-collapse-item>
      </el-collapse>
     </template>
    </section>
   <template #footer><el-button @click="previewVisible = false">关闭</el-button></template>
  </el-dialog>
  <el-dialog v-if="showModelSection" v-model="modelDialogVisible" class="model-config-dialog ps-centered-dialog" :title="modelDialogTitle" width="min(660px, calc(100vw - 32px))" align-center>
   <el-form label-position="top" class="model-config-form" autocomplete="off">
    <div class="model-form-grid">
     <el-form-item label="模型名称"><el-input v-model="modelForm.name" placeholder="例如：DeepSeek 文本生成" autocomplete="off" /></el-form-item>
     <el-form-item label="服务商"><el-select v-model="modelForm.provider" filterable placeholder="选择服务商"><el-option v-for="provider in providers" :key="provider.value" :label="provider.label" :value="provider.value" /></el-select></el-form-item>
     <el-form-item label="模型编码" class="is-full"><el-input v-model="modelForm.modelId" placeholder="填写服务商提供的模型编码" autocomplete="off" /></el-form-item>
     <el-form-item label="接口地址" class="is-full model-help-field">
      <el-input v-model="modelForm.endpoint" placeholder="https://api.example.com/v1" autocomplete="off" />
      <p class="model-field-help">其他服务商请选 compatible，并填写兼容接口地址。</p>
     </el-form-item>
     <el-form-item label="模型能力" class="is-full model-help-field">
      <el-checkbox-group v-model="modelForm.capabilities" class="model-capability-options" aria-label="模型能力">
       <el-checkbox value="text_generate" border>数据处理（文本）</el-checkbox><el-checkbox value="image_generate" border>图片生成</el-checkbox><el-checkbox value="image_input" border>图片输入（识图）</el-checkbox><el-checkbox value="reasoning" border>推理</el-checkbox>
      </el-checkbox-group>
      <p class="model-field-help">可多选；图片输入与图片生成需分别配置。</p>
     </el-form-item>
     <el-form-item v-if="hasTextCapability" label="最大输出 Token"><el-input-number v-model="modelForm.maxTokens" aria-label="最大输出 Token" :min="1" :max="32768" :controls="false" placeholder="模型默认" /></el-form-item>
     <el-form-item v-if="hasTextCapability" label="温度参数"><el-input-number v-model="modelForm.temperature" aria-label="温度参数" :min="0" :max="2" :step="0.1" :controls="false" /></el-form-item>
     <template v-if="hasImageGeneration">
      <el-form-item label="图片尺寸"><el-input v-model="modelForm.imageSize" clearable placeholder="例如：1024x1024" /></el-form-item>
      <el-form-item label="图片质量"><el-input v-model="modelForm.imageQuality" clearable placeholder="例如：standard" /></el-form-item>
      <el-form-item label="图片风格" class="is-full"><el-input v-model="modelForm.imageStyle" clearable placeholder="例如：natural" autocomplete="off" /></el-form-item>
      <p class="model-field-help is-full">尺寸、质量和风格按服务商支持的值填写，留空使用模型默认设置。</p>
     </template>
     <el-form-item label="API 密钥" class="is-full"><el-input v-model="modelForm.apiKey" type="password" name="model-api-key" autocomplete="new-password" show-password :placeholder="editingModel ? '留空保留原密钥' : '填写服务商 API 密钥，加密保存'" /></el-form-item>
    </div>
   </el-form>
   <template #footer><el-button @click="modelDialogVisible = false">取消</el-button><el-button v-if="canModelSave" type="primary" @click="saveModel" :loading="modelSaving">保存配置</el-button></template>
  </el-dialog>

  <el-dialog v-if="showCategorySection" v-model="categoryDialogVisible" :title="editingCategory ? '编辑类别' : '新增类别'" width="min(720px, calc(100vw - 32px))" class="category-config-dialog" :close-on-click-modal="!categorySaving" :close-on-press-escape="!categorySaving" :show-close="!categorySaving" destroy-on-close>
   <el-form label-position="top" class="category-config-form" :disabled="categorySaving">
    <div v-if="!editingCategory" class="category-examples"><span>使用示例</span><el-button v-for="preset in categoryPresets" :key="preset.name" plain :disabled="categoryBusy" @click="prefillCategory(preset)">{{ preset.name }}</el-button></div>
    <div class="category-basic-grid">
      <el-form-item label="类别名称"><el-input v-model="categoryForm.name" placeholder="例如：管网安全" /></el-form-item>
      <el-form-item label="适用内容"><el-select v-model="categoryForm.appliesTo"><el-option label="全部" value="all" /><el-option label="新闻资讯" value="news" /><el-option label="论文" value="paper" /></el-select></el-form-item>
    </div>
    <el-form-item label="分类要求" class="category-prompt-field">
      <p class="category-prompt-help">用自己的话描述哪些内容属于这个类别，可补充关注重点和排除条件。</p>
      <el-input v-model="categoryForm.prompt" aria-label="分类要求" type="textarea" :autosize="{ minRows: 7, maxRows: 14 }" resize="vertical" placeholder="例如：关注油气管道的建设、储运、巡检和安全技术。与能源运输相关的政策和应用案例也保留，排除无关的招聘和广告。" />
      <small v-if="legacyPromptText" class="category-prompt-help">旧格式已转为文字显示；修改并保存后将使用新的文字描述。</small>
    </el-form-item>
    <div class="category-enable-row"><span>启用类别</span><el-switch v-model="categoryForm.isEnabled" aria-label="启用类别" /><span class="category-prompt-help">启用后参与内容分类</span></div>
    <el-collapse v-model="categoryAdvanced">
      <el-collapse-item title="高级设置 · 分类模型" name="model">
        <el-form-item label="分类模型"><el-select v-model="categoryForm.modelId" clearable placeholder="请选择文本模型"><el-option v-for="model in textModels" :key="model.modelId" :label="model.modelName || model.modelCode" :value="model.modelId" /></el-select></el-form-item>
        <p class="category-prompt-help">启用类别前需选择可用的文本模型；暂不启用时可先保存分类要求。</p>
        <el-alert v-if="modelError" :title="modelError" type="warning" :closable="false"><template #default><el-button plain @click="loadModels">重新加载模型</el-button></template></el-alert>
      </el-collapse-item>
    </el-collapse>
   </el-form>
   <template #footer><el-button :disabled="categorySaving" @click="categoryDialogVisible = false">取消</el-button><el-button v-if="canCategorySave" type="primary" :loading="categorySaving" @click="saveCategory">保存</el-button></template>
  </el-dialog>
 </div>
</template>
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Picture, Cpu, Edit, ArrowDown } from '@element-plus/icons-vue'
import { addModel, listModelAll, updateModel } from '@/api/ai/model'
import { listPipelineCategories, createPipelineCategory, updatePipelineCategory, deletePipelineCategory } from '@/api/pipeline/categories'
import { categoryPayload, modelCapabilities, modelsFor } from '@/utils/pipeline/compactContract'
import { CATEGORY_PRESETS, categoryPresetDraft, categoryPromptText, buildProcessingPrompt } from '@/utils/pipeline/processingPrompt'
import { checkPermi, checkRole } from '@/utils/permission'
const props = defineProps({ section: { type: String, default: 'models' } })
const providers = [{ value: 'openai', label: 'OpenAI' }, { value: 'openai-compatible', label: 'OpenAI 兼容' }, { value: 'compatible', label: '其他服务商的兼容端点' }, { value: 'deepseek', label: 'DeepSeek' }]
function capabilityLabel(value) { return ({ text_generate: '数据处理（文本）', image_input: '图片输入', image_generate: '图片生成', reasoning: '推理' })[value] || value }
const activeTab = ref('all')
const modelKeyword = ref(''), modelToggling = ref(null)
const modelGroups = [
 { value: 'all', label: '全部模型' },
 { value: 'models', label: '文本模型', kind: 'text' },
 { value: 'images', label: '图像模型', kind: 'image' }
]
const activeModelGroup = computed(() => modelGroups.find(group => group.value === activeTab.value))
const visibleModels = computed(() => modelsInGroup(activeTab.value))
const modelCounts = computed(() => Object.fromEntries(modelGroups.map(group => [group.value, modelsInGroup(group.value, false).length])))
function modelsInGroup(group, useKeyword = true) {
 const keyword = useKeyword ? modelKeyword.value.trim().toLocaleLowerCase() : ''
 return models.value.filter(model => {
  const capabilities = modelCapabilities(model)
  const image = capabilities.includes('image_generate') || capabilities.includes('image_input')
  const inGroup = group === 'all' || (group === 'images' ? image : capabilities.includes('text_generate') || !image)
  return inGroup && (!keyword || [model.modelName, model.modelCode, model.provider].filter(Boolean).join(' ').toLocaleLowerCase().includes(keyword))
 })
}
const models = ref([]), modelLoading = ref(false), modelError = ref(''), modelSaving = ref(false)
const modelDialogVisible = ref(false), editingModel = ref(null)
const canModelQuery = computed(() => checkPermi(['ai:model:query']))
const canModelAdd = computed(() => checkPermi(['ai:model:add']))
const canModelEdit = computed(() => checkPermi(['ai:model:edit']))
const canModelSave = computed(() => editingModel.value ? canModelEdit.value : canModelAdd.value)
const canCategoryList = computed(() => checkRole(['admin']))
const canCategorySave = computed(() => checkRole(['admin']))
const showModelSection = computed(() => props.section === 'models' && canModelQuery.value)
const showCategorySection = computed(() => props.section === 'categories' && canCategoryList.value)
const modelForm = reactive({ modelId: '', name: '', provider: '', endpoint: '', capabilities: [], maxTokens: null, temperature: 0.2, apiKey: '', imageSize: '', imageQuality: '', imageStyle: '' })
const hasTextCapability = computed(() => modelForm.capabilities.includes('text_generate'))
const hasImageGeneration = computed(() => modelForm.capabilities.includes('image_generate'))
const modelDialogTitle = computed(() => `${editingModel.value ? '配置' : '添加'}${modelForm.capabilities.some(value => value === 'image_generate' || value === 'image_input') && !hasTextCapability.value ? '图像' : '文本'}模型`)
function openModelDialog(kind = 'text') {
 if (!canModelAdd.value) return
 editingModel.value = null
 Object.assign(modelForm, { modelId: '', name: '', provider: kind === 'image' ? 'compatible' : '', endpoint: '', capabilities: [kind === 'image' ? 'image_generate' : 'text_generate'], maxTokens: null, temperature: 0.2, apiKey: '', imageSize: '', imageQuality: '', imageStyle: '' })
 modelDialogVisible.value = true
}
function editModel(model) {
 if (!canModelEdit.value) return
 editingModel.value = model
 Object.assign(modelForm, { modelId: model.modelCode, name: model.modelName || '', provider: model.provider || '', endpoint: model.baseUrl || '', capabilities: [...modelCapabilities(model)], maxTokens: model.maxTokens, temperature: model.temperature ?? 0.2, apiKey: '', imageSize: model.parameters?.size || '', imageQuality: model.parameters?.quality || '', imageStyle: model.parameters?.style || '' })
 modelDialogVisible.value = true
}
function modelParameters() {
 const parameters = { ...(editingModel.value?.parameters || {}) }
 if (hasTextCapability.value) {
  if (modelForm.maxTokens) parameters.max_tokens = modelForm.maxTokens
  else delete parameters.max_tokens
  parameters.temperature = modelForm.temperature
 }
 if (hasImageGeneration.value) {
  for (const [key, value] of [['size', modelForm.imageSize], ['quality', modelForm.imageQuality], ['style', modelForm.imageStyle]]) {
   if (value.trim()) parameters[key] = value.trim()
   else delete parameters[key]
  }
 }
 return parameters
}
async function loadModels() { if (!canModelQuery.value) return; modelLoading.value = true; modelError.value = ''; try { const res = await listModelAll(); models.value = res.data?.rows || res.data || [] } catch (error) { models.value = []; modelError.value = error?.msg || error?.message || '模型配置暂时无法加载，请检查服务后重试'; ElMessage.warning(modelError.value) } finally { modelLoading.value = false } }
async function saveModel() {
 if (!canModelSave.value || modelSaving.value) return
 if (!modelForm.name.trim() || !modelForm.modelId.trim() || !modelForm.provider || !modelForm.endpoint.trim() || !modelForm.capabilities.length) return ElMessage.warning('请填写名称、编码、服务商、地址并选择能力')
 if (!editingModel.value && !modelForm.apiKey.trim()) return ElMessage.warning('请填写新模型的 API 密钥')
 modelSaving.value = true
 try {
  const payload = { modelId: editingModel.value?.modelId, modelCode: modelForm.modelId.trim(), modelName: modelForm.name.trim(), provider: modelForm.provider, baseUrl: modelForm.endpoint.trim(), capabilities: [...modelForm.capabilities], parameters: modelParameters(), ...(hasTextCapability.value ? { maxTokens: modelForm.maxTokens, temperature: modelForm.temperature } : {}), status: editingModel.value?.status || '0', ...(modelForm.apiKey.trim() ? { apiKey: modelForm.apiKey.trim() } : {}) }
  if (editingModel.value) await updateModel(payload)
  else await addModel(payload)
  modelDialogVisible.value = false
  activeTab.value = modelForm.capabilities.some(value => value === 'image_generate' || value === 'image_input') ? 'images' : 'models'
  ElMessage.success('模型配置已保存'); await loadModels()
 } catch (error) { ElMessage.error(error?.msg || error?.message || '模型配置保存失败') }
 finally { modelSaving.value = false }
}
async function toggleModel(model, enabled) {
 if (!canModelEdit.value || modelToggling.value !== null) return
 modelToggling.value = model.modelId
 try { await updateModel({ modelId: model.modelId, status: enabled ? '0' : '1' }); model.status = enabled ? '0' : '1'; ElMessage.success(`模型已${enabled ? '启用' : '停用'}`) }
 catch (error) { ElMessage.error(error?.msg || error?.message || '模型状态更新失败') }
 finally { modelToggling.value = null }
}

const categories = ref([]), categoryLoading = ref(false), categoryError = ref('')
const categoryDialogVisible = ref(false), categorySaving = ref(false), editingCategory = ref(null)
const categoryDisabling = ref(null)
const categoryDeleting = ref(null)
const categoryBusy = computed(() => categorySaving.value || categoryDisabling.value !== null || categoryDeleting.value !== null)
const categoryPresets = computed(() => CATEGORY_PRESETS)
const previewKind = ref('all'), previewContent = ref(''), previewVisible = ref(false)
const categoryKeyword = ref(''), categoryStatus = ref('all')
const filteredCategories = computed(() => {
 const keyword = categoryKeyword.value.trim().toLocaleLowerCase()
 return categories.value.filter(category =>
  (categoryStatus.value === 'all' || (categoryStatus.value === 'enabled' ? category.isEnabled : !category.isEnabled)) &&
  (!keyword || [category.name, categoryPromptText(category.prompt || '')].join(' ').toLocaleLowerCase().includes(keyword)))
})
const processingPreview = computed(() => buildProcessingPrompt({ categories: categoryError.value || categoryLoading.value ? [] : categories.value, kind: previewKind.value, content: previewContent.value }))
const categoryForm = reactive({ name: '', prompt: '', modelId: null, appliesTo: 'all', sortOrder: 0, isEnabled: false })
const categoryAdvanced = ref([])
const legacyPromptText = ref('')
const textModels = computed(() => modelsFor(models.value, 'text_generate'))
function openCategory(item = null) {
 if (!canCategorySave.value || categoryBusy.value) return
 editingCategory.value = item
 categoryAdvanced.value = []
 const readablePrompt = categoryPromptText(item?.prompt || '')
 legacyPromptText.value = readablePrompt !== (item?.prompt || '') ? readablePrompt : ''
 Object.assign(categoryForm, { name: item?.name || '', prompt: readablePrompt, modelId: item?.modelId ?? null, appliesTo: item?.appliesTo || 'all', sortOrder: item?.sortOrder ?? 0, isEnabled: item?.isEnabled ?? false })
 categoryDialogVisible.value = true
}
function prefillCategory(preset) {
 if (!canCategorySave.value || categoryBusy.value) return
 openCategory()
 Object.assign(categoryForm, categoryPresetDraft(preset))
}
async function loadCategories() {
 if (!canCategoryList.value) return
 categoryLoading.value = true; categoryError.value = ''
 try { const res = await listPipelineCategories(); categories.value = res.data?.rows || [] }
 catch (error) { categories.value = []; categoryError.value = error?.msg || error?.message || '类别列表加载失败，请重试' }
 finally { categoryLoading.value = false }
}
async function saveCategory() {
 if (!canCategorySave.value || categoryBusy.value) return
 categorySaving.value = true
 try {
  const prompt = legacyPromptText.value && categoryForm.prompt === legacyPromptText.value ? editingCategory.value.prompt : categoryForm.prompt
  const data = categoryPayload({ ...categoryForm, prompt })
  if (data.isEnabled && !textModels.value.some(model => String(model.modelId) === String(data.modelId))) { categoryAdvanced.value = ['model']; throw new Error('请在高级设置中选择可用的文本模型，再启用类别') }
  if (editingCategory.value) await updatePipelineCategory(editingCategory.value.id, data)
  else await createPipelineCategory(data)
  categoryDialogVisible.value = false; ElMessage.success('类别已保存'); await loadCategories()
 } catch (error) { ElMessage.error(error?.msg || error?.message || '类别保存失败') }
 finally { categorySaving.value = false }
}
async function disableCategory(item) {
 if (!canCategorySave.value || !item.isEnabled || categoryBusy.value) return
 try {
  categoryDisabling.value = item.id
  await ElMessageBox.confirm(`停用“${item.name}”？历史内容和类别引用会保留。`, '停用类别', { type: 'warning', confirmButtonText: '停用', cancelButtonText: '取消' })
  await updatePipelineCategory(item.id, categoryPayload({ ...item, isEnabled: false }))
  ElMessage.success('类别已停用'); await loadCategories()
 } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.msg || error?.message || '类别停用失败') }
 finally { categoryDisabling.value = null }
}
async function deleteCategory(item) {
 if (!canCategorySave.value || categoryBusy.value) return
 categoryDeleting.value = item.id
 try {
  await ElMessageBox.confirm(`确认删除类别“${item.name}”及其分类提示词？删除后无法恢复。已被文章引用的类别无法删除，可选择停用。`, '删除类别提示词', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' })
  await deletePipelineCategory(item.id)
  categories.value = categories.value.filter(row => row.id !== item.id)
  ElMessage.success('类别提示词已删除')
  await loadCategories()
 } catch (error) {
  if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.msg || error?.message || '类别删除失败，请重试')
 } finally { categoryDeleting.value = null }
}

onMounted(() => {
 if (canModelQuery.value) loadModels()
 if (showCategorySection.value) loadCategories()
})
</script>
<style scoped>
.preset-row { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin: 0 0 14px; font-size: 13px; }
.preset-row .el-button { margin-left: 0; }
.preset-row small, .preview-caption { color: var(--el-text-color-regular); line-height: 1.65; }
.processing-preview { min-width: 0; }
.processing-preview h2 { margin: 0; font-size: 16px; }
.preview-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.preview-header > div { min-width: 0; }
.preview-header p, .preview-help, .preview-empty { margin: 6px 0 0; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.7; }
.preview-source { width: 210px; flex-shrink: 0; }
.preview-rule-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.preview-rule-head strong { font-size: 14px; }
.preview-rules { max-height: 320px; overflow-y: auto; border: 1px solid var(--el-border-color-light); border-radius: 6px; }
.preview-rule { padding: 12px 16px; }
.preview-rule + .preview-rule { border-top: 1px solid var(--el-border-color-lighter); }
.preview-rule h3 { margin: 0 0 6px; font-size: 14px; color: var(--el-text-color-primary); }
.preview-rule p { margin: 0; font-size: 14px; line-height: 1.8; white-space: pre-wrap; overflow-wrap: anywhere; color: var(--el-text-color-regular); }
.preview-empty { padding: 12px 0; }
.preview-details { margin-top: 14px; }
.preview-help { margin-bottom: 10px; }
.preview-message-label { margin-top: 14px; }
.preview-prompt :deep(.el-textarea__inner) { font-size: 14px; line-height: 1.8; padding: 12px; }
@media (max-width: 600px) { .preview-header { flex-direction: column; align-items: stretch; gap: 10px; } .preview-source { width: 100%; } .preview-rule { padding: 12px; } }
.preview-warning { color: var(--el-color-warning-dark-2); font-size: 13px; line-height: 1.6; }
.model-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px 16px; }
.model-form-grid .is-full { grid-column: 1 / -1; }
.model-config-form :deep(.el-form-item) { margin-bottom: 0; min-width: 0; }
.model-config-form :deep(.el-form-item__label) { margin-bottom: 8px; padding: 0; line-height: 20px; font-weight: 500; color: var(--el-text-color-primary); }
.model-config-form :deep(.el-select), .model-config-form :deep(.el-input-number) { width: 100%; }
.model-config-form :deep(.el-input__wrapper), .model-config-form :deep(.el-select__wrapper) { min-height: 40px; padding-inline: 12px; border-radius: 6px; background: var(--el-bg-color); outline: none; box-sizing: border-box; }
.model-config-form :deep(.el-input__inner) { height: 38px; font-size: 14px; text-align: left; }
.model-config-form :deep(.el-input__inner:focus), .model-config-form :deep(.el-input__inner:focus-visible), .model-config-form :deep(.el-select__input:focus-visible) { outline: none; box-shadow: none; }
.model-config-form :deep(.el-input__wrapper.is-focus), .model-config-form :deep(.el-select__wrapper.is-focused) { outline: none; box-shadow: 0 0 0 1px var(--el-color-primary) inset, 0 0 0 3px var(--el-color-primary-light-9); }
.model-help-field :deep(.el-form-item__content) { display: block; }
.model-capability-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.model-capability-options :deep(.el-checkbox.is-bordered) { width: 100%; height: auto; min-height: 40px; margin: 0; padding: 10px 12px; border-radius: 6px; }
.model-capability-options :deep(.el-checkbox.is-checked) { background: var(--el-color-primary-light-9); }
.model-capability-options :deep(.el-checkbox__label) { white-space: normal; line-height: 20px; }
@media (max-width: 600px) {
 .model-form-grid { grid-template-columns: minmax(0, 1fr); gap: 16px; }
 .model-config-form :deep(.el-input__wrapper), .model-config-form :deep(.el-select__wrapper), .model-capability-options :deep(.el-checkbox.is-bordered) { min-height: 44px; }
 .model-config-form :deep(.el-input__inner) { font-size: 16px; height: 42px; }
}
.category-config-dialog { max-height: 88dvh; display: flex; flex-direction: column; }
.category-config-dialog :deep(.el-dialog__body) { min-height: 0; overflow-y: auto; }
.category-config-dialog :deep(.el-dialog__footer) { flex-shrink: 0; }
.category-prompt-field :deep(.el-form-item__content) { display: block; }
.category-prompt-field :deep(.el-textarea__inner) { font-size: 15px; line-height: 1.8; padding: 12px 14px; }
.category-prompt-help { margin: 0 0 10px; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.6; }
.category-prompt-field small { display: block; margin: 8px 0 0; }
.category-enable-row { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 12px; }
.category-enable-row .category-prompt-help { margin: 0; }
.category-config-form :deep(.el-form-item) { margin-bottom: 16px; }
.category-config-form :deep(.el-select) { width: 100%; }
.category-basic-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; }
.category-options-row { display: flex; align-items: flex-start; gap: 32px; padding-top: 14px; border-top: 1px solid #e2e8f0; }
.category-options-row :deep(.el-form-item) { margin-bottom: 0; }
.category-config-form :deep(.el-textarea__inner) { line-height: 1.65; }
.category-config-form :deep(.el-input__inner:focus-visible),
.category-config-form :deep(.el-textarea__inner:focus-visible) { outline: none; }
.category-config-form :deep(.el-input__wrapper.is-focus),
.category-config-form :deep(.el-select__wrapper.is-focused) { box-shadow: 0 0 0 1px #7da6c0 inset, 0 0 0 2px #409eff10; }
.category-config-form :deep(.el-textarea__inner:focus) { box-shadow: 0 0 0 1px #7da6c0 inset, 0 0 0 2px #409eff10; }
@media (max-width: 520px) { .category-basic-grid { grid-template-columns: minmax(0, 1fr); gap: 0; } .category-options-row { gap: 24px; flex-wrap: wrap; } }
.model-type-tabs { display: flex; flex-direction: column; flex: 1; min-height: 0; min-width: 0; }
.model-type-tabs > :deep(.el-tabs__header) { flex-shrink: 0; margin: 0 0 16px; }
.model-type-tabs > :deep(.el-tabs__header .el-tabs__item) { height: 44px; }
.model-type-tabs > :deep(.el-tabs__content) { flex: 1; min-height: 0; }
.model-type-tabs :deep(.el-tab-pane) { display: flex; flex-direction: column; height: 100%; min-height: 0; gap: 12px; }
.model-tab-label { display: inline-flex; align-items: center; gap: 8px; }
.model-tab-count { min-width: 20px; padding-inline: 5px; border-radius: 4px; background: var(--el-fill-color); color: var(--el-text-color-regular); font-size: 12px; font-weight: 400; line-height: 20px; text-align: center; font-variant-numeric: tabular-nums; }
.model-type-tabs :deep(.is-active) .model-tab-count { color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.model-management-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 12px 16px; border: 1px solid var(--el-border-color-light); border-radius: 8px; background: var(--el-bg-color); }
.model-management-toolbar > .el-input { flex: 1 1 220px; min-width: 0; }
.model-management-toolbar > .el-dropdown { flex-shrink: 0; margin-inline-start: auto; }
.model-add-arrow { margin-left: 8px; }
.pipeline-model-page .category-panel { padding: 16px; border: 1px solid var(--el-border-color-light); border-radius: 8px; background: var(--el-bg-color); }
.model-empty { padding: 40px 16px; text-align: center; color: var(--el-text-color-secondary); }
.model-list { display: grid; gap: 12px; }
.model-list article { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 20px 24px; align-items: center; min-width: 0; padding: 20px 24px 0; border: 1px solid var(--el-border-color-light); border-radius: 8px; background: var(--el-bg-color); overflow: hidden; }
.model-list header { display: grid; grid-template-columns: 44px minmax(0, 1fr); gap: 8px 12px; align-items: center; min-width: 0; }
.model-logo { grid-row: 1 / 3; display: grid; place-items: center; width: 44px; height: 44px; border: 1px solid var(--el-color-primary-light-8); border-radius: 10px; background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-size: 22px; }
.model-identity { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 12px; min-width: 0; }
.model-list header strong { font-size: 17px; font-weight: 600; line-height: 1.5; overflow-wrap: anywhere; color: var(--el-text-color-primary); }
.model-list header small { font-size: 13px; overflow-wrap: anywhere; color: var(--el-text-color-regular); }
.model-capabilities { grid-column: 2; display: flex; flex-wrap: wrap; gap: 6px; }
.model-capabilities :deep(.el-tag) { --el-tag-bg-color: var(--el-fill-color-light); --el-tag-border-color: transparent; --el-tag-text-color: var(--el-text-color-regular); }
.model-list dl { grid-column: 1 / -1; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.5fr) repeat(2, minmax(0, .65fr)); gap: 18px 24px; min-width: 0; margin: 0 -24px; padding: 16px 24px 18px; border-top: 1px solid var(--el-border-color-lighter); background: var(--el-fill-color-lighter); font-size: 13px; line-height: 1.6; }
.model-list dl > div { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.model-list dt { color: var(--el-text-color-regular); font-size: 12px; }
.model-list dd { margin: 0; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; color: var(--el-text-color-primary); }
.model-list footer { grid-column: 2; grid-row: 1; display: flex; align-items: center; gap: 20px; }
.model-list footer > .el-button { margin: 0; }
.model-status { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--el-text-color-regular); white-space: nowrap; }
@container workspace (max-width: 820px) {
 .model-list dl { grid-template-columns: repeat(2, minmax(0, 1fr)); }
 .model-list footer { gap: 12px; }
}
@container workspace (max-width: 560px) {
 .model-list article { gap: 16px; padding: 16px 16px 0; }
 .model-list header { grid-column: 1 / -1; }
 .model-list footer { grid-column: 1 / -1; grid-row: 3; justify-content: space-between; margin-top: -16px; padding-block: 12px; border-top: 1px solid var(--el-border-color-lighter); }
 .model-list dl { gap: 16px; margin-inline: -16px; padding: 16px; }
 .model-list footer > .el-button, .model-status { min-height: 44px; }
}
:deep(.model-config-dialog) { display: flex; flex-direction: column; max-height: calc(100dvh - 32px); padding: 0; border-radius: 12px; overflow: hidden; }
:deep(.model-config-dialog .el-dialog__body) { min-height: 0; padding: 20px 24px 24px; overflow-y: auto; overscroll-behavior: contain; }
:deep(.model-config-dialog .el-dialog__header) { flex-shrink: 0; margin: 0; padding: 20px 48px 16px 24px; border-bottom: 1px solid var(--el-border-color-lighter); }
:deep(.model-config-dialog .el-dialog__footer) { flex-shrink: 0; padding: 16px 24px; border-top: 1px solid var(--el-border-color-lighter); }
.model-field-help { margin: 7px 0 0; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.6; }
.category-toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.category-toolbar > .el-input { flex: 1; min-width: 160px; }
.category-toolbar > .el-select { width: 140px; flex-shrink: 0; }
.category-toolbar-actions, .category-examples { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.category-toolbar-actions { flex-shrink: 0; }
.category-toolbar-actions .el-button, .category-examples .el-button { margin: 0; }
.category-examples { margin-bottom: 18px; }
.category-examples > span { font-size: 13px; color: var(--el-text-color-secondary); margin-right: 4px; }
.category-table { width: 100%; }
.category-table :deep(.el-table__cell) { padding-block: 14px; }
.category-name { font-size: 14px; color: var(--el-text-color-primary); overflow-wrap: anywhere; }
.category-prompt-summary { margin: 0; font-size: 14px; line-height: 1.7; color: var(--el-text-color-regular); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; }
.category-prompt-tooltip-content { max-width: min(520px, 80vw); max-height: 40vh; overflow-y: auto; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.7; }
@media (max-width: 760px) { .category-toolbar { flex-wrap: wrap; gap: 8px; } .category-toolbar > .el-input { flex-basis: calc(100% - 150px); min-width: 0; } .category-toolbar-actions { width: 100%; justify-content: flex-end; } }
@media(max-width:760px) {
 .model-management-toolbar { padding: 12px; }
}
</style>
