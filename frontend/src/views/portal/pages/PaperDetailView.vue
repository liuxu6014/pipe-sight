<template>
  <div class="ps-page ps-reading-page ps-paper-reading-page">
    <PortalEmptyState v-if="detailLoading" title="正在加载论文" description="正在读取最新的权限和内容状态。" />
    <PortalEmptyState v-else-if="detailError" title="论文暂时无法读取" :description="detailError" action-label="重新加载" @action="loadPaper" />
    <PortalEmptyState v-else-if="!paper" title="论文不存在" description="该论文记录可能已移除，或当前账号没有访问权限。" action-label="返回论文资料" @action="router.push('/portal/papers')" />
    <template v-else>
    <section class="ps-paper-detail-hero" aria-labelledby="paper-detail-title">
      <div class="ps-paper-detail-toolbar">
        <el-button class="ps-detail-back-button" plain :icon="Back" aria-label="返回" @click="returnFromPaperDetail(router)">返回</el-button>
        <div class="ps-paper-detail-actions">
          <el-button v-if="canSwitchLanguage" class="ps-paper-language-action" plain :loading="translating" @click="toggleLanguage">
            {{ showingTranslation ? '切换为原文' : '翻译为中文' }}
          </el-button>
          <el-button :icon="Collection" type="primary" plain :loading="busy(paper)" :disabled="busy(paper)" @click="add">{{ inBasket(paper) ? '取消加入资料库' : '加入资料库' }}</el-button>
        </div>
      </div>
      <h1 id="paper-detail-title">{{ visibleTitle }}</h1>
      <p v-if="translationError" class="ps-paper-translation-error" role="alert">{{ translationError }}</p>
      <dl v-if="paper.authors?.length || paperInstitutions.length" class="ps-paper-credits">
        <div v-if="paper.authors?.length">
          <dt>作者</dt>
          <dd>{{ paper.authors.join(' · ') }}</dd>
        </div>
        <div v-if="paperInstitutions.length">
          <dt>机构</dt>
          <dd>{{ paperInstitutions.join('；') }}</dd>
        </div>
      </dl>
      <div v-if="paper.journal || paper.publishedDate || paper.year || (paper.doi && paper.doi !== '待补充') || sourceUrl || paper.citations != null" class="ps-paper-detail-meta" role="group" aria-label="出版信息">
        <el-tag v-if="paper.journal" type="primary" effect="light">{{ paper.journal }}</el-tag>
        <span v-if="paper.publishedDate || paper.year">发表于 {{ paper.publishedDate || paper.year }}</span>
        <a v-if="doiUrl" :href="doiUrl" class="ps-paper-doi-link" target="_blank" rel="noopener noreferrer">DOI: {{ paper.doi }}</a>
        <span v-else-if="paper.doi && paper.doi !== '待补充'">DOI: {{ paper.doi }}</span>
        <a v-if="!doiUrl && sourceUrl" :href="sourceUrl" class="ps-paper-doi-link" target="_blank" rel="noopener noreferrer">查看原文</a>
        <span v-if="paper.citations != null">被引 {{ paper.citations }} 次</span>
      </div>
    </section>
    <div class="ps-reading-layout" >
      <article class="ps-paper-detail-body">
        <section class="ps-paper-section" aria-labelledby="paper-abstract-heading">
          <div class="ps-paper-section-heading">
            <h2 id="paper-abstract-heading">摘要</h2>
          </div>
          <p class="ps-paper-abstract">{{ visibleAbstract || '摘要未提供' }}</p>
          <div v-if="paper.keywords?.length" class="ps-paper-detail-keywords"><h3>关键词</h3><div class="ps-tag-row"><el-tag v-for="tag in paper.keywords" :key="tag" effect="plain">{{ tag }}</el-tag></div></div>
        </section>
        <ContentInsights class="ps-paper-section ps-paper-insights" :item="paper" kind="paper" />
        <ContentEntities class="ps-paper-core-entities" :entities="paper.entities">
          <template #prepend><ContentCategory :name="contentCategory(paper)" /></template>
        </ContentEntities>
      </article>
      <aside class="ps-reading-aside"><section v-if="newsItems.length" class="ps-panel"><h3>其他新闻资讯</h3><el-link underline="never" :href="$router.resolve(`/portal/news/${item.id}` || '/portal').href" v-for="item in newsItems.slice(0, 3)" :key="item.id" class="ps-related-item ps-ui-title" @click.prevent="openPortalContent(router, `/portal/news/${item.id}`)"><strong>{{ item.title }}</strong><small>{{ item.source }}</small></el-link></section><section v-if="relatedPapers.length" class="ps-panel"><h3>其他论文</h3><el-link underline="never" :href="$router.resolve(`/portal/papers/${item.id}` || '/portal').href" v-for="item in relatedPapers" :key="item.id" class="ps-related-item ps-ui-title" @click.prevent="openPortalContent(router, `/portal/papers/${item.id}`)"><strong>{{ item.titleZh }}</strong><small>{{ item.journal }} · {{ item.year }}</small></el-link></section></aside>
    </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back, Collection } from '@element-plus/icons-vue'
