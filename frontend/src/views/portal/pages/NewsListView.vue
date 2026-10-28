<template>
  <div class="ps-page ps-list-page">
    <div class="ps-toolbar">
      <div class="ps-search-inline"><Search /><input v-model.trim="keyword" aria-label="搜索新闻资讯" placeholder="搜索标题、摘要或正文" @keydown.enter="reload" /><el-button class="ps-ui-action" v-if="keyword" aria-label="清空资讯关键词" @click="keyword = ''">清空</el-button></div>
      <el-select v-model="sourceType" aria-label="资讯来源" style="width: 150px"><el-option label="全部来源" value="全部" /><el-option label="新闻网站" value="新闻网站" /><el-option label="微信公众号" value="微信公众号" /></el-select>
      <el-select v-model="activeTags" multiple :multiple-limit="20" clearable filterable allow-create default-first-option collapse-tags collapse-tags-tooltip placeholder="全部标签" aria-label="资讯标签" style="width: 200px"><el-option v-for="tag in tags" :key="tag" :label="tag" :value="tag" /></el-select>
      <el-button @click="resetFilters">重置筛选</el-button>
      <div class="ps-view-switch"><button type="button" aria-label="列表视图" :aria-pressed="viewMode === 'list'" :class="{ 'is-active': viewMode === 'list' }" @click="viewMode = 'list'"><List /></button><button type="button" aria-label="卡片视图" :aria-pressed="viewMode === 'card'" :class="{ 'is-active': viewMode === 'card' }" @click="viewMode = 'card'"><Grid /></button></div>
    </div>
    <SavedSearchBar kind="news" :query="query" @apply="applySavedSearch" />
    <div class="ps-news-content ps-list-stack">
      <section v-loading="loading" :aria-busy="loading" class="ps-list-stack">
        <div :class="['ps-news-list', 'ps-list-scroll', { 'is-card': viewMode === 'card' }]" tabindex="0" aria-label="新闻资讯列表">
        <article v-for="item in newsItems" :key="item.id" class="ps-news-card">
          <div class="ps-news-card-top"><span class="ps-source-badge">{{ item.sourceType }}</span><time>{{ newsDate(item.time) }}</time></div>
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
          <p>{{ cleanSummary(item.summary) }}</p>
          <div class="ps-tag-row"><button v-for="tag in item.tags" :key="tag" type="button" class="ps-tag" :aria-pressed="activeTags.includes(tag)" @click="toggleTag(tag)">{{ tag }}</button></div>
          </div></div>
          <div class="ps-news-card-footer"><span>{{ item.source }} · {{ item.category }}</span><div><el-button type="primary" plain :loading="busy(item)" :disabled="busy(item)" @click="addToBasket(item)">{{ inBasket(item) ? '取消加入资料库' : '加入资料库' }}</el-button></div></div>
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
import SavedSearchBar from '../components/SavedSearchBar.vue'
import { applySavedSearchQuery } from '@/utils/portal/savedSearches'
import { computed, toRefs, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Grid, List, Search } from '@element-plus/icons-vue'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'
import { getPipelineContentFilters, deletePipelineWorkspaceItem, listPipelineIntelligence, savePipelineWorkspaceItem } from '@/api/pipeline/intelligence'
import { normalizePortalIntelligence } from '@/store/modules/portal'
import { useListQuery, useListRequest, useListWorkspace, validPage } from '@/utils/portal/listQuery'
import { cleanSummary, newsDate } from '@/utils/portal/discovery'

const portalStore = usePortalStore()
const query = useListQuery({ q: '', source: '全部', category: '全部', tag: [], view: 'list', page: 1, size: 10 })
function applySavedSearch(filters) { if (!applySavedSearchQuery(query, filters, 'news')) reload() }
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
const newsItems = computed(() => (data.value?.rows || []).map(item => ({
  ...normalizePortalIntelligence(item),
  category: ['article', 'news', 'wechat'].includes(item.category) ? (item.tags?.[0] || '分类未提供') : (item.category || '分类未提供')
})))
const total = computed(() => Number(data.value?.total || 0))
watch(data, value => { if (value) currentPage.value = validPage(total.value, pageSize.value, currentPage.value) })
const facets = useListRequest(() => ({}), getPipelineContentFilters)
const tags = computed(() => [...new Set([...(facets.data.value?.newsTags || []), ...activeTags.value])])
function toggleTag(tag) {
  activeTags.value = activeTags.value.includes(tag) ? activeTags.value.filter(value => value !== tag) : [...activeTags.value, tag].slice(0, 20)
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
.ps-search-inline > button { flex-shrink: 0; padding: 4px 8px; border: 0; border-radius: 4px; background: transparent; color: var(--ps-muted); white-space: nowrap; cursor: pointer; }
.ps-search-inline > button:hover { color: var(--ps-blue); background: var(--ps-blue-soft); }
@media (min-width: 1051px) {
  .ps-toolbar { flex-wrap: nowrap; }
  .ps-toolbar > .ps-search-inline { flex: 1 1 280px; min-width: 180px; }
  .ps-toolbar > .el-select { flex: 0 0 160px; width: 160px; }
  .ps-toolbar > .el-button, .ps-toolbar > .ps-view-switch { flex-shrink: 0; }
}
.ps-news-title, .ps-news-cover { text-decoration: none; }
.ps-news-card-main { display: flex; gap: 20px; align-items: flex-start; }
.ps-news-card-copy { flex: 1; min-width: 0; }
.ps-news-cover { flex: 0 0 180px; width: 180px; margin-top: 12px; padding: 0; border: 0; border-radius: 8px; overflow: hidden; background: transparent; }
.ps-news-cover img { display: block; width: 100%; height: 122px; object-fit: cover; }
.ps-news-list.is-card .ps-news-card-main { flex-direction: column; gap: 0; }
.ps-news-list.is-card .ps-news-cover { flex: 0 0 auto; width: 100%; }
.ps-news-list.is-card .ps-news-cover img { height: 200px; }
.ps-news-theme-cover { position: relative; height: 200px; width: 100%; overflow: hidden; background: #e6f0f5; }
.ps-news-theme-cover > svg { position: absolute; inset: 0; width: 100%; height: 100%; }
.ps-news-theme-copy { position: relative; z-index: 1; display: flex; flex-direction: column; align-items: flex-start; justify-content: center; height: 100%; padding: 24px; color: #194c68; }
.ps-news-theme-copy small { font-size: 13px; letter-spacing: .12em; }
.ps-news-theme-copy strong { max-width: 55%; margin-top: 10px; font-size: 25px; line-height: 1.4; overflow-wrap: anywhere; }
.ps-news-theme-copy span { margin-top: 22px; padding: 3px 7px; border: 1px solid #bfd5e1; border-radius: 4px; background: #eff6fa; font-size: 11px; color: #395c70; }
@media (max-width: 600px) {
  .ps-news-card-main { flex-direction: column; gap: 0; }
  .ps-news-cover { flex: 0 0 auto; width: 100%; }
  .ps-news-cover img { height: 180px; }
  .ps-news-theme-cover { height: 180px; }
  .ps-news-theme-copy { padding: 18px; }
  .ps-news-theme-copy strong { font-size: 22px; }
}
</style>
