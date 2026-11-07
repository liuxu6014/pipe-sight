<template>
  <div class="ps-chapter-prompt">
    <label :for="`research-chapter-prompt-${index}`">本章写作提示词<span>按需修改</span></label>
    <el-input :id="`research-chapter-prompt-${index}`" :model-value="modelValue || ''" @update:model-value="$emit('update:modelValue', $event)" type="textarea" :autosize="{ minRows: 3, maxRows: 8 }" :maxlength="3000" show-word-limit :aria-label="`第 ${index + 1} 章写作提示词`" placeholder="填写本章重点分析的问题、论证方式或格式要求；留空时沿用模板章节要求。" />
  </div>
</template>

<script setup>
defineProps({ modelValue: String, index: { type: Number, required: true } })
defineEmits(['update:modelValue'])
</script>

<style scoped>
.ps-chapter-prompt { min-width: 0; }
label { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; color: var(--ps-ink); font-size: 14px; font-weight: 500; }
label > span { color: var(--ps-muted); font-size: 12px; font-weight: 400; }
</style>
