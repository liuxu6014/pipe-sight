<template>
  <div class="ps-page ps-reading-page">
    <div class="ps-breadcrumb"><button type="button" @click="router.push('/portal')">首页</button><span>/</span><button type="button" @click="router.push('/portal/news')">科技资讯</button><span>/</span><b>资讯详情</b></div>
    <PortalEmptyState v-if="!article" title="资讯不存在" description="该资讯可能已下线，或当前账号没有访问权限。" action-label="返回科技资讯" @action="router.push('/portal/news')" />
    <div v-else class="ps-reading-layout">
      <article class="ps-article">
        <header class="ps-article-head">
          <div class="ps-article-flags"><span>{{ article.sourceType }}</span><span class="ps-importance is-key">{{ article.importance }}</span></div>
          <h1>{{ article.title }}</h1>
          <div class="ps-article-meta">
            <span>{{ article.source }}</span><span>{{ article.time }}</span><span>{{ article.category }}</span>
            <a v-if="articleUrl" :href="articleUrl" target="_blank" rel="noopener noreferrer">查看原文 <TopRight /></a>
            <span v-else class="ps-source-link is-disabled" title="当前资讯未提供原文链接">暂无原文链接</span>
          </div>
          <div class="ps-article-actions"><el-button :type="portalStore.isFavorite(article.id) ? 'primary' : 'default'" @click="portalStore.toggleFavorite(article.id)"><Star />{{ portalStore.isFavorite(article.id) ? '已收藏' : '收藏' }}</el-button><el-button @click="addToBasket"><Collection />加入资料篮</el-button><el-button @click="copySummary"><DocumentCopy />复制摘要</el-button><el-button type="primary" @click="router.push('/portal/research/create')"><EditPen />引用到报告</el-button></div>
        </header>
        <section id="article-summary" class="ps-ai-summary"><div><MagicStick /></div><span><strong>内容摘要</strong><p>{{ article.summary }}</p></span></section>
        <div class="ps-impact-grid"><section id="article-impact"><span>业务影响</span><strong>可提升缺陷复核与维修排序效率</strong><p>建议纳入完整性评价和开挖验证方案论证。</p></section><section id="article-tech"><span>技术要点</span><strong>统一时空基准与多源特征融合</strong><p>重点关注数据质量分级和结果可解释性。</p></section></div>
        <div class="ps-article-body">
          <p v-for="paragraph in article.body" :key="paragraph">{{ paragraph }}</p>
          <h2 id="article-insight">项目启示</h2>
          <p>建议以可追溯证据链为基础开展工程验证，明确数据适用边界、人工复核节点和技术评价指标，避免将实验室模型精度直接等同于工程应用效果。</p>
        </div>
        <div class="ps-tag-row"><span v-for="tag in article.tags" :key="tag" class="ps-tag">{{ tag }}</span></div>
      </article>
      <aside class="ps-reading-aside">
        <section class="ps-panel ps-article-toc"><h3>文章目录</h3><a href="#article-summary">内容摘要</a><a href="#article-impact">业务影响</a><a href="#article-tech">技术要点</a><a href="#article-insight">项目启示</a></section>
        <section class="ps-panel"><h3>相关资讯</h3><button v-for="item in relatedNews" :key="item.id" type="button" class="ps-related-item" @click="router.push(`/portal/news/${item.id}`)"><strong>{{ item.title }}</strong><small>{{ item.source }} · {{ item.time.slice(5, 10) }}</small></button></section>
        <section class="ps-panel"><h3>相关论文</h3><button v-for="paper in paperItems.slice(0, 2)" :key="paper.id" type="button" class="ps-related-item" @click="router.push(`/portal/papers/${paper.id}`)"><strong>{{ paper.titleZh }}</strong><small>{{ paper.journal }} · {{ paper.year }}</small></button></section>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Collection, DocumentCopy, EditPen, MagicStick, Star, TopRight } from '@element-plus/icons-vue'
import usePortalStore from '@/store/modules/portal'
import PortalEmptyState from '../components/PortalEmptyState.vue'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const article = computed(() => portalStore.newsItems.find(item => item.id === route.params.itemId) || null)
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
function addToBasket() { ElMessage.success(portalStore.addToBasket(article.value) ? '已加入资料篮' : '资料已在资料篮中') }
async function copySummary() {
  const text = `${article.value.title}\n\n${article.value.summary}\n\n来源：${article.value.source} ${article.value.time}`
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
</script>
