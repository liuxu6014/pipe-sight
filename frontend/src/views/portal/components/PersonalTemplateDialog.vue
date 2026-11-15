<template>
  <el-button plain @click="open = true">管理我的模板</el-button>
  <el-dialog v-model="open" title="我的模板" width="min(1100px, calc(100vw - 32px))" align-center append-to-body destroy-on-close class="personal-template-dialog">
    <p>模板仅自己可见。添加内置模板会创建个人副本，保留您已保存的修改。</p>
    <TemplateManager personal @changed="$emit('changed')" />
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import TemplateManager from '@/views/pipeline/template/index.vue'
defineEmits(['changed'])
const open = ref(false)
</script>

<style scoped>
:deep(.pipeline-template-page) { height: min(65vh, 720px); padding: 0; background: transparent; }
</style>
