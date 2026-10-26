<template>
  <div class="ps-diagram-page">
    <header class="ps-diagram-topbar">
      <div class="ps-editor-title"><button type="button" aria-label="返回报告" @click="router.back()"><ArrowLeft /></button><span><strong>报告配图</strong><small>图片由后台配置的生图模型生成</small></span></div>
    </header>
    <main class="ps-image-assets-page"><ReportImageAssets :report-id="String(route.params.id)" /></main>
  </div>
</template>
<script setup>
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import ReportImageAssets from '../components/ReportImageAssets.vue'
const route = useRoute()
const router = useRouter()
</script>
<style scoped>
.ps-image-assets-page { max-width: 1200px; margin: 0 auto; padding: 16px; }
</style>
