<template>
  <span class="ps-category-badge" :class="{ 'is-empty': !category }" :aria-label="`分类：${category || '未分类'}`" :title="category || '该内容尚未保存分类结果'">
    <el-icon aria-hidden="true"><CollectionTag /></el-icon>
    <span>{{ category || '未分类' }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { CollectionTag } from '@element-plus/icons-vue'
const props = defineProps({ name: { type: String, default: '' } })
const category = computed(() => props.name.trim())
</script>

<style scoped>
.ps-category-badge { display: inline-flex; align-items: center; gap: 6px; box-sizing: border-box; max-width: 100%; min-height: 28px; padding: 4px 10px; border-radius: 6px; background: #edf4ff; color: #245ca6; font-size: 13px; font-weight: 500; line-height: 20px; vertical-align: middle; }
.ps-category-badge > .el-icon { flex: 0 0 14px; font-size: 14px; }
.ps-category-badge > span { min-width: 0; overflow-wrap: anywhere; }
.ps-category-badge.is-empty { background: #f1f3f6; color: #5f6b7a; font-weight: 400; }
</style>
