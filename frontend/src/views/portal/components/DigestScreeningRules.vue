<template>
  <section class="digest-rules" aria-label="类别筛选规则">
    <div class="rule-general">
      <header class="rule-toolbar">
        <h3><label :for="readonly ? undefined : generalInputId">通用筛选要求</label></h3>
        <el-button type="primary" plain :icon="View" aria-haspopup="dialog" :disabled="Boolean(error)" @click="previewOpen = true">预览总提示词</el-button>
      </header>
      <p v-if="readonly" class="rule-general-text">{{ effectivePrompt || '使用系统默认规则' }}</p>
      <el-input v-else :id="generalInputId" :model-value="prompt" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }"
        maxlength="5000" :placeholder="defaultPrompt || '填写适用于所有类别的纳入或排除条件'" @update:model-value="emit('update:prompt', $event)" />
    </div>
    <header class="rule-toolbar">
      <h3>类别筛选规则</h3>
      <div class="rule-actions">
        <slot name="actions" />
        <el-button v-if="!readonly" :icon="Plus" :disabled="categories.length >= 30" @click="addCategory">添加类别</el-button>
      </div>
    </header>

    <div v-if="categories.length" class="rule-list" :class="{ 'is-readonly': readonly }">
      <div class="rule-columns" aria-hidden="true"><span>序号</span><span>类别名称</span><span>筛选提示词</span></div>
      <Draggable :model-value="categories" :item-key="ruleKey" handle=".rule-grip" ghost-class="rule-drop-target"
        :disabled="readonly || categories.length < 2" @update:model-value="emit('update:categories', $event)">
        <template #item="{ element: category, index }">
          <div class="rule-row">
            <div class="rule-order">
              <span v-if="readonly || categories.length === 1" class="rule-position">{{ index + 1 }}</span>
              <template v-else>
                <span class="rule-grip" title="拖动调整顺序" aria-hidden="true"><el-icon><Rank /></el-icon></span>
                <select :ref="el => { positionInputs[index] = el }" :value="index + 1"
                  :aria-label="`${category.name || '新类别'}的序号`" title="选择序号"
                  @change="moveCategory(index, Number($event.target.value) - 1)">
                  <option v-for="n in categories.length" :key="n" :value="n">{{ n }}</option>
                </select>
              </template>
            </div>
            <template v-if="readonly">
              <strong>{{ category.name }}</strong><p>{{ category.prompt }}</p>
            </template>
            <template v-else>
              <el-input :ref="el => { nameInputs[index] = el }" :model-value="category.name" :aria-label="`第 ${index + 1} 个类别名称`" placeholder="类别名称" @update:model-value="updateField(index, 'name', $event)" />
              <el-input :model-value="category.prompt" type="textarea" :rows="2" :aria-label="`第 ${index + 1} 个类别筛选提示词`" placeholder="哪些文章应归入此类？" @update:model-value="updateField(index, 'prompt', $event)" />
              <el-button-group class="rule-buttons">
                <el-button :icon="ArrowUp" plain :aria-label="`上移第 ${index + 1} 个类别`" title="上移" :disabled="index === 0" @click="moveCategory(index, index - 1)" />
                <el-button :icon="ArrowDown" plain :aria-label="`下移第 ${index + 1} 个类别`" title="下移" :disabled="index === categories.length - 1" @click="moveCategory(index, index + 1)" />
                <el-button :icon="Delete" plain :aria-label="`删除第 ${index + 1} 个类别`" title="删除类别" @click="removeCategory(index)" />
              </el-button-group>
            </template>
          </div>
        </template>
      </Draggable>
    </div>
    <p v-else class="rule-note">未设置类别，系统按通用要求筛选并判断文章主题。</p>
    <p v-if="error && !readonly" class="rule-error" role="status">{{ error }}</p>

    <el-dialog v-model="previewOpen" title="总提示词预览" width="min(680px, calc(100vw - 32px))" append-to-body align-center>
      <pre class="rule-preview-text" tabindex="0" aria-label="完整筛选提示词">{{ combinedPrompt || '使用系统默认规则' }}</pre>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, nextTick, ref, toRaw, useId } from 'vue'
import Draggable from 'vuedraggable'
import { ArrowDown, ArrowUp, Delete, Plus, Rank, View } from '@element-plus/icons-vue'
import { buildDigestScreeningPrompt, screeningRulesError } from '@/utils/portal/digestScreeningRules'

const props = defineProps({
  categories: { type: Array, default: () => [] },
  prompt: { type: String, default: '' },
  defaultPrompt: { type: String, default: '' },
  readonly: Boolean
})
const emit = defineEmits(['update:categories', 'update:prompt'])
const previewOpen = ref(false)
const generalInputId = useId()
const nameInputs = []
const positionInputs = []
// A row keeps its editor and focus when its name changes or its position moves.
const rowKeys = new WeakMap()
let nextKey = 0
function ruleKey(row) {
  const raw = toRaw(row)
  if (!rowKeys.has(raw)) rowKeys.set(raw, ++nextKey)
  return rowKeys.get(raw)
}
const error = computed(() => screeningRulesError(props.categories))
const effectivePrompt = computed(() => (props.prompt || '').trim() || (props.defaultPrompt || '').trim())
const combinedPrompt = computed(() => error.value ? '' : buildDigestScreeningPrompt(effectivePrompt.value, props.categories))

