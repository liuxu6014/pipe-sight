<template>
  <div class="ps-empty-state">
    <div class="ps-empty-icon"><DocumentRemove /></div>
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>
    <el-button v-if="actionLabel" type="primary" @click="$emit('action')">{{ actionLabel }}</el-button>
  </div>
</template>

<script setup>
import { DocumentRemove } from '@element-plus/icons-vue'

defineProps({
  title: { type: String, default: '暂无内容' },
  description: { type: String, default: '当前条件下没有可展示的数据。' },
  actionLabel: { type: String, default: '' }
})

defineEmits(['action'])
</script>
