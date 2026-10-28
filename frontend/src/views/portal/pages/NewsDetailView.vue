<template>
  <div class="ps-page ps-reading-page">
    <PortalEmptyState v-if="detailLoading" title="正在加载资讯" description="正在读取最新的权限和内容状态。" />
    <PortalEmptyState v-else-if="detailError" title="资讯暂时无法读取" :description="detailError" action-label="重新加载" @action="loadArticle" />
    <PortalEmptyState v-else-if="!article" title="资讯不存在" description="该资讯可能已下线，或当前账号没有访问权限。" action-label="返回科技资讯" @action="router.push('/portal/news')" />
    <div v-else class="ps-reading-layout">
      <article class="ps-article">
        <header class="ps-article-head ps-detail-header">
          <div class="ps-detail-title-row"><el-button class="ps-detail-back-button" plain :icon="Back" aria-label="返回" title="返回" @click="returnFromNewsDetail(router)" /><h1><a v-if="articleUrl" :href="articleUrl" target="_blank" rel="noopener noreferrer" title="打开原文（新窗口）">{{ article.title }}</a><template v-else>{{ article.title }}</template></h1></div>
          <div class="ps-detail-info-row">
          <div class="ps-article-meta">
            <span class="ps-article-source">{{ article.source }}</span><time>{{ newsDate(article.time) }}</time>
            <div class="ps-article-flags"><span>{{ article.sourceType }}</span></div>
          </div>
          <div class="ps-article-actions"><el-button :loading="busy(article)" :disabled="busy(article)" @click="addToBasket"><Collection />{{ inBasket(article) ? '取消加入资料库' : '加入资料库' }}</el-button></div>
          </div>
          <div v-if="article.tags.length" class="ps-article-head-bottom">
          <div class="ps-tag-row"><span v-for="tag in article.tags" :key="tag" class="ps-tag">{{ tag }}</span></div>
          </div>
        </header>
        <section v-if="showSummary" id="article-summary" class="ps-ai-summary" role="button" tabindex="0" aria-label="复制文章摘要，双击或按回车、空格键" title="双击复制摘要" @dblclick="copySummary" @keydown.enter.prevent="copySummary" @keydown.space.prevent="copySummary"><p>{{ summaryText }}</p></section>
        <div v-if="articleAnalysis.length" class="ps-impact-grid"><section v-for="item in articleAnalysis" :id="item.id" :key="item.id"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></section></div>
        <div class="ps-article-body">
          <template v-if="article.body_blocks?.length">
            <template v-for="(block, index) in article.body_blocks" :key="index">
              <p v-if="block.type === 'paragraph'">{{ block.text }}</p>
              <img v-else-if="block.type === 'image'" :src="block.src" :alt="block.alt || '文章配图'" loading="lazy" style="display: block; max-width: 100%; height: auto; margin: 20px auto;" />
            </template>
          </template>
          <template v-else><p v-for="paragraph in article.body" :key="paragraph">{{ paragraph }}</p></template>
        </div>
      </article>
      <aside class="ps-reading-aside">
        <section v-if="articleAnalysis.length" class="ps-panel ps-article-toc"><h3>文章目录</h3><a v-if="showSummary" href="#article-summary">内容摘要</a><a v-for="item in articleAnalysis" :key="item.id" :href="'#' + item.id">{{ item.label }}</a></section>
        <section v-if="relatedNews.length" class="ps-panel"><h3>其他资讯</h3><button v-for="item in relatedNews" :key="item.id" type="button" class="ps-related-item" @click="openPortalContent(router, `/portal/news/${item.id}`)"><strong>{{ item.title }}</strong><small>{{ item.source }}<template v-if="item.time"> · {{ newsDate(item.time) }}</template></small></button></section>
        <section v-if="paperItems.length" class="ps-panel"><h3>其他论文</h3><button v-for="paper in paperItems.slice(0, 2)" :key="paper.id" type="button" class="ps-related-item" @click="openPortalContent(router, `/portal/papers/${paper.id}`)"><strong>{{ paper.titleZh }}</strong><small>{{ paper.journal }} · {{ paper.year }}</small></button></section>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back, Collection } from '@element-plus/icons-vue'
