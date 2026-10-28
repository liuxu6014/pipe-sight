<template>
  <section class="ps-report-images" aria-label="报告生成配图" :aria-busy="loading">
    <div class="ps-image-assets-heading"><h3>生成配图</h3><el-button plain :loading="loading" @click="load">刷新配图</el-button></div>
    <el-alert v-if="loadError" :title="loadError" type="warning" :closable="false" show-icon />
    <el-alert v-if="actionError" :title="actionError" type="error" :closable="false" show-icon />
    <p v-if="loading && !images.length" role="status">正在加载配图资源…</p>
    <p v-else-if="!loadError && !images.length" role="status">尚无配图。请管理员在模板中选择具备图片生成能力的模型并启用配图，生成后在此查看。</p>
    <figure v-for="(image, index) in images" :key="image.id" class="ps-report-image">
      <figcaption><strong>{{ image.position ? `位置 ${image.position}` : `配图 ${index + 1}` }}</strong><span>{{ imageStatusLabel(image.status) }}</span></figcaption>
      <template v-if="image.status === 'completed'">
        <img v-if="image.imageUrl && !image.imageError" :src="image.imageUrl" :alt="`报告配图 ${image.position || index + 1}`" @error="image.imageError = '图片无法解码，请重新加载图片'" />
        <p v-else-if="image.imageLoading" role="status">正在读取图片…</p>
        <p v-if="image.imageError" role="alert">{{ image.imageError }} <el-button plain @click="reloadImage(image)">重新加载图片</el-button></p>
        <a v-if="image.imageUrl && !image.imageError" :href="image.imageUrl" :download="`${image.id}.${image.extension}`">下载图片</a>
      </template>
      <p v-else-if="image.status === 'failed'" role="alert">{{ image.error || '配图生成失败，请检查后台图片模型配置。' }} <el-button plain type="warning" :loading="image.retrying" @click="retry(image)">重试此图</el-button></p>
      <p v-else role="status">配图{{ imageStatusLabel(image.status) }}，状态将自动刷新。</p>
    </figure>
  </section>
</template>
<script setup>
import { getPipelineResearchReportDiagram } from '@/api/pipeline/intelligence'
import { getReportImageBlob, retryReportImage } from '@/api/pipeline/assets'
import { imageStatusLabel, useReportImages } from '@/utils/portal/reportImages'
import usePortalStore from '@/store/modules/portal'
const props = defineProps({ reportId: { type: String, required: true } })
const store = usePortalStore()
const { images, loading, loadError, actionError, load, retry, reloadImage } = useReportImages(() => props.reportId, {
  getMetadata: getPipelineResearchReportDiagram, getImage: getReportImageBlob, retry: retryReportImage
}, { epoch: () => store.workspaceEpoch })
</script>
<style scoped>
.ps-report-images { padding: 18px; border: 1px solid var(--ps-line); border-radius: 8px; background: #fff; }
.ps-image-assets-heading, figcaption { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
h3 { margin: 0; font-size: 16px; }
.ps-report-image { margin: 16px 0 0; padding-top: 14px; border-top: 1px solid var(--ps-line); }
figcaption span, p { color: var(--ps-muted); font-size: 13px; line-height: 1.7; }
img { display: block; max-width: 100%; height: auto; margin: 12px auto; }
a { display: inline-block; color: var(--ps-blue); margin-top: 8px; }
</style>
