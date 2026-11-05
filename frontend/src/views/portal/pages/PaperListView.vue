<template>
  <div class="ps-page ps-paper-library ps-list-page">
    <div class="ps-toolbar ps-paper-toolbar" role="search" aria-label="论文筛选">
      <el-input v-model.trim="keyword" class="ps-paper-search" :prefix-icon="Search" clearable aria-label="搜索论文资料" placeholder="搜索题名、作者或摘要" @keydown.enter="reload" />
      <el-select v-model="year" class="ps-paper-year-filter" filterable allow-create default-first-option aria-label="发表年份，可输入年份" @change="yearRange = []">
        <el-option label="全部年份" value="all" />
        <el-option v-for="item in yearOptions" :key="item" :label="String(item)" :value="String(item)" />
      </el-select>
      <el-select v-model="classification" class="ps-paper-category-filter" clearable filterable placeholder="全部类别" aria-label="论文类别">
        <el-option v-for="name in categoryOptions" :key="name" :label="name" :value="name" />
      </el-select>
      <div class="ps-paper-filter-actions">
        <el-popover trigger="click" placement="bottom-end" :width="380" :popper-style="{ maxWidth: 'calc(100vw - 24px)' }" popper-class="ps-paper-filter-popover">
          <template #reference><el-button :icon="Filter" :type="yearRange.length || journals.length ? 'primary' : 'default'" plain>筛选设置{{ yearRange.length || journals.length ? ' · 已设置' : '' }}</el-button></template>
          <el-tabs v-model="filterTab" class="ps-paper-filter-tabs" aria-label="论文筛选设置">
            <el-tab-pane label="高级筛选" name="advanced">
              <div class="ps-filter-panel ps-paper-advanced">
                <label>年份范围<el-date-picker v-model="yearRange" type="yearrange" value-format="YYYY" start-placeholder="起始年" end-placeholder="结束年" aria-label="论文发表年份范围" style="width: 100%" @change="changeYearRange" /></label>
                <label>期刊 / 会议<el-select v-model="journals" multiple filterable allow-create default-first-option aria-label="期刊或会议名称，可输入" placeholder="输入名称或选择期刊"><el-option v-for="item in journalOptions" :key="item" :label="item" :value="item" /></el-select></label>
                <p>选择后自动筛选，可输入期刊名称。未选年份时包含日期缺失记录。</p>
                <el-button :disabled="!yearRange.length && !journals.length" @click="yearRange = []; journals = []">清除高级筛选</el-button>
              </div>
            </el-tab-pane>
            <el-tab-pane label="常用条件" name="saved">
              <SavedSearchBar kind="paper" :query="query" :show-current-filters="false" inline @apply="applySavedSearch" />
            </el-tab-pane>
          </el-tabs>
        </el-popover>
        <el-button :icon="RefreshLeft" @click="resetFilters">重置</el-button>
      </div>
    </div>
    <div class="ps-content-with-filter ps-list-stack">
      <section v-loading="loading" :aria-busy="loading" class="ps-list-stack">
        <div class="ps-paper-list ps-list-scroll" tabindex="0" aria-label="论文列表">
        <article v-for="paper in filteredPapers" :key="paper.id" class="ps-paper-card">
          <div class="ps-paper-card-top" aria-label="论文概览">
            <span class="ps-paper-source" aria-label="论文来源">{{ paper.journal }}</span>
            <time>{{ paper.publishedDate || paper.year || '日期未提供' }}</time>
            <ContentCategory :name="contentCategory(paper)" />
          </div>
          <div class="ps-paper-main">
            <router-link class="ps-paper-title" :to="`/portal/papers/${paper.id}`">{{ paper.titleZh }}</router-link>
            <div v-if="paper.title && paper.title.trim() !== paper.titleZh?.trim()" class="ps-paper-en-title">{{ paper.title }}</div>
            <div class="ps-paper-byline"><span>作者：{{ paper.authors.join(' · ') }}</span><span v-if="paper.institutions.length">机构：{{ paper.institutions.join('；') }}</span></div>
            <p class="ps-paper-summary">{{ paper.abstract }}</p>
          </div>
          <div class="ps-paper-card-footer">
            <div class="ps-paper-topic-tags">
              <ContentEntities :entities="paper.entities" compact />
              <div v-if="paper.keywords.length" class="ps-paper-keywords" aria-label="论文关键词"><el-tag v-for="tag in paper.keywords" :key="tag" size="small" type="info" effect="plain">{{ tag }}</el-tag></div>
            </div>
            <div class="ps-paper-row-actions">
              <el-link v-if="doiUrl(paper)" class="ps-paper-doi" type="primary" underline="hover" :href="doiUrl(paper)" :title="`DOI: ${paper.doi}`" :aria-label="`查看论文原文，DOI: ${paper.doi}`" target="_blank" rel="noopener noreferrer">DOI 原文</el-link>
              <el-button type="primary" plain :loading="busy(paper)" :disabled="busy(paper)" @click="add(paper)">{{ inBasket(paper) ? '取消加入资料库' : '加入资料库' }}</el-button>
            </div>
          </div>
          <div v-if="(paper.doi && !doiUrl(paper)) || collectionTime(paper) || paper.citationCount !== '未提供'" class="ps-paper-record-meta" aria-label="论文来源信息">
            <span v-if="paper.doi && !doiUrl(paper)" class="ps-paper-doi">DOI: {{ paper.doi }}</span>
            <span v-if="collectionTime(paper)">采集于 {{ collectionTime(paper) }}</span>
            <span v-if="paper.citationCount !== '未提供'">被引 {{ paper.citationCount }} 次</span>
          </div>
        </article>
        <PortalEmptyState v-if="loadError && !loading" title="论文加载失败" :description="loadError" action-label="重新加载" @action="reload" />
        <PortalEmptyState v-else-if="!filteredPapers.length && !loading" title="没有匹配的论文" description="尝试放宽年份或期刊筛选。" action-label="重置筛选" @action="resetFilters" />
        </div>
        <div v-if="total > 0 && !loading && !loadError" class="ps-pagination" aria-label="论文列表分页">
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
import ContentEntities from '../components/ContentEntities.vue'
import ContentCategory from '../components/ContentCategory.vue'
import { applySavedSearchQuery } from '@/utils/portal/savedSearches'
import { computed, ref, toRefs, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Filter, RefreshLeft, Search } from '@element-plus/icons-vue'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'
import { getPipelineContentFilters, listPipelineIntelligence, savePipelineWorkspaceItem, deletePipelineWorkspaceItem } from '@/api/pipeline/intelligence'
import { normalizePortalPaper } from '@/store/modules/portal'
import { useListQuery, useListRequest, useListWorkspace, validPage } from '@/utils/portal/listQuery'
import { cleanSummary } from '@/utils/portal/discovery'
import { contentCategory, collectionTime } from '@/utils/portal/contentPresentation'

