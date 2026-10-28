<template>
  <div class="ps-page ps-paper-library ps-list-page">
    <div class="ps-toolbar ps-paper-toolbar"><div class="ps-search-inline"><Search /><input v-model.trim="keyword" aria-label="搜索论文资料" placeholder="搜索题名、作者或摘要" @keydown.enter="reload" /><el-button class="ps-ui-action" v-if="keyword" aria-label="清空论文关键词" @click="keyword = ''">清空</el-button></div><el-select v-model="year" filterable allow-create default-first-option aria-label="发表年份，可输入年份" style="width: 160px" @change="yearRange = []"><el-option label="全部年份" value="all" /><el-option v-for="item in yearOptions" :key="item" :label="String(item)" :value="String(item)" /></el-select>
      <el-popover trigger="click" placement="bottom-end" :width="360" popper-class="ps-paper-filter-popover">
        <template #reference><el-button :icon="Filter" :type="yearRange.length || journals.length ? 'primary' : 'default'" plain>更多筛选{{ yearRange.length || journals.length ? ' · 已设置' : '' }}</el-button></template>
        <div class="ps-filter-panel ps-paper-advanced"><h3>高级筛选</h3><label>年份范围<el-date-picker v-model="yearRange" type="yearrange" value-format="YYYY" start-placeholder="起始年" end-placeholder="结束年" aria-label="论文发表年份范围" style="width: 100%" @change="changeYearRange" /></label><label>期刊 / 会议<el-select v-model="journals" multiple filterable allow-create default-first-option aria-label="期刊或会议名称，可输入" placeholder="输入名称或选择期刊"><el-option v-for="item in journalOptions" :key="item" :label="item" :value="item" /></el-select></label><p>可输入期刊名称查询已入库记录。未选择年份时包含日期缺失记录。</p><el-button @click="yearRange = []; journals = []">清除高级筛选</el-button></div>
      </el-popover>
      <el-button @click="resetFilters">重置筛选</el-button></div>
    <SavedSearchBar kind="paper" :query="query" @apply="applySavedSearch" />
    <div class="ps-content-with-filter ps-list-stack">
      <section v-loading="loading" :aria-busy="loading" class="ps-list-stack">
        <div class="ps-paper-list ps-list-scroll" tabindex="0" aria-label="论文列表">
        <article v-for="paper in filteredPapers" :key="paper.id" class="ps-paper-card">
          <div class="ps-paper-main">
            <div class="ps-paper-heading">
            <router-link class="ps-paper-title" :to="`/portal/papers/${paper.id}`">{{ paper.titleZh }}</router-link>
            <el-button type="primary" plain :loading="busy(paper)" :disabled="busy(paper)" @click="add(paper)">{{ inBasket(paper) ? '取消加入资料库' : '加入资料库' }}</el-button>
            </div>
            <div v-if="paper.title && paper.title.trim() !== paper.titleZh?.trim()" class="ps-paper-en-title">{{ paper.title }}</div>
            <div class="ps-paper-authors">{{ paper.authors.join(' · ') }}<span>{{ paper.institutions.join('；') }}</span></div>
            <div class="ps-paper-meta" aria-label="论文概览">
              <span class="ps-paper-journal-name">{{ paper.journal }}</span>
              <span>发表时间 {{ paper.publishedDate || paper.year || '未提供' }}</span>
              <span v-if="paper.citationCount !== '未提供'">被引次数 {{ paper.citationCount }}</span>
              <a v-if="doiUrl(paper)" class="ps-paper-doi" :href="doiUrl(paper)" target="_blank" rel="noopener noreferrer">DOI: {{ paper.doi }}</a>
              <span v-else-if="paper.doi" class="ps-paper-doi">DOI: {{ paper.doi }}</span>
            </div>
          </div>
          <div v-if="paper.keywords.length" class="ps-paper-footer">
          <div v-if="paper.keywords.length" class="ps-tag-row"><span v-for="tag in paper.keywords" :key="tag" class="ps-tag">{{ tag }}</span></div>
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
import { applySavedSearchQuery } from '@/utils/portal/savedSearches'
import { computed, toRefs, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Filter, Search } from '@element-plus/icons-vue'
import PortalEmptyState from '../components/PortalEmptyState.vue'
import usePortalStore from '@/store/modules/portal'
import { getPipelineContentFilters, listPipelineIntelligence, savePipelineWorkspaceItem, deletePipelineWorkspaceItem } from '@/api/pipeline/intelligence'
import { normalizePortalPaper } from '@/store/modules/portal'
import { useListQuery, useListRequest, useListWorkspace, validPage } from '@/utils/portal/listQuery'
import { cleanSummary } from '@/utils/portal/discovery'

