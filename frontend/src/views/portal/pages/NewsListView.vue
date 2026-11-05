<template>
  <div class="ps-page ps-list-page ps-news-page">
    <div class="ps-toolbar">
      <div class="ps-search-inline"><Search /><input v-model.trim="keyword" aria-label="搜索新闻资讯" placeholder="搜索标题、摘要或正文" @keydown.enter="reload" /><el-button class="ps-ui-action" v-if="keyword" aria-label="清空资讯关键词" @click="keyword = ''">清空</el-button></div>
      <el-select v-model="sourceType" aria-label="资讯来源" style="width: 150px"><el-option label="全部来源" value="全部" /><el-option label="新闻网站" value="新闻网站" /><el-option label="微信公众号" value="微信公众号" /></el-select>
      <el-select :model-value="activeTags[0] || ''" clearable filterable placeholder="全部类别" aria-label="资讯类别" style="width: 200px" @update:model-value="setCategory"><el-option v-for="tag in tags" :key="tag" :label="tag" :value="tag" /></el-select>
      <el-button @click="resetFilters">重置筛选</el-button>
      <div class="ps-view-switch ps-segmented-row"><el-segmented v-model="viewMode" :options="[{ label: '列表', value: 'list' }, { label: '卡片', value: 'card' }]" aria-label="资讯展示方式"  /></div>
    </div>
    <div class="ps-news-content ps-list-stack">
      <section v-loading="loading" :aria-busy="loading" class="ps-list-stack">
        <div :class="['ps-news-list', 'ps-list-scroll', { 'is-card': viewMode === 'card' }]" tabindex="0" aria-label="新闻资讯列表">
        <article v-for="item in newsItems" :key="item.id" class="ps-news-card">
          <div class="ps-news-row-heading">
            <div class="ps-news-card-top">
              <el-tag class="ps-news-source-type" type="primary" size="small">{{ item.sourceType }}</el-tag>
              <span v-if="item.source" class="ps-news-source" :title="item.source">{{ item.source }}</span>
              <time>{{ newsDate(item.time) }}</time>
              <div v-if="item.extraTags.length" class="ps-news-categories"><el-button v-for="tag in item.extraTags" :key="tag" class="ps-category-chip" size="small" plain :type="activeTags.includes(tag) ? 'primary' : 'default'" :aria-pressed="activeTags.includes(tag)" @click="toggleTag(tag)">{{ tag }}</el-button></div>
            </div>
            <div class="ps-news-row-actions"><el-button type="primary" plain :loading="busy(item)" :disabled="busy(item)" @click="addToBasket(item)">{{ inBasket(item) ? '取消加入资料库' : '加入资料库' }}</el-button></div>
          </div>
          <div class="ps-news-card-main">
          <router-link v-if="item.cover_image || viewMode === 'card'" class="ps-news-cover" :aria-label="`阅读资讯：${item.title}`" :to="`/portal/news/${item.id}`">
            <img v-if="item.cover_image" :src="item.cover_image" alt="文章配图" loading="lazy" />
            <div v-else class="ps-news-theme-cover" role="img" :aria-label="`${item.tags?.[0] || '管网科技'}主题示意，非新闻原图`">
              <svg viewBox="0 0 560 200" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
                <path d="M0 40H560M0 80H560M0 120H560M0 160H560M40 0V200M80 0V200M120 0V200M160 0V200M200 0V200M240 0V200M280 0V200M320 0V200M360 0V200M400 0V200M440 0V200M480 0V200M520 0V200" stroke="#cbdfe9" fill="none" opacity=".5" />
                <path d="M285 200V145Q285 125 305 125H380Q400 125 400 105V60Q400 40 420 40H560" stroke="#bdd5e2" stroke-width="20" fill="none" />
                <path d="M285 200V145Q285 125 305 125H380Q400 125 400 105V60Q400 40 420 40H560" stroke="#236486" stroke-width="3" fill="none" />
                <path d="M340 0V62Q340 82 360 82H465Q485 82 485 102V200" stroke="#87b8c2" stroke-width="12" fill="none" />
                <path d="M340 0V62Q340 82 360 82H465Q485 82 485 102V200" stroke="#26747d" stroke-width="2" fill="none" />
                <circle cx="400" cy="82" r="24" fill="#e6f0f5" stroke="#236486" stroke-width="2" /><circle cx="400" cy="82" r="8" fill="#236486" />
                <circle cx="285" cy="160" r="7" fill="#e6f0f5" stroke="#236486" stroke-width="3" /><circle cx="485" cy="156" r="7" fill="#e6f0f5" stroke="#26747d" stroke-width="3" />
              </svg>
              <div class="ps-news-theme-copy"><small>管网科技资讯</small><strong>{{ item.tags?.[0] || '行业动态' }}</strong><span>主题示意 · 非新闻原图</span></div>
            </div>
          </router-link>
          <div class="ps-news-card-copy">
          <router-link class="ps-news-title" :to="`/portal/news/${item.id}`">{{ item.title }}</router-link>
          <p v-if="cleanSummary(item.summary)" class="ps-news-summary">{{ cleanSummary(item.summary) }}</p>
          <ContentEntities :entities="item.entities" compact>
            <template #prepend><ContentCategory :name="item.categoryName" /></template>
          </ContentEntities>
          </div></div>
        </article>
        <PortalEmptyState v-if="loadError && !loading" title="资讯加载失败" :description="loadError" action-label="重新加载" @action="reload" />
        <PortalEmptyState v-else-if="!newsItems.length && !loading" title="没有匹配的资讯" description="请调整标签、来源或搜索关键词。" action-label="重置筛选" @action="resetFilters" />
        </div>
        <div v-if="total > 0 && !loading && !loadError" class="ps-pagination" aria-label="资讯列表分页">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50]"
            :total="total"
            :pager-count="5"
            layout="total, sizes, ->, prev, pager, next, jumper"
            background
          />
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import ContentEntities from '../components/ContentEntities.vue'
import ContentCategory from '../components/ContentCategory.vue'
import { computed, toRefs, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'
import { getPipelineContentFilters, deletePipelineWorkspaceItem, listPipelineIntelligence, savePipelineWorkspaceItem } from '@/api/pipeline/intelligence'
import { normalizePortalIntelligence } from '@/store/modules/portal'
import { useListQuery, useListRequest, useListWorkspace, validPage } from '@/utils/portal/listQuery'
import { cleanSummary, newsDate } from '@/utils/portal/discovery'

const portalStore = usePortalStore()
const query = useListQuery({ q: '', source: '全部', category: '全部', tag: [], view: 'list', page: 1, size: 10 })
const { q: keyword, source: sourceType, tag: activeTags, view: viewMode, page: currentPage, size: pageSize } = toRefs(query)
// Old category links referred to tags; migrate them into the single visible filter.
watch(() => [query.category, query.tag], () => {
  const legacy = query.category
  const values = Array.isArray(query.tag) ? [...query.tag] : [query.tag]
  if (legacy && !['全部', 'article', 'news', 'wechat'].includes(legacy)) values.unshift(legacy)
  if (query.source === '全部' && ['news', 'wechat'].includes(legacy)) query.source = legacy === 'news' ? '新闻网站' : '微信公众号'
  const normalized = [...new Set(values.map(value => String(value || '').trim()).filter(value => value && value !== '全部'))].slice(0, 20)
  query.category = '全部'
  if (JSON.stringify(query.tag) !== JSON.stringify(normalized)) query.tag = normalized
}, { immediate: true, deep: true })
const { inBasket, busy, toggleBasket } = useListWorkspace(portalStore, { save: savePipelineWorkspaceItem, remove: deletePipelineWorkspaceItem })
const { data, loading, loadError, reload } = useListRequest(() => ({
  category: 'article',
  keyword: keyword.value || undefined,
  tags: activeTags.value.length ? JSON.stringify(activeTags.value) : undefined,
  source_type: ({ 新闻网站: 'news', 微信公众号: 'wechat' })[sourceType.value],
  pageNum: currentPage.value,
  pageSize: pageSize.value
}), listPipelineIntelligence)
const newsItems = computed(() => (data.value?.rows || []).map(item => {
  const normalized = normalizePortalIntelligence(item)
  return {
    ...normalized,
    category: ['article', 'news', 'wechat'].includes(item.category) ? (item.tags?.[0] || '分类未提供') : (item.category || '分类未提供'),
    extraTags: normalized.tags.filter(tag => tag !== normalized.categoryName)
  }
}))
const total = computed(() => Number(data.value?.total || 0))
watch(data, value => { if (value) currentPage.value = validPage(total.value, pageSize.value, currentPage.value) })
const facets = useListRequest(() => ({}), getPipelineContentFilters)
const tags = computed(() => [...new Set([...(facets.data.value?.articleCategories || facets.data.value?.newsTags || []), ...activeTags.value])])
function setCategory(value) { activeTags.value = value ? [value] : [] }
function toggleTag(tag) {
  if (activeTags.value.includes(tag)) activeTags.value = activeTags.value.filter(value => value !== tag)
  else setCategory(tag)
}
async function addToBasket(item) {
  try {
    const result = await toggleBasket(item, 'article')
    if (result === 'saved') ElMessage.success('已加入资料库')
    else if (result === 'removed') ElMessage.success('已取消加入资料库')
  } catch (error) { ElMessage.error(error?.msg || '资料库更新失败，请重试') }
}
function resetFilters() {
  const unchanged = !keyword.value && sourceType.value === '全部' && !activeTags.value.length && currentPage.value === 1
  keyword.value = ''; sourceType.value = '全部'; query.category = '全部'; activeTags.value = []; currentPage.value = 1
  if (unchanged) reload()
}
</script>

<style scoped>
.ps-page { --ws-page-space: 14px; }
.ps-toolbar { min-height: 0; padding: 6px 12px; row-gap: 6px; margin-bottom: 10px; }
.ps-toolbar > .ps-search-inline { flex: 1 1 100%; }
.ps-toolbar > .el-select { flex: 1 1 150px; }
.ps-search-inline > button { flex-shrink: 0; white-space: nowrap; }
@media (min-width: 1051px) {
  .ps-toolbar { flex-wrap: nowrap; }
  .ps-toolbar > .ps-search-inline { flex: 1 1 280px; min-width: 180px; }
  .ps-toolbar > .el-select { flex: 0 0 160px; width: 160px; }
  .ps-toolbar > .el-button, .ps-toolbar > .ps-view-switch { flex-shrink: 0; }
}
.ps-news-title, .ps-news-cover { text-decoration: none; }
.ps-news-page .ps-news-list { gap: 10px; align-content: start; }
.ps-news-page .ps-news-card { min-width: 0; padding: 14px 18px 16px; border-radius: 10px; box-shadow: none; }
.ps-news-row-heading { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: start; gap: 10px 16px; margin-bottom: 8px; }
.ps-news-page .ps-news-card-top { display: flex; flex-wrap: wrap; align-items: center; align-content: center; gap: 6px 12px; min-width: 0; min-height: 36px; margin: 0; font-size: 13px; line-height: 1.5; color: var(--ps-muted); }
.ps-news-card-top time { white-space: nowrap; font-size: inherit; color: #637084; }
.ps-news-source-type { flex-shrink: 0; height: 28px; padding: 0 10px; border: 0; border-radius: 6px; font-size: 13px; line-height: 20px; --el-tag-text-color: #245ca6; --el-tag-bg-color: #edf4ff; }
.ps-news-source { max-width: min(260px, 100%); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--ps-ink-2); }
.ps-news-categories { display: flex; flex-wrap: wrap; gap: 6px; min-width: 0; }
.ps-news-categories :deep(.el-button) { margin: 0; white-space: normal; overflow-wrap: anywhere; }
.ps-news-row-actions :deep(.el-button) { margin: 0; }
.ps-news-card-main { display: flex; gap: 16px; align-items: flex-start; }
.ps-news-card-copy { flex: 1; min-width: 0; }
.ps-news-page .ps-news-title { display: block; margin: 0; color: var(--ps-ink); font-size: 17px; font-weight: 600; line-height: 1.6; overflow-wrap: anywhere; }
.ps-news-page .ps-news-title:hover { color: var(--ps-blue); }
.ps-news-title:focus-visible, .ps-news-cover:focus-visible { outline: 2px solid var(--ps-blue); outline-offset: 3px; border-radius: 4px; }
.ps-news-page .ps-news-summary { margin: 7px 0 0; color: var(--ps-muted); font-size: 14px; line-height: 1.8; overflow-wrap: anywhere; }
.ps-news-cover { flex: 0 0 180px; width: 180px; margin-top: 2px; padding: 0; border: 0; border-radius: 8px; overflow: hidden; background: transparent; }
.ps-news-cover img { display: block; width: 100%; height: 122px; object-fit: cover; }
.ps-news-list.is-card .ps-news-card-main { flex-direction: column; gap: 0; }
.ps-news-list.is-card .ps-news-cover { flex: 0 0 auto; width: 100%; }
.ps-news-list.is-card .ps-news-title { margin-top: 10px; }
.ps-news-list.is-card .ps-news-cover img { height: 200px; }
.ps-news-theme-cover { position: relative; height: 200px; width: 100%; overflow: hidden; background: #e6f0f5; }
.ps-news-theme-cover > svg { position: absolute; inset: 0; width: 100%; height: 100%; }
.ps-news-theme-copy { position: relative; z-index: 1; display: flex; flex-direction: column; align-items: flex-start; justify-content: center; height: 100%; padding: 24px; color: #194c68; }
.ps-news-theme-copy small { font-size: 13px; letter-spacing: .12em; }
.ps-news-theme-copy strong { max-width: 55%; margin-top: 10px; font-size: 25px; line-height: 1.4; overflow-wrap: anywhere; }
.ps-news-theme-copy span { margin-top: 22px; padding: 3px 7px; border: 1px solid #bfd5e1; border-radius: 4px; background: #eff6fa; font-size: 11px; color: #395c70; }
@media (max-width: 600px) {
  .ps-news-page .ps-news-card { padding: 12px; }
  .ps-news-row-heading { gap: 8px; margin-bottom: 6px; }
  .ps-news-page .ps-news-card-top { gap: 4px 8px; min-height: 44px; }
  .ps-news-page .ps-news-title { font-size: 16px; }
  .ps-news-card-main { flex-direction: column; gap: 0; }
  .ps-news-cover { flex: 0 0 auto; width: 100%; }
  .ps-news-cover img { height: 180px; }
  .ps-news-theme-cover { height: 180px; }
  .ps-news-theme-copy { padding: 18px; }
  .ps-news-theme-copy strong { font-size: 22px; }
}
</style>