function updateField(index, field, value) {
  const rows = [...props.categories]
  const updated = { ...rows[index], [field]: value }
  rowKeys.set(updated, ruleKey(rows[index]))
  rows[index] = updated
  emit('update:categories', rows)
}
async function addCategory() {
  const index = props.categories.length
  if (index >= 30) return
  emit('update:categories', [...props.categories, { name: '', prompt: '' }])
  await nextTick()
  nameInputs[index]?.focus()
}
async function moveCategory(index, target) {
  if (props.readonly || target < 0 || target >= props.categories.length || index === target) return
  const rows = [...props.categories]
  const [row] = rows.splice(index, 1)
  rows.splice(target, 0, row)
  emit('update:categories', rows)
  await nextTick()
  positionInputs[target]?.focus()
}
function removeCategory(index) {
  emit('update:categories', props.categories.filter((_, position) => position !== index))
}
</script>

<style scoped>
.digest-rules { min-width: 0; container-type: inline-size; color: var(--el-text-color-primary); }
.rule-general { margin-bottom: 18px; }
.rule-toolbar, .rule-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.rule-toolbar { justify-content: space-between; margin-bottom: 10px; }
.rule-toolbar h3 { margin: 0; font-size: 15px; font-weight: 600; }
.rule-actions :deep(.el-button) { margin: 0; }
.rule-list { --rule-action-width: 90px; }
.rule-columns, .rule-row { display: grid; grid-template-columns: 70px minmax(110px, 1fr) minmax(0, 3fr) var(--rule-action-width); gap: 6px 12px; }
.rule-columns { padding: 7px 10px; background: var(--el-fill-color-lighter); font-size: 12px; color: var(--el-text-color-secondary); }
.rule-row { align-items: start; padding: 8px 10px; border-bottom: 1px solid var(--el-border-color-lighter); }
.rule-order, .rule-buttons { display: flex; align-items: center; min-height: 32px; }
.rule-order { gap: 2px; font-variant-numeric: tabular-nums; }
.rule-order select { color: var(--el-text-color-primary); background: var(--el-fill-color-blank); border: 1px solid var(--el-border-color); border-radius: var(--el-border-radius-base); height: 32px; width: 46px; font: inherit; cursor: pointer; }
.rule-position { color: var(--el-text-color-secondary); }
.rule-grip { display: inline-grid; place-items: center; width: 22px; height: 32px; color: var(--el-text-color-secondary); cursor: grab; touch-action: none; user-select: none; }
.rule-grip:active { cursor: grabbing; }
.rule-drop-target { background: var(--el-color-primary-light-9); box-shadow: inset 3px 0 var(--el-color-primary); }
.rule-buttons :deep(.el-button) { width: 30px; height: 32px; padding: 0; margin: 0; }
.rule-row :deep(.el-textarea__inner) { field-sizing: content; max-height: 9lh; }
.is-readonly :is(.rule-columns, .rule-row) { grid-template-columns: 36px minmax(110px, 1fr) minmax(0, 3fr); }
.rule-row strong, .rule-row p, .rule-general-text, .rule-preview-text { margin: 0; font: inherit; line-height: 1.65; white-space: pre-wrap; overflow-wrap: anywhere; }
.rule-preview-text { max-height: min(60dvh, 34rem); overflow: auto; padding: 14px 16px; border-radius: var(--el-border-radius-base); background: var(--el-fill-color-lighter); color: var(--el-text-color-primary); }
.rule-row strong { font-weight: 600; }
.rule-note, .rule-error { margin: 8px 0; font-size: 13px; color: var(--el-text-color-secondary); }
.rule-error { color: var(--el-color-danger); }
@container (max-width: 560px) {
  .rule-columns { display: none; }
  .rule-row { grid-template-columns: auto minmax(0, 1fr) auto; gap: 6px; padding: 8px 0; }
  .rule-row :deep(.el-textarea) { grid-column: 1 / -1; grid-row: 2; }
  .rule-buttons { grid-column: 3; grid-row: 1; }
  .is-readonly .rule-row { grid-template-columns: auto minmax(0, 1fr); }
  .is-readonly .rule-row > p { grid-column: 2; }
}
@media (pointer: coarse) {
  .rule-toolbar :deep(.el-button) { min-height: 44px; }
  .rule-grip, .rule-order select, .rule-buttons :deep(.el-button) { min-height: 44px; }
  .rule-buttons :deep(.el-button) { width: 44px; }
  .rule-list { --rule-action-width: 132px; }
}
</style>
