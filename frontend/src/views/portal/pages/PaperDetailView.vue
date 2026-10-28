<template>
  <div class="ps-page ps-reading-page">
    <PortalEmptyState v-if="detailLoading" title="正在加载论文" description="正在读取最新的权限和内容状态。" />
    <PortalEmptyState v-else-if="detailError" title="论文暂时无法读取" :description="detailError" action-label="重新加载" @action="loadPaper" />
    <PortalEmptyState v-else-if="!paper" title="论文不存在" description="该论文记录可能已移除，或当前账号没有访问权限。" action-label="返回论文资料" @action="router.push('/portal/papers')" />
    <template v-else>
    <section class="ps-paper-detail-hero ps-detail-header">
      <div class="ps-detail-title-row"><el-button class="ps-detail-back-button" plain :icon="Back" aria-label="返回" title="返回" @click="returnFromPaperDetail(router)" /><h1>{{ paper.titleZh }}</h1></div>
      <p v-if="originalTitle" class="ps-paper-original-title">{{ originalTitle }}</p>
      <p v-if="paper.authors?.length" class="ps-paper-detail-authors"><span>作者</span>{{ paper.authors.join(' · ') }}</p>
      <p v-if="paperInstitutions.length" class="ps-paper-detail-institutions"><span>机构</span>{{ paperInstitutions.join('；') }}</p>
      <div class="ps-detail-info-row">
      <div class="ps-paper-detail-meta"><span>{{ paper.journal }}</span><span>{{ paper.publishedDate || paper.year }}</span><a v-if="doiUrl" :href="doiUrl" class="ps-paper-doi-link" target="_blank" rel="noopener noreferrer">DOI {{ paper.doi }}</a><span v-else-if="paper.doi && paper.doi !== '待补充'">DOI {{ paper.doi }}</span><a v-if="!doiUrl && sourceUrl" :href="sourceUrl" class="ps-paper-doi-link" target="_blank" rel="noopener noreferrer">{{ sourceUrl }}</a><span v-if="paper.citations != null">被引 {{ paper.citations }} 次</span></div>
      <div class="ps-article-actions">
        <el-button type="primary" :loading="busy(paper)" :disabled="busy(paper)" @click="add"><Collection />{{ inBasket(paper) ? '取消加入资料库' : '加入资料库' }}</el-button>
      </div>
      </div>
    </section>
    <div class="ps-reading-layout" >
      <article class="ps-paper-detail-body">
        <nav class="ps-tabs-line"><button v-for="tab in tabs" :key="tab" type="button" :class="{ 'is-active': activeTab === tab }" @click="activeTab = tab">{{ tab }}</button></nav>
        <section v-if="activeTab === '摘要'" class="ps-paper-section"><p>{{ paper.abstract || '摘要未提供' }}</p><h3 v-if="paper.keywords?.length">关键词</h3><div class="ps-tag-row"><span v-for="tag in paper.keywords" :key="tag" class="ps-tag">{{ tag }}</span></div></section>
        <section v-else-if="activeTab === 'AI解读'" class="ps-paper-section"><h2>AI 解读</h2><div v-if="aiInterpretation.length" class="ps-insight-list"><article v-for="(item, index) in aiInterpretation" :key="`${item.title}-${index}`"><span>{{ String(index + 1).padStart(2, '0') }}</span><div><strong>{{ item.title }}</strong><p>{{ item.content }}</p></div></article></div><p v-else class="ps-inspector-empty">暂无 AI 解读，当前仅展示论文元数据与摘要。</p></section>
      </article>
      <aside class="ps-reading-aside"><section v-if="newsItems.length" class="ps-panel"><h3>其他新闻资讯</h3><button v-for="item in newsItems.slice(0, 3)" :key="item.id" type="button" class="ps-related-item" @click="openPortalContent(router, `/portal/news/${item.id}`)"><strong>{{ item.title }}</strong><small>{{ item.source }}</small></button></section><section v-if="relatedPapers.length" class="ps-panel"><h3>其他论文</h3><button v-for="item in relatedPapers" :key="item.id" type="button" class="ps-related-item" @click="openPortalContent(router, `/portal/papers/${item.id}`)"><strong>{{ item.titleZh }}</strong><small>{{ item.journal }} · {{ item.year }}</small></button></section></aside>
    </div>
    </template>
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
import { normalizePortalPaper } from '@/store/modules/portal'
import { openPortalContent, returnFromPaperDetail } from '@/utils/portal/openContent'
import PortalEmptyState from '../components/PortalEmptyState.vue'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const { inBasket, busy, toggleBasket } = useListWorkspace(portalStore, { save: savePipelineWorkspaceItem, remove: deletePipelineWorkspaceItem })
const activeTab = ref('摘要')
const livePaper = ref(null)
const detailError = ref('')
const detailLoading = ref(true)
const paper = computed(() => detailError.value ? null : livePaper.value)
const originalTitle = computed(() => {
  const original = String(paper.value?.title || '').trim()
  const normalize = value => String(value || '').replace(/\s+/g, ' ').trim().toLocaleLowerCase()
  return normalize(original) !== normalize(paper.value?.titleZh) ? original : ''
})
const paperInstitutions = computed(() => [...new Set((paper.value?.institutions || [])
  .map(value => String(value || '').trim())
  .filter(value => value && !['来源数据库', '机构待补充', '未提供', '待补充'].includes(value)))])
