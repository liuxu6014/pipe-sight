<template>
  <div class="ps-page ps-list-page ps-personal-templates">
    <TemplateManager personal />
  </div>
</template>

<script setup>
import TemplateManager from '@/views/pipeline/template/index.vue'
</script>

<style scoped>
.ps-personal-templates { min-height: 0; }
:deep(.pipeline-template-page) { flex: 1 1 0; min-height: 0; padding: 0; }
</style>