const portalStore = usePortalStore()
const filterTab = ref('advanced')
const currentYear = new Date().getFullYear()
const query = useListQuery({ q: '', year: 'all', years: [], journals: [], classification: '', page: 1, size: 10 })
function applySavedSearch(filters) { if (!applySavedSearchQuery(query, filters, 'paper')) reload() }
const { q: keyword, year, years: yearRange, journals, classification, page: currentPage, size: pageSize } = toRefs(query)
const { inBasket, busy, toggleBasket } = useListWorkspace(portalStore, { save: savePipelineWorkspaceItem, remove: deletePipelineWorkspaceItem })
const facets = useListRequest(() => ({}), getPipelineContentFilters)
const categoryOptions = computed(() => [...new Set([...(facets.data.value?.paperCategories || facets.data.value?.categories || []), ...(classification.value ? [classification.value] : [])])])
const journalOptions = computed(() => [...new Set([...(facets.data.value?.journals || []), ...journals.value])])
const yearOptions = computed(() => [...new Set([currentYear, ...(facets.data.value?.years || []), ...(year.value === 'all' ? [] : [Number(year.value)])])].sort((a, b) => b - a))
const selectedYearRange = computed(() => {
  if (year.value !== 'all') {
    const selected = Number(year.value)
    return [selected, selected]
  }
  return yearRange.value || []
})
const { data, loading, loadError, reload } = useListRequest(() => {
  const [yearFrom, yearTo] = selectedYearRange.value.map(Number)
  return {
      category: 'paper',
      tag: classification.value || undefined,
      keyword: keyword.value || undefined,
      yearFrom,
      yearTo,
      journal: journals.value.length ? journals.value.join(',') : undefined,
      pageNum: currentPage.value,
      pageSize: pageSize.value
  }
}, params => {
  if ([params.yearFrom, params.yearTo].some(value => value !== undefined && (!Number.isInteger(value) || value < 1600 || value > 2200))) throw new Error('请输入 1600–2200 之间的有效年份')
  if (params.yearFrom > params.yearTo) throw new Error('起始年份不能晚于结束年份')
  return listPipelineIntelligence(params)
})
const filteredPapers = computed(() => (data.value?.rows || []).map(item => ({
  ...normalizePortalPaper(item),
  authors: Array.isArray(item.authors) ? item.authors : item.authors ? [item.authors] : ['作者信息未提供'],
  institutions: item.institutions || [],
  journal: item.journal || item.source || item.source_name || '来源未提供',
  abstract: cleanSummary(item.abstractZh || item.abstract_zh || item.abstract || item.summary) || '摘要未提供，请进入详情核对来源。',
  citationCount: item.citations ?? item.citation_count ?? '未提供'
})))
const total = computed(() => Number(data.value?.total || 0))
watch(data, value => { if (value) currentPage.value = validPage(total.value, pageSize.value, currentPage.value) })
function changeYearRange(value) { year.value = 'all'; yearRange.value = value || [] }
function resetFilters() {
  const unchanged = !keyword.value && year.value === 'all' && !yearRange.value?.length && !journals.value.length && !classification.value && currentPage.value === 1
  keyword.value = ''; year.value = 'all'; yearRange.value = []; journals.value = []; classification.value = ''; currentPage.value = 1
  if (unchanged) reload()
}
async function add(paper) {
  try {
    const result = await toggleBasket(paper, 'paper')
    if (result === 'saved') ElMessage.success('已加入资料库')
    else if (result === 'removed') ElMessage.success('已取消加入资料库')
  } catch (error) { ElMessage.error(error?.msg || '资料库更新失败，请重试') }
}
function doiUrl(paper) {
  const doi = String(paper?.doi || '').trim().replace(/^doi:\s*/i, '').replace(/^https?:\/\/(?:dx\.)?doi\.org\//i, '')
  if (!/^10\.\d{4,9}\/\S+$/i.test(doi)) return ''
  return `https://doi.org/${doi.split('/').map(encodeURIComponent).join('/')}`
}
</script>

<style scoped>
.ps-paper-library > .ps-paper-toolbar { display: grid; grid-template-columns: minmax(220px, 1fr) 136px 164px max-content; --el-component-size: 40px; align-items: center; gap: 10px; padding: 10px 12px; }
.ps-paper-toolbar > :is(.ps-paper-search, .ps-paper-year-filter, .ps-paper-category-filter) { width: 100%; min-width: 0; height: var(--el-component-size); }
.ps-paper-filter-actions { display: flex; align-items: center; gap: 8px; min-width: 0; }
.ps-paper-filter-actions :deep(.el-button) { height: var(--el-component-size); margin: 0; }
.ps-paper-filter-tabs { max-height: min(560px, calc(100dvh - 180px)); overflow-y: auto; }
.ps-paper-filter-tabs :deep(.el-tabs__header) { margin-bottom: 8px; }
.ps-paper-filter-tabs :deep(.ps-saved-search-bar) { display: block; margin: 0; }
.ps-paper-filter-tabs :deep(.ps-saved-search-panel > strong) { display: none; }
@media (max-width: 1150px) {
  .ps-paper-library > .ps-paper-toolbar { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) max-content; }
  .ps-paper-toolbar > .ps-paper-search { grid-column: 1 / -1; }
}
@media (max-width: 760px) {
  .ps-paper-library > .ps-paper-toolbar { grid-template-columns: repeat(2, minmax(0, 1fr)); --el-component-size: 44px; gap: 8px; }
  .ps-paper-filter-actions { grid-column: 1 / -1; }
  .ps-paper-filter-actions > :deep(.el-button) { flex: 1; min-width: 0; }
}
/* Compact bibliographic header, reading content and a shared action footer. */
.ps-paper-library .ps-paper-list { gap: 10px; align-content: start; }
.ps-paper-library .ps-paper-card { display: block; min-width: 0; padding: 16px 20px; border-radius: 10px; box-shadow: none; }
.ps-paper-card-top { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; min-width: 0; margin-bottom: 8px; font-size: 13px; line-height: 1.5; color: var(--ps-muted); }
.ps-paper-card-top time { white-space: nowrap; }
.ps-paper-source { color: var(--ps-ink-2); font-weight: 600; overflow-wrap: anywhere; }
.ps-paper-main .ps-paper-title { display: block; margin: 0; color: var(--ps-ink); font-size: 18px; font-weight: 600; line-height: 1.55; text-align: left; overflow-wrap: anywhere; text-decoration: none; }
.ps-paper-main .ps-paper-title:hover { color: var(--ps-blue); }
.ps-paper-title:focus-visible, .ps-paper-doi:focus-visible { outline: 2px solid var(--ps-blue); outline-offset: 3px; border-radius: 4px; }
.ps-paper-main .ps-paper-en-title { margin: 4px 0 0; overflow-wrap: anywhere; }
.ps-paper-byline { display: flex; flex-wrap: wrap; gap: 4px 16px; margin-top: 5px; color: var(--ps-muted); font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.ps-paper-main > .ps-paper-summary { display: block; margin: 9px 0 0; color: var(--ps-ink-2); font-size: 14px; line-height: 1.8; overflow-wrap: anywhere; }
.ps-paper-card-footer { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; margin-top: 12px; }
.ps-paper-topic-tags { flex: 1 1 260px; min-width: 0; display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.ps-paper-topic-tags :deep(.ps-content-entities) { margin: 0; max-width: 100%; }
.ps-paper-keywords { display: flex; flex-wrap: wrap; gap: 6px; min-width: 0; }
.ps-paper-keywords .el-tag { max-width: 100%; height: auto; white-space: normal; overflow-wrap: anywhere; }
.ps-paper-row-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin-left: auto; }
.ps-paper-row-actions > .el-button { margin: 0; }
.ps-paper-record-meta { display: flex; flex-wrap: wrap; gap: 4px 16px; margin-top: 8px; color: var(--ps-muted); font-size: 12px; line-height: 1.6; }
.ps-paper-doi { min-width: 0; overflow-wrap: anywhere; }
@media (max-width: 600px) {
  .ps-paper-library .ps-paper-card { padding: 14px; }
  .ps-paper-main .ps-paper-title { font-size: 16px; }
  .ps-paper-byline { flex-direction: column; gap: 4px; }
  .ps-paper-topic-tags { flex-basis: 100%; }
  .ps-paper-row-actions { width: 100%; justify-content: flex-end; }
  .ps-paper-row-actions > .el-button { min-height: 44px; }
}
</style>