const tabs = computed(() => aiInterpretation.value.length ? ['摘要', 'AI解读'] : ['摘要'])
const sourceUrl = computed(() => {
 try { const url = new URL(paper.value?.sourceUrl || paper.value?.url || ''); return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : '' } catch { return '' }
})
const doiUrl = computed(() => {
  const doi = String(paper.value?.doi || '').trim().replace(/^doi:\s*/i, '').replace(/^https?:\/\/(?:dx\.)?doi\.org\//i, '')
  if (!/^10\.\d{4,9}\/\S+$/i.test(doi)) return ''
  return `https://doi.org/${doi.split('/').map(encodeURIComponent).join('/')}`
})
const relatedPapers = computed(() => portalStore.paperItems.filter(item => item.id !== paper.value?.id).slice(0, 3))
const newsItems = computed(() => portalStore.newsItems)
function insightText(value) {
  if (Array.isArray(value)) return value.map(item => insightText(item)).filter(Boolean).join('；')
  if (value && typeof value === 'object') return insightText(value.content || value.summary || value.description || value.text || '')
  return value == null ? '' : String(value).trim()
}
const aiInterpretation = computed(() => {
  const current = paper.value || {}
  const value = current.aiInsight || current.ai_insight || current.aiInterpretation || current.ai_interpretation || current.metadata?.aiInsight || current.metadata?.ai_insight
  if (Array.isArray(value)) {
    return value.map((item, index) => {
      if (item && typeof item === 'object') return { title: item.title || item.label || `解读 ${index + 1}`, content: insightText(item.content || item.summary || item.description || item.text) }
      return { title: `解读 ${index + 1}`, content: insightText(item) }
    }).filter(item => item.content)
  }
  if (value && typeof value === 'object') {
    return Object.entries(value).map(([title, content]) => ({ title, content: insightText(content) })).filter(item => item.content)
  }
  return insightText(value) ? [{ title: 'AI 解读', content: insightText(value) }] : []
})
async function add() {
  if (!paper.value) return
  try {
    const result = await toggleBasket(paper.value, 'paper')
    if (result === 'saved') ElMessage.success('已加入资料库')
    else if (result === 'removed') ElMessage.success('已取消加入资料库')
  } catch (error) { ElMessage.error(error?.msg || '资料库更新失败，请重试') }
}
let detailRequest = 0
async function loadPaper() {
  const request = ++detailRequest
  activeTab.value = '摘要'
  detailLoading.value = true
  livePaper.value = null
  detailError.value = ''
  try {
    const res = await getPipelineIntelligenceDetail(route.params.itemId)
    if (request !== detailRequest) return
    const payload = res.data?.data || res.data
    if (payload?.id && payload.category === 'paper') {
      livePaper.value = normalizePortalPaper(payload)
      activeTab.value = '摘要'
    }
    else detailError.value = '该论文记录不存在或当前账号没有访问权限。'
  } catch (error) {
    if (request !== detailRequest) return
    detailError.value = error?.msg || '论文详情加载失败，请确认后端服务和访问权限。'
  } finally {
    if (request === detailRequest) detailLoading.value = false
  }
}
onMounted(loadPaper)
watch(() => route.params.itemId, loadPaper)
</script>

<style scoped>
.ps-paper-detail-hero { padding: 22px 28px; margin-bottom: 16px; }
.ps-paper-doi-link { color: var(--ps-blue); text-decoration: none; overflow-wrap: anywhere; }
.ps-paper-doi-link:hover { text-decoration: underline; }
.ps-paper-doi-link:focus-visible { outline: 2px solid var(--ps-blue); outline-offset: 2px; }
.ps-paper-detail-hero h1 { margin: 0; font-size: 24px; font-weight: 600; line-height: 1.45; letter-spacing: 0; overflow-wrap: anywhere; }
.ps-paper-detail-authors, .ps-paper-detail-institutions { margin: 8px 0; color: var(--ps-muted); font-size: 14px; line-height: 1.7; overflow-wrap: anywhere; }
.ps-paper-detail-authors > span, .ps-paper-detail-institutions > span { margin-right: 12px; color: var(--ps-ink-2); }
@media (max-width: 600px) {
  .ps-paper-detail-hero { padding: 16px 18px; }
  .ps-paper-detail-hero h1 { font-size: 20px; }
}
</style>
