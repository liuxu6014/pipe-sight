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
            <span class="ps-article-source">{{ article.source }}</span><time>发布于 {{ newsDate(article.time) }}</time><span v-if="article.author">作者 {{ article.author }}</span>
            <div class="ps-article-flags"><span>{{ article.sourceType }}</span></div>
          </div>
          <div class="ps-article-actions"><el-button :icon="Collection" :loading="busy(article)" :disabled="busy(article)" @click="addToBasket">{{ inBasket(article) ? '取消加入资料库' : '加入资料库' }}</el-button></div>
          </div>
          <div v-if="article.tags.length" class="ps-article-head-bottom">
          <div class="ps-tag-row"><span v-for="tag in article.tags" :key="tag" class="ps-tag">{{ tag }}</span></div>
          </div>
          <el-tag v-if="categoryName && !article.tags.includes(categoryName)" effect="plain">{{ categoryName }}</el-tag>
        </header>
        <el-tabs v-model="activeTab" class="ps-content-tabs" aria-label="资讯内容切换">
          <el-tab-pane label="摘要" name="summary"><section id="article-summary" class="ps-news-summary"><div class="summary-heading"><h2>内容摘要</h2><el-button v-if="summaryText" plain @click="copySummary">复制摘要</el-button></div><p>{{ summaryText || '当前记录暂未提供摘要。' }}</p></section></el-tab-pane>
          <el-tab-pane label="全文" name="fulltext"><div class="ps-translation-toolbar"><el-radio-group v-if="content.hasTranslation" v-model="language" aria-label="文章语言"><el-radio-button value="original">原文</el-radio-button><el-radio-button value="zh">已保存中文</el-radio-button></el-radio-group><el-tooltip v-else content="按需翻译与结果入库接口待接入；不会自动翻译或覆盖原文。"><span><el-button disabled plain>翻译为中文 · 待接入</el-button></span></el-tooltip></div>
        <div class="ps-article-body">
          <template v-if="language === 'original' && article.body_blocks?.length">
            <template v-for="(block, index) in article.body_blocks" :key="index">
              <p v-if="block.type === 'paragraph'">{{ block.text }}</p>
              <img v-else-if="block.type === 'image'" :src="block.src" :alt="block.alt || '文章配图'" loading="lazy" style="display: block; max-width: 100%; height: auto; margin: 20px auto;" />
            </template>
          </template>
          <template v-else><p v-for="(paragraph, index) in visibleBody" :key="index">{{ paragraph }}</p><el-empty v-if="!visibleBody.length" description="当前资料未提供全文，可查看摘要或打开标题原文。" :image-size="64" /></template>
        </div>
          </el-tab-pane>
          <el-tab-pane label="官网洞察" name="insight"><ContentInsights :item="article" /></el-tab-pane>
        </el-tabs>
        <ContentEntities :entities="article.entities" />
      </article>
      <aside class="ps-reading-aside">
        <section class="ps-panel ps-article-toc"><h3>阅读导航</h3><el-button plain @click="activeTab = 'summary'">内容摘要</el-button><el-button plain @click="activeTab = 'fulltext'">文章全文</el-button><el-button plain @click="activeTab = 'insight'">官网洞察</el-button></section>
        <section v-if="relatedNews.length" class="ps-panel"><h3>其他资讯</h3><el-link underline="never" :href="$router.resolve(`/portal/news/${item.id}` || '/portal').href" v-for="item in relatedNews" :key="item.id" class="ps-related-item ps-ui-title" @click.prevent="openPortalContent(router, `/portal/news/${item.id}`)"><strong>{{ item.title }}</strong><small>{{ item.source }}<template v-if="item.time"> · {{ newsDate(item.time) }}</template></small></el-link></section>
        <section v-if="paperItems.length" class="ps-panel"><h3>其他论文</h3><el-link underline="never" :href="$router.resolve(`/portal/papers/${paper.id}` || '/portal').href" v-for="paper in paperItems.slice(0, 2)" :key="paper.id" class="ps-related-item ps-ui-title" @click.prevent="openPortalContent(router, `/portal/papers/${paper.id}`)"><strong>{{ paper.titleZh }}</strong><small>{{ paper.journal }} · {{ paper.year }}</small></el-link></section>
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
import ContentEntities from '../components/ContentEntities.vue'
import ContentInsights from '../components/ContentInsights.vue'
import { contentCategory, readingContent } from '@/utils/portal/contentPresentation'
import { newsDate } from '@/utils/portal/discovery'
import { openPortalContent, returnFromNewsDetail } from '@/utils/portal/openContent'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const { inBasket, busy, toggleBasket } = useListWorkspace(portalStore, { save: savePipelineWorkspaceItem, remove: deletePipelineWorkspaceItem })
const liveArticle = ref(null)
const detailError = ref('')
const detailLoading = ref(true)
const activeTab = ref('summary')
const language = ref('original')
const article = computed(() => detailError.value ? null : liveArticle.value)
const categoryName = computed(() => contentCategory(article.value || {}))
const content = computed(() => readingContent(article.value || {}))
const visibleBody = computed(() => language.value === 'zh' ? content.value.translated : content.value.original)
const summaryText = computed(() => (article.value?.summary || '').replace(/^导读摘要（据公开资料整理）\s*[:：]\s*/, ''))
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
let detailRequest = 0
async function loadArticle() {
  const request = ++detailRequest
  activeTab.value = 'summary'
  language.value = 'original'
  detailLoading.value = true
  liveArticle.value = null
  detailError.value = ''
  try {
    const res = await getPipelineIntelligenceDetail(route.params.itemId)
    if (request !== detailRequest) return
    const payload = res.data?.data || res.data
    if (payload?.id && payload.category !== 'paper') liveArticle.value = normalizePortalIntelligence(payload)
    else detailError.value = '该资讯记录不存在或当前账号没有访问权限。'
  } catch (error) {
    if (request !== detailRequest) return
    detailError.value = error?.msg || '资讯详情加载失败，请确认后端服务和访问权限。'
  } finally {
    if (request === detailRequest) detailLoading.value = false
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
.ps-content-tabs { margin-top: 16px; }.ps-news-summary { padding: 16px 18px; background: var(--ps-blue-soft); border-radius: 8px; }.summary-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }.summary-heading h2 { margin: 0; font-size: 16px; }.ps-news-summary p { line-height: 1.9; white-space: pre-wrap; margin: 12px 0 0; }.ps-translation-toolbar { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; }
.ps-article { padding-top: 22px; }
.ps-article-head h1 { margin: 0; font-size: 24px; font-weight: 600; line-height: 1.45; letter-spacing: 0; overflow-wrap: anywhere; }
@media (max-width: 600px) {
  .ps-article { padding-top: 16px; }
  .ps-article-head h1 { font-size: 20px; }
}
</style>