import usePortalStore from '@/store/modules/portal'
import { getPipelineIntelligenceDetail, savePipelineWorkspaceItem, deletePipelineWorkspaceItem } from '@/api/pipeline/intelligence'
import { useListWorkspace } from '@/utils/portal/listQuery'
import { normalizePortalIntelligence } from '@/store/modules/portal'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import { newsDate } from '@/utils/portal/discovery'
import { openPortalContent, returnFromNewsDetail } from '@/utils/portal/openContent'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const { inBasket, busy, toggleBasket } = useListWorkspace(portalStore, { save: savePipelineWorkspaceItem, remove: deletePipelineWorkspaceItem })
const liveArticle = ref(null)
const detailError = ref('')
const detailLoading = ref(true)
const article = computed(() => detailError.value ? null : liveArticle.value)
const summaryText = computed(() => (article.value?.summary || '').replace(/^导读摘要（据公开资料整理）\s*[:：]\s*/, ''))
const showSummary = computed(() => {
  const normalize = value => String(value || '').replace(/\s+/g, '')
  const body = article.value?.body_blocks?.filter(block => block.type === 'paragraph').map(block => block.text).join('') || article.value?.body?.join('') || ''
  return Boolean(summaryText.value && !normalize(body).startsWith(normalize(summaryText.value)))
})
const articleUrl = computed(() => {
  const value = article.value?.sourceUrl || article.value?.source_url || article.value?.originalUrl || article.value?.original_url || article.value?.url || article.value?.link
  if (!value) return ''
  try {
    const target = new URL(value, window.location.origin)
    return ['http:', 'https:'].includes(target.protocol) ? target.href : ''
  } catch (error) {
    return ''
  }
})
const relatedNews = computed(() => portalStore.newsItems.filter(item => item.id !== article.value?.id).slice(0, 3))
const paperItems = computed(() => portalStore.paperItems)
function asText(value) {
  if (Array.isArray(value)) return value.map(item => asText(item)).filter(Boolean).join('；')
  if (value && typeof value === 'object') return asText(value.summary || value.content || value.description || value.text || '')
  return value == null ? '' : String(value).trim()
}
const articleAnalysis = computed(() => {
  const current = article.value || {}
  return [
    { id: 'article-impact', label: '业务影响', value: asText(current.businessImpact || current.business_impact || current.impact) },
    { id: 'article-tech', label: '技术要点', value: asText(current.technicalPoints || current.technical_points || current.technicalSummary || current.technical_summary) }
  ].filter(item => item.value)
})
async function loadArticle() {
  detailLoading.value = true
  liveArticle.value = null
  detailError.value = ''
  try {
    const res = await getPipelineIntelligenceDetail(route.params.itemId)
    const payload = res.data?.data || res.data
    if (payload?.id && payload.category !== 'paper') liveArticle.value = normalizePortalIntelligence(payload)
    else detailError.value = '该资讯记录不存在或当前账号没有访问权限。'
  } catch (error) {
    detailError.value = error?.msg || '资讯详情加载失败，请确认后端服务和访问权限。'
  } finally {
    detailLoading.value = false
  }
}
async function addToBasket() {
  if (!article.value) return
  try {
    const result = await toggleBasket(article.value, 'article')
    if (result === 'saved') ElMessage.success('已加入资料库')
    else if (result === 'removed') ElMessage.success('已取消加入资料库')
  } catch (error) { ElMessage.error(error?.msg || '资料库更新失败，请重试') }
}
async function copySummary() {
  const text = `${article.value.title}\n\n${summaryText.value}\n\n来源：${article.value.source} ${article.value.time}`
  try {
    let copiedWithClipboard = false
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text)
        copiedWithClipboard = true
      } catch (error) {
        copiedWithClipboard = false
      }
    }
    if (!copiedWithClipboard) {
      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.setAttribute('readonly', '')
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      const copied = document.execCommand('copy')
      textarea.remove()
      if (!copied) throw new Error('copy failed')
    }
    ElMessage.success('资讯摘要已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败，请手动选择摘要内容')
  }
}
onMounted(loadArticle)
watch(() => route.params.itemId, loadArticle)
</script>

<style scoped>
.ps-article { padding-top: 22px; }
.ps-article-head h1 { margin: 0; font-size: 24px; font-weight: 600; line-height: 1.45; letter-spacing: 0; overflow-wrap: anywhere; }
@media (max-width: 600px) {
  .ps-article { padding-top: 16px; }
  .ps-article-head h1 { font-size: 20px; }
}
</style>
