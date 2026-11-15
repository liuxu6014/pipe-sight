<template>
  <div class="ps-page ps-personal-templates">
    <header><h1>我的模板</h1><p>模板仅自己可见，可直接用于科研报告和情报简报。</p></header>
    <TemplateManager personal />
  </div>
</template>

<script setup>
import TemplateManager from '@/views/pipeline/template/index.vue'
</script>

<style scoped>
.ps-personal-templates { display: flex; flex-direction: column; gap: 16px; min-height: 0; }
header h1 { margin: 0 0 8px; font-size: 22px; }
header p { margin: 0; color: var(--ps-muted); }
:deep(.pipeline-template-page) { flex: 1; min-height: 0; padding: 0; background: transparent; }
</style>
