<template>
  <div class="ps-empty-state" :class="{ 'is-compact': compact }" role="status">
    <div class="ps-empty-icon" aria-hidden="true"><DocumentRemove /></div>
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>
    <div v-if="actionLabel || secondaryActionLabel" class="ps-empty-actions">
      <el-button v-if="actionLabel" type="primary" @click="$emit('action')">{{ actionLabel }}</el-button>
      <el-button v-if="secondaryActionLabel" @click="$emit('secondary-action')">{{ secondaryActionLabel }}</el-button>
    </div>
  </div>
</template>

<script setup>
import { DocumentRemove } from '@element-plus/icons-vue'

defineProps({
  title: { type: String, default: '暂无内容' },
  description: { type: String, default: '当前条件下没有可展示的数据。' },
  actionLabel: { type: String, default: '' },
  secondaryActionLabel: { type: String, default: '' },
  compact: { type: Boolean, default: false }
})

defineEmits(['action', 'secondary-action'])
</script>