const portalStore = usePortalStore()
const currentYear = new Date().getFullYear()
const query = useListQuery({ q: '', year: 'all', years: [], journals: [], page: 1, size: 10 })
function applySavedSearch(filters) { if (!applySavedSearchQuery(query, filters, 'paper')) reload() }
const { q: keyword, year, years: yearRange, journals, page: currentPage, size: pageSize } = toRefs(query)
const { inBasket, busy, toggleBasket } = useListWorkspace(portalStore, { save: savePipelineWorkspaceItem, remove: deletePipelineWorkspaceItem })
const facets = useListRequest(() => ({}), getPipelineContentFilters)
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
  journal: item.journal || '期刊 / 会议未提供',
  abstract: cleanSummary(item.abstractZh || item.abstract_zh || item.abstract || item.summary) || '摘要未提供，请进入详情核对来源。',
  citationCount: item.citations ?? item.citation_count ?? '未提供'
})))
const total = computed(() => Number(data.value?.total || 0))
watch(data, value => { if (value) currentPage.value = validPage(total.value, pageSize.value, currentPage.value) })
function changeYearRange(value) { year.value = 'all'; yearRange.value = value || [] }
function resetFilters() {
  const unchanged = !keyword.value && year.value === 'all' && !yearRange.value?.length && !journals.value.length && currentPage.value === 1
  keyword.value = ''; year.value = 'all'; yearRange.value = []; journals.value = []; currentPage.value = 1
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
.ps-search-inline > button { flex-shrink: 0; padding: 4px 8px; border: 0; border-radius: 4px; background: transparent; color: var(--ps-muted); white-space: nowrap; cursor: pointer; }
.ps-search-inline > button:hover { color: var(--ps-blue); background: var(--ps-blue-soft); }
.ps-paper-library .ps-paper-card { display: block; padding: 18px 20px; border-radius: 10px; }
.ps-paper-heading { display: flex; align-items: flex-start; gap: 16px; margin-bottom: 8px; }
.ps-paper-heading .ps-paper-title { flex: 1; min-width: 0; margin: 0; font-size: 17px; font-weight: 600; line-height: 1.45; text-align: left; overflow-wrap: anywhere; text-decoration: none; }
.ps-paper-main .ps-paper-authors { margin-bottom: 4px; }
.ps-paper-main .ps-paper-meta { display: flex; flex-wrap: wrap; gap: 4px 16px; margin: 0; padding: 0; border: 0; border-radius: 0; background: transparent; }
.ps-paper-meta .ps-paper-journal-name { color: var(--ps-ink-2); font-weight: 600; }
.ps-paper-meta .ps-paper-doi { overflow-wrap: anywhere; min-width: 0; }
.ps-paper-meta a.ps-paper-doi { color: var(--ps-blue); text-decoration: none; }
.ps-paper-meta a.ps-paper-doi:hover { text-decoration: underline; }
.ps-paper-meta a.ps-paper-doi:focus-visible { outline: 2px solid var(--ps-blue); outline-offset: 2px; }
.ps-paper-footer { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 16px; margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--ps-line-soft); }
.ps-paper-footer .ps-tag-row { flex: 1 1 200px; min-width: 0; margin: 0; gap: 6px; }
.ps-paper-library .ps-paper-actions { display: flex; flex: 0 1 auto; align-items: center; flex-wrap: wrap; gap: 4px; margin: 0 0 0 auto; padding: 0; border: 0; }
.ps-paper-actions :deep(.el-button) { margin-left: 0; min-height: 36px; padding-inline: 10px; }
.ps-paper-actions :deep(.el-button.is-text) { color: var(--ps-muted); }
.ps-paper-actions :deep(.el-button.is-text:hover) { color: var(--ps-blue); }
@media (max-width: 600px) {
  .ps-paper-library .ps-paper-card { padding: 16px; }
  .ps-paper-heading { flex-direction: column; gap: 8px; }
  .ps-paper-heading .ps-paper-title { width: 100%; font-size: 16px; }
  .ps-paper-main .ps-paper-meta { gap: 4px 12px; }
  .ps-paper-main .ps-paper-authors span { display: block; margin-left: 0; }
  .ps-paper-actions :deep(.el-button) { min-height: 44px; }
  .ps-paper-footer { align-items: flex-start; }
  .ps-paper-footer .ps-tag-row { flex-basis: 100%; }
  .ps-paper-library .ps-paper-actions { justify-content: flex-end; width: 100%; }
}
</style>