import usePortalStore from '@/store/modules/portal'
import { getPipelineIntelligenceDetail, savePipelineWorkspaceItem, deletePipelineWorkspaceItem, translatePipelinePaperTitle, translatePipelinePaperAbstract } from '@/api/pipeline/intelligence'
import { useListWorkspace } from '@/utils/portal/listQuery'
import { normalizePortalPaper } from '@/store/modules/portal'
import { openPortalContent, returnFromPaperDetail } from '@/utils/portal/openContent'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import ContentCategory from '../components/ContentCategory.vue'
import ContentInsights from '../components/ContentInsights.vue'
import ContentEntities from '../components/ContentEntities.vue'
import { contentCategory } from '@/utils/portal/contentPresentation'

const route = useRoute()
const router = useRouter()
const portalStore = usePortalStore()
const { inBasket, busy, toggleBasket } = useListWorkspace(portalStore, { save: savePipelineWorkspaceItem, remove: deletePipelineWorkspaceItem })
const livePaper = ref(null)
const detailError = ref('')
const detailLoading = ref(true)
const showingTranslation = ref(false)
const translating = ref(false)
const translationError = ref('')
const paper = computed(() => detailError.value ? null : livePaper.value)
const isEnglishTitle = computed(() => {
  const original = paper.value?.title || ''
  return /[A-Za-z]{2}/.test(original) && !/[\u3400-\u9fff]/.test(original)
})
const hasTitleTranslation = computed(() => isEnglishTitle.value && /[\u3400-\u9fff]/.test(paper.value?.titleZh || ''))
const visibleTitle = computed(() => (showingTranslation.value && hasTitleTranslation.value ? paper.value?.titleZh : paper.value?.title) || paper.value?.titleZh)
const originalAbstract = computed(() => paper.value?.abstractOriginal ?? paper.value?.abstract_original ?? paper.value?.abstract ?? '')
const translatedAbstract = computed(() => paper.value?.abstractZh || paper.value?.abstract_zh || '')
const isEnglishAbstract = computed(() => {
  const latin = (originalAbstract.value.match(/[A-Za-z]/g) || []).length
  const han = (originalAbstract.value.match(/[\u3400-\u9fff]/g) || []).length
  return latin >= 2 && latin > han
})
const hasAbstractTranslation = computed(() => /[\u3400-\u9fff]/.test(translatedAbstract.value))
const visibleAbstract = computed(() => (showingTranslation.value && isEnglishAbstract.value && hasAbstractTranslation.value
  ? translatedAbstract.value : originalAbstract.value) || translatedAbstract.value || paper.value?.abstract || '')
