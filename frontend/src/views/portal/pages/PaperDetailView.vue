<template>
  <div class="ps-page ps-reading-page ps-paper-reading-page">
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
      <div class="ps-paper-detail-meta">
        <el-tag v-if="paper.journal" type="primary" size="small">{{ paper.journal }}</el-tag>
        <span v-if="paper.publishedDate || paper.year">发表于 {{ paper.publishedDate || paper.year }}</span>
        <el-tag :type="contentCategory(paper) ? 'primary' : 'info'" size="small" effect="plain">分类：{{ contentCategory(paper) || '未分类' }}</el-tag>
        <a v-if="doiUrl" :href="doiUrl" class="ps-paper-doi-link" target="_blank" rel="noopener noreferrer">DOI: {{ paper.doi }}</a>
        <span v-else-if="paper.doi && paper.doi !== '待补充'">DOI: {{ paper.doi }}</span>
        <a v-if="!doiUrl && sourceUrl" :href="sourceUrl" class="ps-paper-doi-link" target="_blank" rel="noopener noreferrer">查看原文</a>
        <span v-if="paper.citations != null">被引 {{ paper.citations }} 次</span>
      </div>
      <div class="ps-article-actions">
        <el-button :icon="Collection" type="primary" :loading="busy(paper)" :disabled="busy(paper)" @click="add">{{ inBasket(paper) ? '取消加入资料库' : '加入资料库' }}</el-button>
      </div>
      </div>
    </section>
    <div class="ps-reading-layout" >
      <article class="ps-paper-detail-body">
        <div class="ps-paper-content-toolbar">
          <el-segmented v-model="activeTab" :options="[{ label: '摘要', value: '摘要' }, { label: 'AI 解读', value: 'AI解读' }]" aria-label="论文内容切换" />
          <div v-if="activeTab === '摘要'" class="ps-paper-language">
            <el-radio-group v-if="originalAbstract && translatedAbstract" v-model="abstractLanguage" aria-label="摘要语言">
              <el-radio-button value="original">原文摘要</el-radio-button><el-radio-button value="zh">已保存中文</el-radio-button>
            </el-radio-group>
            <el-tooltip v-if="!translatedAbstract" content="按需翻译和保存接口待接入，不会自动发起翻译。">
              <span tabindex="0" aria-label="翻译为中文，功能待接入"><el-button plain disabled>翻译为中文</el-button></span>
            </el-tooltip>
          </div>
        </div>
        <section v-if="activeTab === '摘要'" class="ps-paper-section" aria-label="论文摘要">
          <p class="ps-paper-abstract">{{ visibleAbstract || '摘要未提供' }}</p>
          <div v-if="paper.keywords?.length" class="ps-paper-detail-keywords"><h3>关键词</h3><div class="ps-tag-row"><el-tag v-for="tag in paper.keywords" :key="tag" effect="plain">{{ tag }}</el-tag></div></div>
        </section>
        <section v-else class="ps-paper-section ps-paper-insights" aria-label="论文 AI 解读"><ContentInsights :item="paper" kind="paper" /></section>
        <ContentEntities v-if="paper.entities?.length" class="ps-paper-core-entities" :entities="paper.entities" />
      </article>
      <aside class="ps-reading-aside"><section v-if="newsItems.length" class="ps-panel"><h3>其他新闻资讯</h3><el-link underline="never" :href="$router.resolve(`/portal/news/${item.id}` || '/portal').href" v-for="item in newsItems.slice(0, 3)" :key="item.id" class="ps-related-item ps-ui-title" @click.prevent="openPortalContent(router, `/portal/news/${item.id}`)"><strong>{{ item.title }}</strong><small>{{ item.source }}</small></el-link></section><section v-if="relatedPapers.length" class="ps-panel"><h3>其他论文</h3><el-link underline="never" :href="$router.resolve(`/portal/papers/${item.id}` || '/portal').href" v-for="item in relatedPapers" :key="item.id" class="ps-related-item ps-ui-title" @click.prevent="openPortalContent(router, `/portal/papers/${item.id}`)"><strong>{{ item.titleZh }}</strong><small>{{ item.journal }} · {{ item.year }}</small></el-link></section></aside>
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
import ContentInsights from '../components/ContentInsights.vue'
import ContentEntities from '../components/ContentEntities.vue'
import { contentCategory } from '@/utils/portal/contentPresentation'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const { inBasket, busy, toggleBasket } = useListWorkspace(portalStore, { save: savePipelineWorkspaceItem, remove: deletePipelineWorkspaceItem })
const activeTab = ref('摘要')
const livePaper = ref(null)
const detailError = ref('')
const detailLoading = ref(true)
const paper = computed(() => detailError.value ? null : livePaper.value)
const abstractLanguage = ref('original')
const originalAbstract = computed(() => paper.value?.abstractOriginal || paper.value?.abstract_original || paper.value?.abstract || '')
const translatedAbstract = computed(() => paper.value?.abstractZh || paper.value?.abstract_zh || '')
const visibleAbstract = computed(() => abstractLanguage.value === 'zh' ? translatedAbstract.value : originalAbstract.value || translatedAbstract.value)
const originalTitle = computed(() => {
  const original = String(paper.value?.title || '').trim()
  const normalize = value => String(value || '').replace(/\s+/g, ' ').trim().toLocaleLowerCase()
  return normalize(original) !== normalize(paper.value?.titleZh) ? original : ''
})
const paperInstitutions = computed(() => [...new Set((paper.value?.institutions || [])
  .map(value => String(value || '').trim())
  .filter(value => value && !['来源数据库', '机构待补充', '未提供', '待补充'].includes(value)))])
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
  abstractLanguage.value = 'original'
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
.ps-paper-reading-page .ps-paper-detail-body { min-width: 0; padding: 0; }
.ps-paper-content-toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px 16px; padding: 12px 20px; border-bottom: 1px solid var(--ps-line-soft); }
.ps-paper-language { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; min-width: 0; }
.ps-paper-detail-body .ps-paper-section { padding: 20px; }
.ps-paper-section .ps-paper-abstract { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 15px; line-height: 1.9; }
.ps-paper-detail-keywords { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px 14px; margin-top: 16px; }
.ps-paper-detail-keywords h3 { margin: 0; flex-shrink: 0; font-size: 13px; color: var(--ps-muted); font-weight: 500; }
.ps-paper-detail-keywords .ps-tag-row { margin: 0; flex: 1; min-width: 0; }
.ps-paper-detail-keywords :deep(.el-tag) { max-width: 100%; height: auto; white-space: normal; overflow-wrap: anywhere; }
.ps-paper-detail-body .ps-paper-core-entities { margin: 0 20px; padding: 16px 0 20px; border: 0; border-top: 1px solid var(--ps-line-soft); border-radius: 0; }
.ps-paper-core-entities :deep(.entity-heading) { margin-bottom: 10px; }
.ps-paper-core-entities :deep(.entity-heading h2) { font-size: 14px; }
.ps-paper-core-entities :deep(dl) { display: flex; flex-wrap: wrap; gap: 10px 24px; }
.ps-paper-core-entities :deep(.entity-group) { max-width: 100%; }
.ps-paper-insights :deep(.ps-content-insights > h2) { display: none; }
.ps-paper-insights :deep(.insight-note) { margin-top: 0; }
@media (max-width: 600px) {
  .ps-paper-content-toolbar { padding: 12px 14px; gap: 8px; }
  .ps-paper-detail-body .ps-paper-section { padding: 16px 14px; }
  .ps-paper-detail-body .ps-paper-core-entities { margin: 0 14px; padding: 14px 0 16px; }
}

