<template>
 <section class="model-purpose-settings" aria-labelledby="model-purpose-title">
  <header><h2 id="model-purpose-title">选择业务使用的模型</h2><p>按业务用途分别选择模型，保存后生效。</p></header>
  <el-alert v-if="modelError" title="模型列表加载失败，请重新加载后选择。" type="error" :closable="false" show-icon><template #default><el-button plain type="primary" @click="$emit('reload-models')">重新加载模型</el-button></template></el-alert>
  <div v-for="item in purposes" :key="item.key" class="model-purpose-row">
   <div class="model-purpose-copy"><h3 :id="`purpose-${item.key}`">{{ item.label }}</h3><p>{{ item.description }}</p></div>
   <div class="model-purpose-control">
    <el-select v-model="item.modelId" :aria-label="item.label" :aria-labelledby="`purpose-${item.key}`" filterable clearable :placeholder="item.capability === 'image_generate' ? '请选择图片生成模型' : '请选择文本模型'" :loading="item.loading || loading" :disabled="!editable || item.loading || item.saving || !!item.error || loading || !!modelError">
     <el-option label="暂不启用" value="" />
     <el-option v-if="unavailable(item)" :value="item.modelId" :label="`当前模型不可用（${item.modelId}）`" disabled />
     <el-option v-for="model in availableModels(item)" :key="model.modelId" :label="model.modelName || model.modelCode" :value="String(model.modelId)" />
    </el-select>
    <el-button v-if="editable" type="primary" :loading="item.saving" :disabled="item.loading || loading || !!item.error || !!modelError || item.modelId === item.savedId" @click="save(item)">保存</el-button>
   </div>
   <p v-if="!loading && !modelError && !availableModels(item).length" class="model-purpose-hint">尚未接入可用的{{ item.capability === 'image_generate' ? '图片生成' : '文本' }}模型。<el-button v-if="addable" plain type="primary" @click="$emit('add-model', item.capability === 'image_generate' ? 'image' : 'text')">{{ item.capability === 'image_generate' ? '添加图片模型' : '添加文本模型' }}</el-button></p>
   <p v-if="item.error || item.saveError || unavailable(item)" class="model-purpose-error" role="alert">{{ item.error || item.saveError || '当前模型已停用或不可用，请重新选择。' }}<el-button v-if="item.error" plain type="primary" @click="load(item)">重试</el-button></p>
  </div>
 </section>
</template>
<script setup>
import { computed, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { getGenerationModelConfig, updateGenerationModelConfig, getProcessingModelConfig, updateProcessingModelConfig, getTranslationModelConfig, updateTranslationModelConfig } from '@/api/ai/model'
import { modelsFor } from '@/utils/pipeline/compactContract'
defineEmits(['reload-models', 'add-model'])
const props = defineProps({ models: { type: Array, default: () => [] }, loading: Boolean, modelError: String, editable: Boolean, addable: Boolean })
const modelsByCapability = computed(() => ({ text_generate: modelsFor(props.models, 'text_generate'), image_generate: modelsFor(props.models, 'image_generate') }))
function availableModels(item) { return modelsByCapability.value[item.capability] || [] }
const purposes = reactive([
 { key: 'processing', label: '内容处理模型', description: '过滤、分类时一并生成摘要、提取实体与专业解读。', read: getProcessingModelConfig, write: updateProcessingModelConfig },
 { key: 'translation', label: '翻译模型', description: '将英文新闻正文、论文摘要翻译为中文。', read: getTranslationModelConfig, write: updateTranslationModelConfig },
 { key: 'image', label: '图片生成模型', capability: 'image_generate', description: '生成简报、科研报告等成果的配图，按生成设置启用。', read: () => getGenerationModelConfig('image'), write: value => updateGenerationModelConfig('image', value) },
 { key: 'digest', label: '简报生成模型', description: '生成周报和月报正文，自动计划也使用此模型。', read: () => getGenerationModelConfig('digest'), write: value => updateGenerationModelConfig('digest', value) },
 { key: 'research', label: '科研报告生成模型', description: '生成科研需求、技术路线等报告正文及后续改写。', read: () => getGenerationModelConfig('research'), write: value => updateGenerationModelConfig('research', value) }
].map(item => ({ capability: 'text_generate', ...item, modelId: '', savedId: '', loading: true, saving: false, error: '', saveError: '' })))
function unavailable(item) { return !!item.modelId && !props.loading && !props.modelError && !availableModels(item).some(model => String(model.modelId) === item.modelId) }
function settingError(error, fallback) {
 const message = error?.msg || error?.message
 return typeof message === 'string' && /[\u3400-\u9fff]/.test(message) ? message : fallback
}
async function load(item) {
 if (item.saving) return
 item.loading = true; item.error = ''
 try {
  const response = await item.read()
  if (!response.data || !Object.hasOwn(response.data, 'modelId')) throw new Error('模型配置响应无效')
  item.modelId = item.savedId = response.data.modelId == null ? '' : String(response.data.modelId)
 } catch (error) { item.error = settingError(error, `${item.label}读取失败，请重试。`) }
 finally { item.loading = false }
}
async function save(item) {
 if (!props.editable || props.loading || props.modelError || item.loading || item.error || item.saving || item.modelId === item.savedId) return
 item.saveError = ''
 if (unavailable(item)) { item.saveError = `请选择已启用的${item.capability === 'image_generate' ? '图片生成' : '文本'}模型`; return }
 item.saving = true
 const selection = item.modelId
 try { await item.write({ modelId: selection || null }); item.savedId = selection; ElMessage.success(`${item.label}已保存`) }
 catch (error) { item.saveError = settingError(error, `${item.label}保存失败，请重试。`) }
 finally { item.saving = false }
}
onMounted(() => Promise.all(purposes.map(load)))
</script>
<style scoped>
.model-purpose-settings { margin-top: 0; border: 1px solid var(--el-border-color-light); border-radius: 8px; background: var(--el-bg-color); }
.model-purpose-settings > .el-alert { width: auto; margin: 16px 24px 0; }
.model-purpose-settings > header { padding: 18px 24px; border-bottom: 1px solid var(--el-border-color-lighter); }
h2, h3, p { margin: 0; }
h2 { font-size: 16px; font-weight: 600; }
h3 { font-size: 14px; font-weight: 600; }
p { color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.65; margin-top: 6px; }
.model-purpose-row { display: grid; grid-template-columns: minmax(220px, 1fr) minmax(270px, 380px); gap: 12px 28px; align-items: center; padding: 20px 24px; }
.model-purpose-row + .model-purpose-row { border-top: 1px solid var(--el-border-color-lighter); }
.model-purpose-control { display: flex; align-items: center; gap: 12px; min-width: 0; }
.model-purpose-control .el-select { flex: 1; min-width: 0; }
.model-purpose-control :deep(.el-select__wrapper) { min-height: 40px; }
.model-purpose-control .el-button { height: 40px; margin: 0; }
.model-purpose-hint { grid-column: 1 / -1; margin: 0; }
.model-purpose-error { grid-column: 1 / -1; margin: 0; color: var(--el-color-danger); }
@media (max-width: 760px) { .model-purpose-row { grid-template-columns: 1fr; padding: 18px; } .model-purpose-settings > header { padding: 18px; } .model-purpose-control :deep(.el-select__wrapper), .model-purpose-control .el-button { min-height: 44px; } }
</style>