const canSwitchLanguage = computed(() => isEnglishTitle.value || isEnglishAbstract.value)
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
async function toggleLanguage() {
  if (!canSwitchLanguage.value || translating.value) return
  if (showingTranslation.value) {
    showingTranslation.value = false
    return
  }
  const request = detailRequest
  const id = paper.value.id
  translationError.value = ''
  translating.value = true
  try {
    if (isEnglishTitle.value && !hasTitleTranslation.value) {
      const res = await translatePipelinePaperTitle(id)
      if (request !== detailRequest) return
      livePaper.value.titleZh = requireChineseTranslation(res.data?.titleZh, '标题')
    }
    if (isEnglishAbstract.value && !hasAbstractTranslation.value) {
      const res = await translatePipelinePaperAbstract(id)
      if (request !== detailRequest) return
      livePaper.value.abstractZh = requireChineseTranslation(res.data?.abstractZh, '摘要')
    }
    showingTranslation.value = true
  } catch (error) {
    if (request === detailRequest) translationError.value = error?.msg || error?.message || '论文翻译失败，请重试'
  } finally {
    if (request === detailRequest) translating.value = false
  }
}
function requireChineseTranslation(value, label) {
  if (typeof value !== 'string' || !/[\u3400-\u9fff]/.test(value)) throw new Error(`未收到中文${label}，请重试`)
  return value
}
async function loadPaper() {
  const request = ++detailRequest
  showingTranslation.value = false
  translating.value = false
  translationError.value = ''
  detailLoading.value = true
  livePaper.value = null
  detailError.value = ''
  try {
    const res = await getPipelineIntelligenceDetail(route.params.itemId)
    if (request !== detailRequest) return
    const payload = res.data?.data || res.data
    if (payload?.id && payload.category === 'paper') livePaper.value = normalizePortalPaper(payload)
    else detailError.value = '该论文记录不存在或当前账号没有访问权限。'
  } catch (error) {
    if (request !== detailRequest) return
    detailError.value = error?.msg || '论文详情加载失败，请确认后端服务和访问权限。'
  } finally {
    if (request === detailRequest) detailLoading.value = false
  }
}
onMounted(loadPaper)
onBeforeUnmount(() => { detailRequest += 1 })
watch(() => route.params.itemId, loadPaper)
</script>

<style scoped>
:global(html:has(.ps-paper-reading-page)) { overflow-y: scroll; }
.ps-paper-reading-page .ps-paper-detail-body { min-width: 0; padding: 0; }
.ps-paper-section-heading { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 16px; margin-bottom: 10px; }
.ps-paper-section-heading h2 { margin: 0; font-size: 17px; }
.ps-paper-detail-body .ps-paper-section { padding: 16px 20px; }
.ps-paper-insights { border-top: 1px solid var(--ps-line-soft); }
.ps-paper-insights :deep(h2) { margin: 0 0 8px; font-size: 17px; }
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
@media (max-width: 600px) {
  .ps-paper-detail-body .ps-paper-section { padding: 16px 14px; }
  .ps-paper-detail-body .ps-paper-core-entities { margin: 0 14px; padding: 14px 0 16px; }
}

.ps-paper-detail-hero {
  display: grid;
  gap: 12px;
  padding: 18px 24px;
  margin-bottom: 16px;
  background: var(--ps-paper);
}
.ps-paper-detail-toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; }
.ps-paper-detail-toolbar .el-button { margin: 0; }
.ps-paper-detail-toolbar .ps-detail-back-button { color: var(--ps-muted); }
.ps-paper-detail-toolbar .ps-detail-back-button:hover { color: var(--ps-blue); }
.ps-paper-detail-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.ps-paper-language-action { inline-size: 122px; }
.ps-paper-translation-error { margin: 0; color: var(--el-color-danger); font-size: 13px; }
.ps-paper-detail-hero h1 { max-width: 64ch; margin: 0; color: var(--ps-ink); font-size: 24px; font-weight: 600; line-height: 1.45; letter-spacing: 0; overflow-wrap: anywhere; }
.ps-paper-credits { display: grid; gap: 5px; margin: 0; color: var(--ps-muted); font-size: 14px; line-height: 1.65; }
.ps-paper-credits > div { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 10px; }
.ps-paper-credits dt { color: var(--ps-ink-2); }
.ps-paper-credits dd { margin: 0; overflow-wrap: anywhere; }
.ps-paper-detail-hero .ps-paper-detail-meta {
  align-items: center;
  gap: 6px 16px;
  padding-top: 12px;
  border-top: 1px solid var(--ps-line-soft);
  line-height: 1.6;
}
.ps-paper-detail-meta > * { min-width: 0; overflow-wrap: anywhere; }
.ps-paper-detail-meta :deep(.el-tag) { max-width: 100%; height: auto; min-height: var(--el-tag-height); white-space: normal; }
.ps-paper-detail-meta :deep(.el-tag__content) { white-space: normal; overflow-wrap: anywhere; }
.ps-paper-doi-link { color: var(--ps-blue); text-decoration: none; overflow-wrap: anywhere; }
.ps-paper-doi-link:hover { text-decoration: underline; }
.ps-paper-doi-link:focus-visible { outline: 2px solid var(--ps-blue); outline-offset: 2px; }
@media (max-width: 600px) {
  .ps-paper-detail-hero { padding: 14px; }
  .ps-paper-detail-hero h1 { font-size: 20px; }
  .ps-paper-detail-toolbar .el-button { min-height: 44px; }
}
</style>