.ps-paper-detail-hero { padding: 18px 20px; margin-bottom: 16px; background: var(--ps-surface, #fff); }
.ps-paper-detail-hero .ps-detail-title-row { margin: 0 0 10px; }
.ps-paper-detail-hero .ps-detail-info-row { gap: 12px 20px; }
.ps-paper-detail-hero .ps-paper-detail-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; margin: 0; color: var(--ps-muted); font-size: 13px; line-height: 1.6; }
.ps-paper-detail-meta > span, .ps-paper-detail-meta > a { min-width: 0; overflow-wrap: anywhere; }
.ps-paper-detail-meta :deep(.el-tag) { max-width: 100%; height: auto; min-height: var(--el-tag-height); white-space: normal; }
.ps-paper-detail-meta :deep(.el-tag__content) { white-space: normal; overflow-wrap: anywhere; }
.ps-paper-doi-link { color: var(--ps-blue); text-decoration: none; overflow-wrap: anywhere; }
.ps-paper-doi-link:hover { text-decoration: underline; }
.ps-paper-doi-link:focus-visible { outline: 2px solid var(--ps-blue); outline-offset: 2px; }
.ps-paper-detail-hero h1 { max-width: none; margin: 0; color: var(--ps-ink); font-size: 22px; font-weight: 600; line-height: 1.5; letter-spacing: 0; overflow-wrap: anywhere; }
.ps-paper-detail-authors, .ps-paper-detail-institutions { margin: 0 0 10px; color: var(--ps-muted); font-size: 14px; line-height: 1.7; overflow-wrap: anywhere; }
.ps-paper-detail-authors > span, .ps-paper-detail-institutions > span { margin-right: 12px; color: var(--ps-ink-2); }
@media (max-width: 600px) {
  .ps-paper-detail-hero { padding: 14px; }
  .ps-paper-detail-hero h1 { font-size: 20px; }
  .ps-paper-detail-hero > :not(.ps-detail-title-row) { grid-column: 1 / -1; }
  .ps-paper-detail-hero .ps-detail-info-row { flex-wrap: wrap; }
  .ps-paper-detail-hero .ps-paper-detail-meta { flex-basis: 100%; }
  .ps-paper-detail-hero .ps-article-actions { margin-left: auto; }
}
</style>
